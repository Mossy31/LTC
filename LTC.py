#--------------------------------------#

# IndietroRobot
# CodiceBlocchi

#--------------------------------------#

from PIL import ImageTk
from PIL import Image
import screeninfo
import tkinter
import copy
import math
import json

SogliaRimozionePunti = 10
SogliaTrascinamento = 3
Raggio = 5
PassoSnap = 45
ListaPunti = []
StoriaAnnulla = []
ImmagineTappeto = "Mappa.png"
IndirizzoImmagineCursore = "Cursore.png"
IndirizzoConfig = "Config.json"
IndirizzoPunti = "Punti.txt"
ModalitaCenter = False

# Tipi di punto
AVANTI = 0
INDIETRO = 1
MOTORE = 2
CURVA = 3
ColoriTipi = {AVANTI: "red", INDIETRO: "yellow", MOTORE: "blue", CURVA: "green"}

# Tasti premuti insieme al click (event.state)
SHIFT = 0x0001
CTRL = 0x0004

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

# I punti sono sempre salvati in mm, i pixel servono solo per disegnare
def InPixel(Valore):
    return Valore * PPM

def InMm(Valore):
    return Valore / PPM

def NuovoPunto(X, Y, Tipo=AVANTI):
    Punto = {"X": X, "Y": Y, "Tipo": Tipo}
    if Tipo == MOTORE:
        Punto["Target"] = 0
        Punto["Gradi"] = 0
    return Punto

def CaricaConfig():
    with open(IndirizzoConfig, "r") as File:
        Punto = json.load(File)["PuntoFisso"]
    if isinstance(Punto, list):
        # Vecchio formato in pixel
        return NuovoPunto(InMm(Punto[0]), InMm(Punto[1]))
    return NuovoPunto(Punto["X"], Punto["Y"])

def SalvaConfig(Punto):
    with open(IndirizzoConfig, "w") as File:
        json.dump({"PuntoFisso": {"X": round(Punto["X"], 1), "Y": round(Punto["Y"], 1)}}, File, indent=4)

PuntoFisso = CaricaConfig()
ListaPunti.append(dict(PuntoFisso))

#--------------------------------------#
# Geometria (mm, Y verso il basso, gradi in senso orario partendo dall'alto)

def Distance(A, B):
    return math.hypot(A["X"] - B["X"], A["Y"] - B["Y"])

def Angle(A, B):
    return math.degrees(math.atan2(A["Y"] - B["Y"], A["X"] - B["X"]))-90

def Vicino(Gradi, Riferimento):
    # Sceglie l'angolo equivalente piu' vicino, cosi' il robot gira dal lato corto
    while Gradi - Riferimento > 180:
        Gradi -= 360
    while Gradi - Riferimento < -180:
        Gradi += 360
    return Gradi

def Arco(A, B, Direzione):
    # Arco che parte da A tangente alla direzione del robot e finisce in B
    # Ritorna (Raggio, Angolo, Centro) oppure None se B e' in linea retta
    Dx = math.sin(math.radians(Direzione))
    Dy = -math.cos(math.radians(Direzione))
    Vx = B["X"] - A["X"]
    Vy = B["Y"] - A["Y"]
    Phi = math.atan2(Dx * Vy - Dy * Vx, Dx * Vx + Dy * Vy)
    if abs(math.sin(Phi)) < 0.01:
        return None
    RaggioArco = math.hypot(Vx, Vy) / (2 * abs(math.sin(Phi)))
    Segno = 1 if Phi > 0 else -1
    Centro = (A["X"] - Dy * RaggioArco * Segno, A["Y"] + Dx * RaggioArco * Segno)
    return RaggioArco, math.degrees(2 * Phi), Centro

def PuntiArco(Da, DatiArco):
    _, Angolo, Centro = DatiArco
    Rx = Da["X"] - Centro[0]
    Ry = Da["Y"] - Centro[1]
    Passi = max(2, int(abs(Angolo) / 5))
    Coordinate = []
    for I in range(Passi + 1):
        T = math.radians(Angolo) * I / Passi
        X = Centro[0] + Rx * math.cos(T) - Ry * math.sin(T)
        Y = Centro[1] + Rx * math.sin(T) + Ry * math.cos(T)
        Coordinate += [InPixel(X), InPixel(Y)]
    return Coordinate

def Segmenti():
    # Percorre la lista tenendo traccia della direzione del robot
    Direzione = 0
    Risultato = []
    for Precedente, Punto in zip(ListaPunti, ListaPunti[1:]):
        Prima = Direzione
        DatiArco = Arco(Precedente, Punto, Direzione) if Punto["Tipo"] == CURVA else None
        if DatiArco:
            Direzione += DatiArco[1]
        else:
            Gradi = Angle(Precedente, Punto)
            if Punto["Tipo"] == INDIETRO:
                Gradi += 180
            Direzione = Vicino(Gradi, Direzione)
        Risultato.append({"Da": Precedente, "A": Punto, "Prima": Prima, "Dopo": Direzione, "Arco": DatiArco})
    return Risultato

def DirezioneFinale():
    Lista = Segmenti()
    return Lista[-1]["Dopo"] if Lista else 0

def Snap(X, Y):
    # Blocca la linea a multipli di PassoSnap gradi rispetto all'ultimo punto
    Ultimo = ListaPunti[-1]
    Arrivo = {"X": X, "Y": Y}
    Gradi = math.radians(round(Angle(Ultimo, Arrivo) / PassoSnap) * PassoSnap)
    Distanza = Distance(Ultimo, Arrivo)
    return Ultimo["X"] + Distanza * math.sin(Gradi), Ultimo["Y"] - Distanza * math.cos(Gradi)

def TrovaPunto(X, Y):
    for Punto in reversed(ListaPunti):
        if abs(InPixel(Punto["X"]) - X) <= SogliaRimozionePunti and abs(InPixel(Punto["Y"]) - Y) <= SogliaRimozionePunti:
            return Punto
    return None

#--------------------------------------#
# Annulla

def SalvaStato():
    StoriaAnnulla.append(copy.deepcopy(ListaPunti))
    if len(StoriaAnnulla) > 100:
        StoriaAnnulla.pop(0)

def Annulla(event=None):
    if StoriaAnnulla:
        ListaPunti[:] = StoriaAnnulla.pop()
        Aggiorna()

#--------------------------------------#
# Mouse

Trascinato = None
Spostato = False
InizioTrascinamento = (0, 0)

def PremiS(event):
    global PuntoFisso, ModalitaCenter, Trascinato, Spostato, InizioTrascinamento
    SalvaStato()

    if ModalitaCenter:
        PuntoFisso = NuovoPunto(InMm(event.x), InMm(event.y))
        SalvaConfig(PuntoFisso)
        ListaPunti[0] = dict(PuntoFisso)
        Center()
        Aggiorna()
        return

    Trascinato = TrovaPunto(event.x, event.y)
    Spostato = False
    InizioTrascinamento = (event.x, event.y)
    if Trascinato is None:
        X = InMm(event.x)
        Y = InMm(event.y)
        Tipo = CURVA if event.state & CTRL else AVANTI
        if event.state & SHIFT and Tipo != CURVA:
            X, Y = Snap(X, Y)
        ListaPunti.append(NuovoPunto(X, Y, Tipo))
        Aggiorna()

def TrascinaS(event):
    global Spostato
    MovimentoCursore(event)
    if Trascinato is None:
        return
    if abs(event.x - InizioTrascinamento[0]) > SogliaTrascinamento or abs(event.y - InizioTrascinamento[1]) > SogliaTrascinamento:
        Spostato = True
    if Spostato:
        Trascinato["X"] = InMm(event.x)
        Trascinato["Y"] = InMm(event.y)
        Aggiorna()

def RilasciaS(event):
    global Trascinato
    if Trascinato is not None and not Spostato:
        # Click senza trascinare: cambia tipo al punto
        Tipo = Trascinato["Tipo"]
        if event.state & CTRL:
            if Tipo == CURVA:
                Trascinato["Tipo"] = AVANTI
            elif Tipo in (AVANTI, INDIETRO):
                Trascinato["Tipo"] = CURVA
        elif Tipo == AVANTI:
            Trascinato["Tipo"] = INDIETRO
        elif Tipo == INDIETRO:
            Trascinato["Tipo"] = AVANTI
        Aggiorna()
    Trascinato = None

def ClickC(event):
    Punto = TrovaPunto(event.x, event.y)
    Nuovo = Punto is None
    if Nuovo:
        Punto = NuovoPunto(InMm(event.x), InMm(event.y), MOTORE)
    Valori = ChiediParametriMotore(Punto.get("Target", 0), Punto.get("Gradi", 0))
    if Valori is None:
        return
    SalvaStato()
    Punto["Tipo"] = MOTORE
    Punto["Target"], Punto["Gradi"] = Valori
    if Nuovo:
        ListaPunti.append(Punto)
    Aggiorna()

def ClickD(event):
    Punto = TrovaPunto(event.x, event.y)
    if Punto is not None:
        SalvaStato()
        ListaPunti.remove(Punto)
        Aggiorna()

def ChiediParametriMotore(Target, Gradi):
    Finestrella = tkinter.Toplevel(Finestra)
    Finestrella.title("Parametri motore")
    Finestrella.transient(Finestra)
    Risultato = []

    tkinter.Label(Finestrella, text="Target (1-4)").grid(row=0, column=0, padx=10, pady=5, sticky="w")
    CampoTarget = tkinter.Entry(Finestrella, width=8)
    CampoTarget.insert(0, str(Target))
    CampoTarget.grid(row=0, column=1, padx=10, pady=5)

    tkinter.Label(Finestrella, text="Gradi").grid(row=1, column=0, padx=10, pady=5, sticky="w")
    CampoGradi = tkinter.Entry(Finestrella, width=8)
    CampoGradi.insert(0, str(Gradi))
    CampoGradi.grid(row=1, column=1, padx=10, pady=5)

    def Conferma(event=None):
        try:
            Risultato.extend([int(CampoTarget.get()), int(CampoGradi.get())])
        except ValueError:
            return
        Finestrella.destroy()

    tkinter.Button(Finestrella, text="OK", command=Conferma).grid(row=2, column=0, columnspan=2, pady=5)
    Finestrella.bind("<Return>", Conferma)
    Finestrella.bind("<Escape>", lambda event: Finestrella.destroy())
    CampoTarget.focus_set()
    CampoTarget.select_range(0, tkinter.END)
    try:
        Finestrella.wait_visibility()
        Finestrella.grab_set()
    except tkinter.TclError:
        pass
    Finestra.wait_window(Finestrella)
    return Risultato or None

#--------------------------------------#

def Center():
    global ModalitaCenter
    ModalitaCenter = not ModalitaCenter
    BottoneCenter.config(relief=tkinter.SUNKEN if ModalitaCenter else tkinter.RAISED)

def Aggiorna():
    Tela.delete("Punti", "Linee")
    if len(ListaPunti) < 1:
        ListaPunti.append(dict(PuntoFisso))
    for Segmento in Segmenti():
        if Segmento["Arco"]:
            Tela.create_line(*PuntiArco(Segmento["Da"], Segmento["Arco"]), fill="black", tags="Linee")
        else:
            Tela.create_line(InPixel(Segmento["Da"]["X"]), InPixel(Segmento["Da"]["Y"]), InPixel(Segmento["A"]["X"]), InPixel(Segmento["A"]["Y"]), fill="black", tags="Linee")
    for Punto in ListaPunti:
        X1 = InPixel(Punto["X"])
        Y1 = InPixel(Punto["Y"])
        Tela.create_oval(X1-Raggio, Y1-Raggio, X1+Raggio, Y1+Raggio, fill=ColoriTipi[Punto["Tipo"]], outline="black", tags="Punti")

def Esporta():
    with open("Output.txt", "w") as File:
        for Segmento in Segmenti():
            Punto = Segmento["A"]
            if Segmento["Arco"]:
                RaggioArco, Angolo, _ = Segmento["Arco"]
                File.write(f"C {round(RaggioArco)} {round(Angolo)}\n")
            else:
                if abs(Segmento["Dopo"] - Segmento["Prima"]) >= 0.5:
                    File.write(f"G {round(Segmento['Dopo'])}\n")
                Distanza = Distance(Segmento["Da"], Punto)
                if Punto["Tipo"] == INDIETRO:
                    Distanza = -Distanza
                File.write(f"A {round(Distanza)}\n")
            if Punto["Tipo"] == MOTORE:
                File.write(f"M {Punto['Target']} {Punto['Gradi']}\n")

def Salva():
    with open(IndirizzoPunti, "w") as File:
        json.dump(ListaPunti, File, indent=4)

def Apri():
    with open(IndirizzoPunti, "r") as File:
        Punti = json.load(File)
    # Il vecchio formato era una lista di [X, Y, Tipo] in pixel
    Punti = [Punto if isinstance(Punto, dict) else NuovoPunto(InMm(Punto[0]), InMm(Punto[1]), Punto[2]) for Punto in Punti]
    SalvaStato()
    ListaPunti[:] = Punti
    Aggiorna()

def Cancella():
    SalvaStato()
    ListaPunti.clear()
    Aggiorna()

def MovimentoCursore(event):
    Tela.coords(CursoreScalatoTkinterMouse, event.x, event.y)
    Tela.delete("Anteprima")
    if ModalitaCenter or Trascinato is not None or not ListaPunti:
        return

    # Anteprima del prossimo tratto con lunghezza e angolo
    Ultimo = ListaPunti[-1]
    X = InMm(event.x)
    Y = InMm(event.y)
    Curva = event.state & CTRL
    if event.state & SHIFT and not Curva:
        X, Y = Snap(X, Y)
    Arrivo = {"X": X, "Y": Y}
    Direzione = DirezioneFinale()
    DatiArco = Arco(Ultimo, Arrivo, Direzione) if Curva else None
    if DatiArco:
        Tela.create_line(*PuntiArco(Ultimo, DatiArco), fill="gray20", dash=(4, 4), tags="Anteprima")
        Testo = f"R {round(DatiArco[0])} mm  {round(DatiArco[1])}°"
    else:
        Tela.create_line(InPixel(Ultimo["X"]), InPixel(Ultimo["Y"]), InPixel(X), InPixel(Y), fill="gray20", dash=(4, 4), tags="Anteprima")
        Testo = f"{round(Distance(Ultimo, Arrivo))} mm  {round(Vicino(Angle(Ultimo, Arrivo), Direzione))}°"
    Etichetta = Tela.create_text(event.x + 15, event.y - 15, text=Testo, anchor="w", font=("TkDefaultFont", 10, "bold"), tags="Anteprima")
    X1, Y1, X2, Y2 = Tela.bbox(Etichetta)
    Sfondo = Tela.create_rectangle(X1-3, Y1-2, X2+3, Y2+2, fill="white", outline="black", tags="Anteprima")
    Tela.tag_raise(Etichetta, Sfondo)

Rotellina = 0

def MovimentoRotellinaSu(event):
    global Rotellina
    Rotellina = (Rotellina + 2) % 360
    ImpostaImmagine(Rotellina)

def MovimentoRotellinaGiu(event):
    global Rotellina
    Rotellina = (Rotellina - 2) % 360
    ImpostaImmagine(Rotellina)

def MovimentoRotellina(event):
    if event.delta > 0:
        MovimentoRotellinaSu(event)
    else:
        MovimentoRotellinaGiu(event)

CacheCursore = {}

def ImpostaImmagine(Gradi):
    # Ruota il cursore al volo e tiene in memoria le immagini gia' create
    if Gradi not in CacheCursore:
        CacheCursore[Gradi] = ImageTk.PhotoImage(ImmagineCursoreScalato.rotate(Gradi, expand=True))
    Tela.itemconfig(CursoreScalatoTkinterMouse, image=CacheCursore[Gradi])

Finestra = tkinter.Tk()
Finestra.title("Line-To-Code")

for Colonna in range(7):
    Finestra.columnconfigure(Colonna, weight=1)

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
BottoneAnnulla = tkinter.Button(Finestra, text="Annulla", command=Annulla, padx=20, pady=20, anchor=tkinter.N)
BottoneAnnulla.grid(row=0, column=4, sticky="nsew")
BottoneCenter = tkinter.Button(Finestra, text="Center", command=Center, padx=20, pady=20, anchor=tkinter.N)
BottoneCenter.grid(row=0, column=5, sticky="nsew")
BottoneExit = tkinter.Button(Finestra, text="Exit", command=Finestra.destroy, padx=20, pady=20, anchor=tkinter.N)
BottoneExit.grid(row=0, column=6, sticky="nsew")

Tela = tkinter.Canvas(Finestra, width=LarghezzaImmagine_px, height=AltezzaImmagine_px)
Tela.grid(row=1, column=0, columnspan=7)

Aiuto = tkinter.Label(Finestra, text="Sinistro: punto (Shift = 0/45/90°, Ctrl = curva) · Trascina: sposta · Click su punto: avanti/indietro (Ctrl: curva) · Centrale: motore · Destro: elimina · Rotella: ruota robot · Ctrl+Z: annulla")
Aiuto.grid(row=2, column=0, columnspan=7, sticky="w", padx=5, pady=3)

Tela.bind("<ButtonPress-1>", PremiS)
Tela.bind("<B1-Motion>", TrascinaS)
Tela.bind("<ButtonRelease-1>", RilasciaS)
Tela.bind("<Button-2>", ClickC)
Tela.bind("<Button-3>", ClickD)
Tela.bind("<Motion>", MovimentoCursore)
Tela.bind("<Button-4>", MovimentoRotellinaSu)
Tela.bind("<Button-5>", MovimentoRotellinaGiu)
Tela.bind("<MouseWheel>", MovimentoRotellina)
Finestra.bind("<Control-z>", Annulla)
Finestra.bind("<Control-Z>", Annulla)

TappetoGara = Image.open(ImmagineTappeto)
TappetoGaraScalato = TappetoGara.resize((LarghezzaImmagine_px, AltezzaImmagine_px))
TappetoGaraScalatoTkinter = ImageTk.PhotoImage(TappetoGaraScalato)
Tappeto = Tela.create_image(0, 0, anchor=tkinter.NW, image=TappetoGaraScalatoTkinter, tags="Tappeto")

ImmagineCursore = Image.open(IndirizzoImmagineCursore).convert("RGBA")
DimensioniRobotPixel = (round(DimensioniRobot[0]*PPM), round(DimensioniRobot[1]*PPM))
ImmagineCursoreScalato = ImmagineCursore.resize(DimensioniRobotPixel)
CursoreScalatoTkinterMouse = Tela.create_image(LarghezzaImmagine_px/2, AltezzaImmagine_px/2, anchor="center", tags="Mouse")
ImpostaImmagine(Rotellina)

Aggiorna()
Finestra.mainloop()
