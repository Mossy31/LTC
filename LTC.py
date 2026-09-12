#--------------------------------------#

# IndietroRobot
# Zoom
# SpostaPunti
# CalcolareAngoloIniziale
# InterfacciaGraficaBoostata
# Angoli Interativi
# Segmenti Interativi

#--------------------------------------#

from PIL import ImageTk
from PIL import Image
import screeninfo
import tkinter
import math
import PIL

SogliaRimozionePunti = 10
Raggio = 3.5
ListaPunti = []
ImmagineTappeto = "Mappa.png"
IndirizzoImmagineCursore = "Cursore.png"
PuntoFisso = (347, 1883, 0)

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
    X = event.x
    Y = event.y

    ListaPunti.append((X, Y, 0))
    Aggiorna()

def ClickC(event):
    X = event.x
    Y = event.y
    ListaPunti.append((X, Y, 1, 0, 0, 0))

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
        ListaPunti.append(PuntoFisso)
    for Numero, Punto in enumerate(ListaPunti):
        X1 = Punto[0]
        Y1 = Punto[1]
        Type = Punto[2]
        if Type == 1:
            Tela.create_oval(X1-Raggio, Y1-Raggio, X1+Raggio, Y1+Raggio, fill="blue", outline="black", tags="Punti")
        else:
            Tela.create_oval(X1-Raggio, Y1-Raggio, X1+Raggio, Y1+Raggio, fill="red", outline="black", tags="Punti")      
        if Numero > 0:
            X2 = PuntoPrecedente[0]
            Y2 = PuntoPrecedente[1]
            Tela.create_line(X1, Y1, X2, Y2, fill="black", tags="Linee")        
        PuntoPrecedente = Punto

def Esporta():
    with open("Output.txt", "w") as File:
        if len(ListaPunti) > 1:
            for ContatorePunto in range(len(ListaPunti)):
                try:
                    Punto1 = ListaPunti[ContatorePunto]
                    Punto2 = ListaPunti[ContatorePunto + 1]
                    Punto3 = ListaPunti[ContatorePunto + 2]
                    if Punto2[2] > 0 and ContatorePunto + 2 < len(ListaPunti):
                        File.write(f"A {Distanza(Punto1[0], Punto1[1], Punto2[0], Punto2[1])}\n")
                        
                        if len(Punto2) > 5:
                            File.write(f"M {Punto2[3]} {Punto2[4]}\n")
                            File.write(f"M {Punto2[3]} {Punto2[5]}\n")
                        else:
                            File.write(f"M {Punto2[3]} {Punto2[4]}\n")

                        File.write(f"G {CalcoloAngolo(Punto1[0], Punto1[1], Punto2[0], Punto2[1], Punto3[0], Punto3[1])}\n")
                    else:
                        File.write(f"A {Distanza(Punto1[0], Punto1[1], Punto2[0], Punto2[1])}\n")
                        File.write(f"G {CalcoloAngolo(Punto1[0], Punto1[1], Punto2[0], Punto2[1], Punto3[0], Punto3[1])}\n")
                except IndexError:
                    try:
                        Punto1 = ListaPunti[ContatorePunto]
                        Punto2 = ListaPunti[ContatorePunto + 1]
                        if Punto1[2] > 0:
                            File.write(f"M {Punto2[3]} {Punto2[4]}\n")
                        File.write(f"A {Distanza(Punto1[0], Punto1[1], Punto2[0], Punto2[1])}\n")
                    except IndexError:
                        try:                            
                            Punto1 = ListaPunti[ContatorePunto]
                            if Punto1[2] > 0:
                                File.write(f"M {Punto2[3]} {Punto2[4]}\n")                            
                        except:
                            File.close()
    
    with open("Output.txt", "r") as File:
        print(File.read())

def Ridisegna():
    ListaPunti.clear()
    Aggiorna()
    with open("Output.txt", "r") as File:
        for Number, Line in enumerate(File.readlines()):
            print(f"{Number}) {Line.strip()}")
            if Line.strip()[0] == "A":
                ListaPunti.append(PuntoFisso + (0, Line.strip().removeprefix("A").strip()), 0)



def Distanza(X1, Y1, X2, Y2):
    Distanza = math.sqrt(pow(int(X1)-int(X2), 2) + pow(int(Y1)-int(Y2), 2))
    return Distanza/PPM

def CalcoloAngolo(X1, Y1, X2, Y2, X3, Y3):
    
    #DaCapire#

    V1 = (X2 - X1, Y2 - Y1)
    V2 = (X3 - X2, Y3 - Y2)
    Det = V1[0]*V2[1] - V1[1]*V2[0]
    Dot = V1[0]*V2[0] + V1[1]*V2[1]
    AngoloRadianti = math.atan2(Det, Dot)
    AngoloGradi = math.degrees(AngoloRadianti)
    return round(AngoloGradi)

    #DaCapire#

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

Tela = tkinter.Canvas(Finestra, width=LarghezzaImmagine_px, height=AltezzaImmagine_px)
Tela.grid(row=1, column=0, columnspan=4)

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

print("LoL")
Ridisegna()
Aggiorna

Finestra.mainloop()