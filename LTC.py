#--------------------------------------#

# IndietroRobot
# CodiceBlocchi

#--------------------------------------#

from PIL import ImageTk
from PIL import Image
import screeninfo
import tkinter
import math
import json
import PIL

SogliaRimozionePunti = 10
Raggio = 5
ListaPunti = []
ImmagineTappeto = "Mappa.png"
IndirizzoImmagineCursore = "Cursore.png"
IndirizzoConfig = "Config.json"
ModalitaCenter = False

def CaricaConfig():
    with open(IndirizzoConfig, "r") as File:
        return json.load(File)["PuntoFisso"]

def SalvaConfig(Punto):
    with open(IndirizzoConfig, "w") as File:
        json.dump({"PuntoFisso": Punto}, File, indent=4)

PuntoFisso = CaricaConfig()
ListaPunti.append(list(PuntoFisso))

MmPerStud = 8
MmPerPixelArt = MmPerStud / 2

PixelArtLarghezzaRobot = 101
PixelArtAltezzaRobot = 101

DimensioniRobot = (PixelArtLarghezzaRobot * MmPerPixelArt, PixelArtAltezzaRobot * MmPerPixelArt)

Schermo = screeninfo.get_monitors()[0]

AltezzaSchermo_px = Schermo.height
LarghezzaSchermo_px = Schermo.width
AltezzaSchermo_mm = Schermo.height_mm
LarghezzaSchermo_mm = Schermo.width_mm

Diangonale_mm = math.sqrt(LarghezzaSchermo_mm**2 + AltezzaSchermo_mm**2)
Diagonale_px = math.sqrt(LarghezzaSchermo_px**2 + AltezzaSchermo_px**2)

PPM = Diagonale_px / Diangonale_mm

AltezzaImmagine_mm = 1143
LarghezzaImmagine_mm = 2000

FattoreVisualizzazione = min(
    (LarghezzaSchermo_px * 0.9) / (LarghezzaImmagine_mm * PPM),
    (AltezzaSchermo_px * 0.9) / (AltezzaImmagine_mm * PPM),
    1
)
PPM *= FattoreVisualizzazione

AltezzaImmagine_px = int(AltezzaImmagine_mm * PPM)
LarghezzaImmagine_px = int(LarghezzaImmagine_mm * PPM)

def ClickS(event):
    global PuntoFisso, ModalitaCenter
    X = event.x
    Y = event.y
    Aggiungi = True    
    
    if ModalitaCenter:
        PuntoFisso = [X, Y, 0]
        SalvaConfig(PuntoFisso)
        if len(ListaPunti) > 0:
            ListaPunti[0] = list(PuntoFisso)
        else:
            ListaPunti.append(list(PuntoFisso))
        ModalitaCenter = not ModalitaCenter
    
    else:
        for Punto in ListaPunti:
            if (Punto[0] >= X-SogliaRimozionePunti and Punto[0]<= X+SogliaRimozionePunti):
                if(Punto[1] >= Y-SogliaRimozionePunti and Punto[1]<= Y+SogliaRimozionePunti):
                    if Punto[2] == 0:
                        Punto[2] = 1
                    elif Punto[2] == 1:
                        Punto[2] = 0
                    Aggiungi = False
        if Aggiungi:
            ListaPunti.append([X, Y, 0])
    Aggiorna()

def Center():
    global ModalitaCenter
    ModalitaCenter = not ModalitaCenter

def ClickC(event):
    X = event.x
    Y = event.y
    ListaPunti.append([X, Y, 2])

    Aggiorna()

def ClickD(event):
    X = event.x
    Y = event.y

    for Punto in ListaPunti:
        if (Punto[0] >= X-SogliaRimozionePunti and Punto[0]<= X+SogliaRimozionePunti):
            if(Punto[1] >= Y-SogliaRimozionePunti and Punto[1]<= Y+SogliaRimozionePunti):
                ListaPunti.remove(Punto)
                Aggiorna()
                break

def Aggiorna():
    Tela.delete("Punti", "Linee")
    if len(ListaPunti) < 1:
        ListaPunti.append(list(PuntoFisso))
    for Numero, Punto in enumerate(ListaPunti):
        X1 = Punto[0]
        Y1 = Punto[1]
        Type = Punto[2]
        if Type == 2:
            Tela.create_oval(X1-Raggio, Y1-Raggio, X1+Raggio, Y1+Raggio, fill="blue", outline="black", tags="Punti")
        elif Type == 1:
            Tela.create_oval(X1-Raggio, Y1-Raggio, X1+Raggio, Y1+Raggio, fill="yellow", outline="black", tags="Punti")
        else:
            Tela.create_oval(X1-Raggio, Y1-Raggio, X1+Raggio, Y1+Raggio, fill="red", outline="black", tags="Punti")      
        if Numero > 0:
            X2 = PuntoPrecedente[0]
            Y2 = PuntoPrecedente[1]
            Tela.create_line(X1, Y1, X2, Y2, fill="black", tags="Linee")        
        PuntoPrecedente = Punto

def Esporta():
    with open("Output.txt", "w") as File:
        Precedente = ListaPunti[0]
        for Punto in ListaPunti[1:]:
            Gradi = Angle(Precedente, Punto)
            Distanza = Distance(Precedente, Punto)
            if Punto[2] == 1:
                Gradi += 180
                Distanza = -Distanza
            File.write(f"G {round(Gradi)}\n")
            File.write(f"A {round(Distanza)}\n")
            if Punto[2] == 2:
                File.write("M 0 0\n")
            Precedente = Punto

def Distance(A, B):
    return math.sqrt((A[0] - B[0])**2 + (A[1] - B[1])**2)/PPM

def Angle(A, B):
    return math.degrees(math.atan2(A[1] - B[1], A[0] - B[0]))-90

def Salva():
    with open("Punti.txt", "w") as File:
        File.write(str(ListaPunti))

def Apri():
    with open("Punti.txt", "r") as File:
        ListaPunti.clear()
        ListaPunti.extend(eval(File.read().strip()))
        Aggiorna()

def Cancella():
    ListaPunti.clear()
    Aggiorna()

def MovimentoCursore(event):
    Tela.coords(CursoreScalatoTkinterMouse, event.x, event.y)
Rotellina = 0

def MovimentoRotellinaSu(event):
    global Rotellina
    if Rotellina <= 180:
        Rotellina += 2
        ImpostaImmagine(Rotellina)

def MovimentoRotellinaGiu(event):
    global Rotellina
    if Rotellina >= -180:
        Rotellina -= 2
        ImpostaImmagine(Rotellina)
    
def ImpostaImmagine(Gradi):
    global ImmagineCursoreScalatoTkinter
    global IndirizzoImmagineCursore, DimensioniRobot, PPM, Rotellina
    try:
        ImmagineCursore = Image.open(f"Immagini/Cursore{Gradi}.png")
        DimensioniRobotPixel = (round(DimensioniRobot[0]*PPM), round(DimensioniRobot[1]*PPM))
        ImmagineCursoreScalato = ImmagineCursore.resize(DimensioniRobotPixel)
        ImmagineCursoreScalatoTkinter = ImageTk.PhotoImage(ImmagineCursoreScalato)
        Tela.itemconfig(CursoreScalatoTkinterMouse, image=ImmagineCursoreScalatoTkinter)
    except:
        pass

Finestra = tkinter.Tk()
Finestra.title("Line-To-Code")

Finestra.columnconfigure(0, weight=1)
Finestra.columnconfigure(1, weight=1)
Finestra.columnconfigure(2, weight=1)
Finestra.columnconfigure(3, weight=1)
Finestra.columnconfigure(4, weight=1)
Finestra.columnconfigure(5, weight=1)

Finestra.rowconfigure(0, weight=1)
Finestra.rowconfigure(1, weight=1)

BottoneEsporta = tkinter.Button(Finestra, text="Esporta", command=Esporta, padx=20, pady=20, anchor=tkinter.N)
BottoneEsporta.grid(row=0, column=0, sticky="nsew")
BottoneSalva = tkinter.Button(Finestra, text="Salva", command=Salva, padx=20, pady=20, anchor=tkinter.N)
BottoneSalva.grid(row=0, column=1, sticky="nsew")
BottoneApri = tkinter.Button(Finestra, text="Apri", command=Apri, padx=20, pady=20, anchor=tkinter.N)
BottoneApri.grid(row=0, column=2, sticky="nsew")
BottoneCancella = tkinter.Button(Finestra, text="Cancella", command=Cancella, padx=20, pady=20, anchor=tkinter.N)
BottoneCancella.grid(row=0, column=3, sticky="nsew")
BottoneCenter = tkinter.Button(Finestra, text="Center", command=Center, padx=20, pady=20, anchor=tkinter.N)
BottoneCenter.grid(row=0, column=4, sticky="nsew")
BottoneExit = tkinter.Button(Finestra, text="Exit", command=Finestra.destroy, padx=20, pady=20, anchor=tkinter.N)
BottoneExit.grid(row=0, column=5, sticky="nsew")

Tela = tkinter.Canvas(Finestra, width=LarghezzaImmagine_px, height=AltezzaImmagine_px)
Tela.grid(row=1, column=0, columnspan=6)

Tela.bind("<Button-1>", ClickS)
Tela.bind("<Button-2>", ClickC)
Tela.bind("<Button-3>", ClickD)
Tela.bind("<Motion>", MovimentoCursore)
Tela.bind("<Button-4>", MovimentoRotellinaSu)
Tela.bind("<Button-5>", MovimentoRotellinaGiu)

TappetoGara = Image.open(ImmagineTappeto)
TappetoGaraScalato = TappetoGara.resize((LarghezzaImmagine_px, AltezzaImmagine_px))
TappetoGaraScalatoTkinter = ImageTk.PhotoImage(TappetoGaraScalato)
Tappeto = Tela.create_image(0, 0, anchor=tkinter.NW, image=TappetoGaraScalatoTkinter, tags="Tappeto")

ImmagineCursore = Image.open(IndirizzoImmagineCursore)
DimensioniRobotPixel = (round(DimensioniRobot[0]*PPM), round(DimensioniRobot[1]*PPM))
ImmagineCursoreScalato = ImmagineCursore.resize(DimensioniRobotPixel)
ImmagineCursoreScalatoTkinter = ImageTk.PhotoImage(ImmagineCursoreScalato)
CursoreScalatoTkinterMouse = Tela.create_image(LarghezzaImmagine_px/2, AltezzaImmagine_px/2, image=ImmagineCursoreScalatoTkinter, anchor="center", tags="Mouse")

Input = input("Generare(y/N): ")

if(["Yes", "yes", "Y", "y"].__contains__(Input)):
    print("\n")
    for Angolo in range(0, 180, 2):
        ImmagineCursorePositiva = ImmagineCursore.rotate(Angolo)
        ImmagineCursorePositiva.save(f"Immagini/{IndirizzoImmagineCursore.removesuffix(".png")}{str(Angolo)}.png")
        ImmagineCursoreNegativa = ImmagineCursore.rotate(-Angolo)
        ImmagineCursoreNegativa.save(f"Immagini/{IndirizzoImmagineCursore.removesuffix(".png")}-{str(Angolo)}.png")

Aggiorna()
Finestra.mainloop()