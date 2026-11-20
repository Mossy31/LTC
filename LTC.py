#--------------------------------------#

# IndietroRobot
# CodiceBlocchi

#--------------------------------------#

from PIL import ImageTk
from PIL import Image
import screeninfo
import tkinter.messagebox
import tkinter.filedialog
import datetime
import zipfile
import subprocess
import threading
import tempfile
import asyncio
import time
import tkinter
import os
import copy
import math
import json
import shutil
import sys

# Nell'eseguibile (PyInstaller) immagini e programma dell'hub stanno nella cartella del pacchetto,
# mentre Config.json, Punti.txt, Output.txt e Backup/ stanno accanto all'eseguibile
if getattr(sys, "frozen", False):
    CartellaRisorse = sys._MEIPASS
    os.chdir(os.path.dirname(sys.executable))
    if not os.path.exists("Config.json"):
        shutil.copy(os.path.join(CartellaRisorse, "Config.json"), "Config.json")
else:
    CartellaRisorse = "."

if sys.platform == "win32":
    # Senza questo Windows ingrandisce la finestra sfocandola
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass

SogliaRimozionePunti = 10
SogliaTrascinamento = 3
Raggio = 5
PassoSnap = 45
RaggioMassimoCurva = 5000
ListaPunti = []
StoriaAnnulla = []
ImmagineTappeto = os.path.join(CartellaRisorse, "Mappa.png")
IndirizzoImmagineCursore = os.path.join(CartellaRisorse, "Cursore.png")
IndirizzoConfig = "Config.json"
IndirizzoPunti = "Punti.txt"
IndirizzoProgrammaHub = os.path.join(CartellaRisorse, "Pybricks", "Esegui.py")
CartellaBackup = "Backup"
# Nome Bluetooth dell'hub, None = il primo hub Pybricks trovato
NomeHub = None
ModalitaCenter = False

# Tipi di punto
AVANTI = 0
INDIETRO = 1
MOTORE = 2
CURVA = 3
ColoriTipi = {AVANTI: "red", INDIETRO: "yellow", MOTORE: "blue", CURVA: "green"}

# Direzione del robot alla partenza (gradi in senso orario dall'alto della mappa)
Orientamenti = [("Su (0°)", 0), ("Destra (+90°)", 90), ("Giu' / indietro (180°)", 180), ("Sinistra (-90°)", -90)]

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
# Alcuni schermi (spesso su Windows) non dicono quanto sono grandi: si stimano 96 pixel per pollice
AltezzaSchermo_mm = Schermo.height_mm or Schermo.height * 25.4 / 96
LarghezzaSchermo_mm = Schermo.width_mm or Schermo.width * 25.4 / 96

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

# Scala usata dai vecchi file salvati in pixel; poi PPM segue la grandezza della finestra
PPMVecchiFile = PPM

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
        return NuovoPunto(Punto[0] / PPMVecchiFile, Punto[1] / PPMVecchiFile)
    Nuovo = NuovoPunto(Punto["X"], Punto["Y"])
    Nuovo["Orientamento"] = Punto.get("Orientamento", 0)
    return Nuovo

def SalvaConfig(Punto):
    with open(IndirizzoConfig, "w") as File:
        json.dump({"PuntoFisso": {"X": round(Punto["X"], 1), "Y": round(Punto["Y"], 1), "Orientamento": Punto.get("Orientamento", 0)}}, File, indent=4)

def Orientamento():
    # Sta sul punto di partenza, cosi' viene salvato e annullato insieme al percorso
    return ListaPunti[0].get("Orientamento", 0) if ListaPunti else PuntoFisso.get("Orientamento", 0)

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

def Arco(A, M, B):
    # Arco di cerchio che parte da A, passa per M e finisce in B
    # Ritorna (Raggio, Angolo, Centro, Direzione iniziale) oppure None se i punti sono in linea
    D = 2 * (A["X"] * (M["Y"] - B["Y"]) + M["X"] * (B["Y"] - A["Y"]) + B["X"] * (A["Y"] - M["Y"]))
    if abs(D) < 1e-6:
        return None
    QA = A["X"]**2 + A["Y"]**2
    QM = M["X"]**2 + M["Y"]**2
    QB = B["X"]**2 + B["Y"]**2
    Cx = (QA * (M["Y"] - B["Y"]) + QM * (B["Y"] - A["Y"]) + QB * (A["Y"] - M["Y"])) / D
    Cy = (QA * (B["X"] - M["X"]) + QM * (A["X"] - B["X"]) + QB * (M["X"] - A["X"])) / D
    Rx = A["X"] - Cx
    Ry = A["Y"] - Cy
    RaggioArco = math.hypot(Rx, Ry)
    if RaggioArco > RaggioMassimoCurva:
        return None

    Orario = (M["X"] - A["X"]) * (B["Y"] - M["Y"]) - (M["Y"] - A["Y"]) * (B["X"] - M["X"]) > 0
    AngoloA = math.atan2(Ry, Rx)
    AngoloB = math.atan2(B["Y"] - Cy, B["X"] - Cx)
    if Orario:
        Angolo = (AngoloB - AngoloA) % (2 * math.pi)
        Vx, Vy = -Ry, Rx
    else:
        Angolo = -((AngoloA - AngoloB) % (2 * math.pi))
        Vx, Vy = Ry, -Rx
    Tangente = math.degrees(math.atan2(Vx, -Vy))
    return RaggioArco, math.degrees(Angolo), (Cx, Cy), Tangente

def PuntiArco(Da, DatiArco):
    _, Angolo, Centro, _ = DatiArco
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

def PassaggioPredefinito(A, B):
    # A meta' strada, spostato di lato di un quarto della lunghezza
    return {"X": (A["X"] + B["X"]) / 2 + (B["Y"] - A["Y"]) / 4, "Y": (A["Y"] + B["Y"]) / 2 - (B["X"] - A["X"]) / 4}

def Segmenti():
    # Percorre la lista tenendo traccia della direzione del robot sulla mappa
    Direzione = Orientamento()
    Risultato = []
    for Precedente, Punto in zip(ListaPunti, ListaPunti[1:]):
        Prima = Direzione
        DatiArco = None
        if Punto["Tipo"] == CURVA and "Passaggio" in Punto:
            DatiArco = Arco(Precedente, Punto["Passaggio"], Punto)
        if DatiArco:
            Inizio = Vicino(DatiArco[3], Direzione)
            Direzione = Inizio + DatiArco[1]
        elif Distance(Precedente, Punto) >= 0.5:
            Gradi = Angle(Precedente, Punto)
            if Punto["Tipo"] == INDIETRO:
                Gradi += 180
            Direzione = Vicino(Gradi, Direzione)
            Inizio = Direzione
        else:
            # Punto sopra il precedente (es. motore subito dopo una curva): il robot non gira
            Inizio = Direzione
        Risultato.append({"Da": Precedente, "A": Punto, "Prima": Prima, "Inizio": Inizio, "Dopo": Direzione, "Arco": DatiArco})
    return Risultato

def DirezioneFinale():
    Lista = Segmenti()
    return Lista[-1]["Dopo"] if Lista else Orientamento()

def Snap(X, Y):
    # Blocca la linea a multipli di PassoSnap gradi rispetto all'ultimo punto
    Ultimo = ListaPunti[-1]
    Arrivo = {"X": X, "Y": Y}
    Gradi = math.radians(round(Angle(Ultimo, Arrivo) / PassoSnap) * PassoSnap)
    Distanza = Distance(Ultimo, Arrivo)
    return Ultimo["X"] + Distanza * math.sin(Gradi), Ultimo["Y"] - Distanza * math.cos(Gradi)

def Vicinissimo(Punto, X, Y):
    return abs(InPixel(Punto["X"]) - X) <= SogliaRimozionePunti and abs(InPixel(Punto["Y"]) - Y) <= SogliaRimozionePunti

def TrovaPunto(X, Y):
    # Ritorna un punto o un punto di passaggio di una curva (il punto di partenza si cambia solo con Center)
    for Punto in reversed(ListaPunti):
        if Punto is ListaPunti[0]:
            continue
        if "Passaggio" in Punto and Vicinissimo(Punto["Passaggio"], X, Y):
            return Punto["Passaggio"]
        if Vicinissimo(Punto, X, Y):
            return Punto
    return None

def Indice(Punto):
    return next(I for I, Altro in enumerate(ListaPunti) if Altro is Punto)

#--------------------------------------#
# Annulla

def SalvaStato():
    StoriaAnnulla.append(copy.deepcopy(ListaPunti))
    if len(StoriaAnnulla) > 100:
        StoriaAnnulla.pop(0)

def Annulla(event=None):
    global PassaggioInSospeso
    PassaggioInSospeso = None
    if StoriaAnnulla:
        ListaPunti[:] = StoriaAnnulla.pop()
    Aggiorna()

def AnnullaCurva(event=None):
    global PassaggioInSospeso
    PassaggioInSospeso = None
    Aggiorna()

#--------------------------------------#
# Mouse

Trascinato = None
Spostato = False
InizioTrascinamento = (0, 0)
PassaggioInSospeso = None

def PremiS(event):
    global PuntoFisso, ModalitaCenter, Trascinato, Spostato, InizioTrascinamento, PassaggioInSospeso
    X = InMm(event.x)
    Y = InMm(event.y)

    if ModalitaCenter:
        SalvaStato()
        PuntoFisso = NuovoPunto(X, Y)
        PuntoFisso["Orientamento"] = Orientamento()
        ListaPunti[0] = dict(PuntoFisso)
        SalvaConfig(PuntoFisso)
        Center()
        Aggiorna()
        return

    if PassaggioInSospeso is not None:
        # Secondo click della curva: punto di arrivo
        SalvaStato()
        Punto = NuovoPunto(X, Y, CURVA)
        Punto["Passaggio"] = PassaggioInSospeso
        PassaggioInSospeso = None
        ListaPunti.append(Punto)
        Aggiorna()
        return

    Trascinato = TrovaPunto(event.x, event.y)
    Spostato = False
    InizioTrascinamento = (event.x, event.y)
    if Trascinato is not None:
        SalvaStato()
    elif event.state & CTRL:
        # Primo click della curva: punto di passaggio
        PassaggioInSospeso = {"X": X, "Y": Y}
        Aggiorna()
    else:
        if event.state & SHIFT:
            X, Y = Snap(X, Y)
        SalvaStato()
        ListaPunti.append(NuovoPunto(X, Y))
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
        # Click senza trascinare: cambia tipo al punto (i punti di passaggio non hanno un tipo)
        Tipo = Trascinato.get("Tipo")
        if event.state & CTRL:
            if Tipo == CURVA:
                Trascinato["Tipo"] = AVANTI
                Trascinato.pop("Passaggio", None)
            elif Tipo in (AVANTI, INDIETRO) and Indice(Trascinato) > 0:
                Trascinato["Tipo"] = CURVA
                Trascinato["Passaggio"] = PassaggioPredefinito(ListaPunti[Indice(Trascinato) - 1], Trascinato)
        elif Tipo == AVANTI:
            Trascinato["Tipo"] = INDIETRO
        elif Tipo == INDIETRO:
            Trascinato["Tipo"] = AVANTI
        Aggiorna()
    Trascinato = None

def ClickC(event):
    Punto = TrovaPunto(event.x, event.y)
    if Punto is not None and "Tipo" not in Punto:
        return
    Nuovo = Punto is None
    if Nuovo:
        Punto = NuovoPunto(InMm(event.x), InMm(event.y), MOTORE)
    Valori = ChiediParametriMotore(Punto.get("Target", 0), Punto.get("Gradi", 0))
    if Valori is None:
        return
    SalvaStato()
    Punto["Tipo"] = MOTORE
    Punto["Target"], Punto["Gradi"] = Valori
    Punto.pop("Passaggio", None)
    if Nuovo:
        ListaPunti.append(Punto)
    Aggiorna()

def ClickD(event):
    Punto = TrovaPunto(event.x, event.y)
    if Punto is None:
        if ListaPunti and Vicinissimo(ListaPunti[0], event.x, event.y):
            MenuOrientamento(event)
        return
    SalvaStato()
    Proprietario = next((Altro for Altro in ListaPunti if Altro.get("Passaggio") is Punto), None)
    if Proprietario is not None:
        # Eliminare il punto di passaggio trasforma la curva in una linea
        Proprietario["Tipo"] = AVANTI
        del Proprietario["Passaggio"]
    else:
        ListaPunti[:] = [Altro for Altro in ListaPunti if Altro is not Punto]
    Aggiorna()

def MenuOrientamento(event):
    Menu = tkinter.Menu(Finestra, tearoff=0)
    Scelta = tkinter.IntVar(Menu, value=Orientamento())
    for Testo, Gradi in Orientamenti:
        Menu.add_radiobutton(label=Testo, variable=Scelta, value=Gradi, command=lambda Gradi=Gradi: ImpostaOrientamento(Gradi))
    Menu.tk_popup(event.x_root, event.y_root)

def ImpostaOrientamento(Gradi):
    global Rotellina
    if Gradi == Orientamento():
        return
    SalvaStato()
    ListaPunti[0]["Orientamento"] = Gradi
    PuntoFisso["Orientamento"] = Gradi
    SalvaConfig(PuntoFisso)
    # Il cursore parte girato come il robot
    Rotellina = -Gradi % 360
    ImpostaImmagine(Rotellina)
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
            Valori = [int(CampoTarget.get()), int(CampoGradi.get())]
        except ValueError:
            return
        if not 1 <= Valori[0] <= 4:
            return
        Risultato.extend(Valori)
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

def DisegnaPassaggio(Punto):
    X1 = InPixel(Punto["X"])
    Y1 = InPixel(Punto["Y"])
    Tela.create_oval(X1-Raggio, Y1-Raggio, X1+Raggio, Y1+Raggio, fill="white", outline="green", width=2, tags="Punti")

def Aggiorna():
    Tela.delete("Punti", "Linee")
    if len(ListaPunti) < 1:
        ListaPunti.append(dict(PuntoFisso))
    for Segmento in Segmenti():
        if Segmento["Arco"]:
            Tela.create_line(*PuntiArco(Segmento["Da"], Segmento["Arco"]), fill="black", tags="Linee")
        else:
            Tela.create_line(InPixel(Segmento["Da"]["X"]), InPixel(Segmento["Da"]["Y"]), InPixel(Segmento["A"]["X"]), InPixel(Segmento["A"]["Y"]), fill="black", tags="Linee")
    # Freccia che mostra come parte il robot
    Partenza = ListaPunti[0]
    Gradi = math.radians(Orientamento())
    Tela.create_line(InPixel(Partenza["X"]), InPixel(Partenza["Y"]), InPixel(Partenza["X"]) + 25 * math.sin(Gradi), InPixel(Partenza["Y"]) - 25 * math.cos(Gradi), arrow=tkinter.LAST, width=2, fill="black", tags="Linee")
    for Punto in ListaPunti:
        X1 = InPixel(Punto["X"])
        Y1 = InPixel(Punto["Y"])
        Tela.create_oval(X1-Raggio, Y1-Raggio, X1+Raggio, Y1+Raggio, fill=ColoriTipi[Punto["Tipo"]], outline="black", tags="Punti")
        if "Passaggio" in Punto:
            DisegnaPassaggio(Punto["Passaggio"])
    if PassaggioInSospeso is not None:
        DisegnaPassaggio(PassaggioInSospeso)
    AggiornaTesto()

def Istruzioni():
    Righe = []
    for Segmento in Segmenti():
        Punto = Segmento["A"]
        if abs(Segmento["Inizio"] - Segmento["Prima"]) >= 0.5:
            # Il robot azzera l'angolo alla partenza: gli angoli sono relativi all'orientamento iniziale
            Righe.append(f"G {round(Segmento['Inizio'] - Orientamento())}")
        if Segmento["Arco"]:
            RaggioArco, Angolo, _, _ = Segmento["Arco"]
            # Pybricks arc(): raggio positivo = curva a destra, negativo = a sinistra;
            # un angolo negativo vorrebbe dire retromarcia, quindi resta sempre positivo
            Righe.append(f"C {round(RaggioArco) if Angolo > 0 else -round(RaggioArco)} {round(abs(Angolo))}")
        else:
            Distanza = Distance(Segmento["Da"], Punto)
            if Punto["Tipo"] == INDIETRO:
                Distanza = -Distanza
            if round(Distanza) != 0:
                Righe.append(f"A {round(Distanza)}")
        if Punto["Tipo"] == MOTORE:
            Righe.append(f"M {Punto['Target']} {Punto['Gradi']}")
    return "".join(Riga + "\n" for Riga in Righe)

def Esporta():
    with open("Output.txt", "w") as File:
        File.write(Istruzioni())
    AggiornaTesto(True)

#--------------------------------------#
# Editor a destra: le stesse istruzioni di Esporta (mm e gradi), modificabili.
# Cambiando un valore il percorso sulla mappa viene ricostruito da capo.

# Lettera: (numero di valori, descrizione per gli errori)
FormatoIstruzioni = {"A": (1, "A mm"), "G": (1, "G gradi"), "C": (2, "C raggio gradi"), "M": (2, "M target gradi")}
TestoMostrato = ""
ModificaDaTesto = False
StatoSalvatoTesto = False

def AggiornaTesto(Forza=False):
    # Riscrive l'editor col percorso della mappa, ma non mentre lo si sta modificando
    global TestoMostrato
    if ModificaDaTesto and not Forza:
        return
    Nuovo = Istruzioni()
    if Nuovo == Editor.get("1.0", "end-1c"):
        TestoMostrato = Nuovo
        return
    Cursore = Editor.index(tkinter.INSERT)
    Vista = Editor.yview()[0]
    Editor.delete("1.0", tkinter.END)
    Editor.insert("1.0", Nuovo)
    Editor.mark_set(tkinter.INSERT, Cursore)
    Editor.yview_moveto(Vista)
    Editor.tag_remove("Errore", "1.0", tkinter.END)
    StatoEditor.config(text="", fg="black")
    TestoMostrato = Nuovo

def LeggiIstruzioni(Testo):
    # Ritorna (lista di (lettera, valori), None) oppure (None, (numero riga, errore))
    Righe = []
    for Numero, Riga in enumerate(Testo.split("\n"), 1):
        Parti = Riga.split()
        if not Parti:
            continue
        Lettera = Parti[0].upper()
        if Lettera not in FormatoIstruzioni:
            return None, (Numero, f"'{Parti[0]}' non e' A, G, C o M")
        Quanti, Formato = FormatoIstruzioni[Lettera]
        try:
            Valori = [int(Valore) for Valore in Parti[1:]]
        except ValueError:
            return None, (Numero, f"servono numeri interi: {Formato}")
        if len(Valori) != Quanti:
            return None, (Numero, f"formato: {Formato}")
        if Lettera == "C" and not (0 < abs(Valori[0]) <= RaggioMassimoCurva and 0 < Valori[1] < 360):
            return None, (Numero, f"raggio da 1 a {RaggioMassimoCurva} (negativo = sinistra), gradi da 1 a 359")
        if Lettera == "M" and not 1 <= Valori[0] <= 4:
            return None, (Numero, "target da 1 a 4: M target gradi")
        Righe.append((Lettera, Valori))
    return Righe, None

def PuntiDaIstruzioni(Righe):
    # Rifa' il percorso del robot dal punto di partenza (mm, Y verso il basso, gradi orari dall'alto)
    Partenza = ListaPunti[0]
    X, Y = Partenza["X"], Partenza["Y"]
    Direzione = Orientamento()
    Punti = [Partenza]
    for Lettera, Valori in Righe:
        if Lettera == "G":
            Direzione = Valori[0] + Orientamento()
        elif Lettera == "A":
            Radianti = math.radians(Direzione)
            X += Valori[0] * math.sin(Radianti)
            Y -= Valori[0] * math.cos(Radianti)
            Punti.append(NuovoPunto(X, Y, INDIETRO if Valori[0] < 0 else AVANTI))
        elif Lettera == "C":
            # Il centro sta a destra del robot se il raggio e' positivo, a sinistra se negativo
            Radianti = math.radians(Direzione)
            Cx = X + Valori[0] * math.cos(Radianti)
            Cy = Y + Valori[0] * math.sin(Radianti)
            Angolo = Valori[1] if Valori[0] > 0 else -Valori[1]
            def Ruota(Gradi):
                T = math.radians(Gradi)
                return {"X": Cx + (X - Cx) * math.cos(T) - (Y - Cy) * math.sin(T), "Y": Cy + (X - Cx) * math.sin(T) + (Y - Cy) * math.cos(T)}
            Punto = NuovoPunto(**Ruota(Angolo), Tipo=CURVA)
            Punto["Passaggio"] = Ruota(Angolo / 2)
            X, Y = Punto["X"], Punto["Y"]
            Direzione += Angolo
            Punti.append(Punto)
        elif Lettera == "M":
            # Un motore subito dopo un tratto in avanti sta su quel punto, altrimenti su un punto nuovo dove si trova il robot
            Ultimo = Punti[-1]
            if Ultimo["Tipo"] != AVANTI or Ultimo is Partenza:
                Ultimo = NuovoPunto(X, Y)
                Punti.append(Ultimo)
            Ultimo["Tipo"] = MOTORE
            Ultimo["Target"], Ultimo["Gradi"] = Valori
    return Punti

def ModificaTesto(event=None):
    global ModificaDaTesto, StatoSalvatoTesto, TestoMostrato
    Testo = Editor.get("1.0", "end-1c")
    if Testo == TestoMostrato:
        return
    TestoMostrato = Testo
    Editor.tag_remove("Errore", "1.0", tkinter.END)
    Righe, Errore = LeggiIstruzioni(Testo)
    if Errore:
        Editor.tag_add("Errore", f"{Errore[0]}.0", f"{Errore[0]}.end")
        StatoEditor.config(text=f"Riga {Errore[0]}: {Errore[1]}", fg="red")
        return
    StatoEditor.config(text="", fg="black")
    # Un solo passo di Annulla per tutta la modifica nell'editor
    if not StatoSalvatoTesto:
        SalvaStato()
        StatoSalvatoTesto = True
    ListaPunti[1:] = PuntiDaIstruzioni(Righe)[1:]
    ModificaDaTesto = True
    Aggiorna()
    ModificaDaTesto = False

def EsciDalTesto(event=None):
    # Uscendo dall'editor si vede il percorso come lo eseguira' il robot
    global StatoSalvatoTesto
    StatoSalvatoTesto = False
    if not Editor.tag_ranges("Errore"):
        AggiornaTesto(True)

#--------------------------------------#
# Run: carica il percorso sull'hub via Bluetooth con pybricksdev e lo avvia.
# La connessione resta aperta in un thread a parte, cosi' si legge anche la batteria.

try:
    import bleak
    from pybricksdev.connections import ConnectionState
    from pybricksdev.connections.pybricks import PybricksHubBLE
    from pybricksdev.ble.pybricks import PYBRICKS_SERVICE_UUID
except ImportError:
    bleak = None

Hub = None
Batteria = None
CicloHub = None
LavoroHub = None
BloccoHub = None

# Soglie del firmware Pybricks per le batterie LEGO ricaricabili (lib/pbio/sys/battery.c), in mV:
# piena 8190, sotto 7200 non e' piu' OK, 6800 avviso batteria bassa, 6000 l'hub si spegne.
# 7,3 V e' la tensione nominale (media), non quella a batteria carica.
BatteriaPiena = 8190
BatteriaOk = 7200
BatteriaBassa = 6800
BatteriaVuota = 6000
IntervalloBatteria = 60

ProgrammaBatteria = """from pybricks.hubs import PrimeHub
print("BATTERIA", PrimeHub().battery.voltage())
"""

def EHub(Dispositivo, Dati):
    return PYBRICKS_SERVICE_UUID in Dati.service_uuids and (NomeHub is None or Dispositivo.name == NomeHub)

def ScollegaHubRimasti():
    # Un hub rimasto collegato (es. a Pybricks Code chiuso male) non si fa piu' trovare
    # bluetoothctl esiste solo su Linux
    if not sys.platform.startswith("linux"):
        return
    try:
        Collegati = subprocess.run(["bluetoothctl", "devices", "Connected"], capture_output=True, text=True, timeout=5).stdout
        for Riga in Collegati.splitlines():
            Parti = Riga.split()
            if len(Parti) < 2 or Parti[0] != "Device":
                continue
            Info = subprocess.run(["bluetoothctl", "info", Parti[1]], capture_output=True, text=True, timeout=5).stdout
            if PYBRICKS_SERVICE_UUID in Info.lower():
                subprocess.run(["bluetoothctl", "disconnect", Parti[1]], capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        pass

async def EseguiSulHub(Indirizzo):
    # Ritorna quello che il programma ha stampato sull'hub
    global Batteria
    async with BloccoHub:
        await Hub.run(Indirizzo, wait=True, print_output=False)
        Uscita = [Riga.decode(errors="replace") for Riga in Hub.output]
    for Riga in Uscita:
        Parti = Riga.split()
        if len(Parti) == 2 and Parti[0] == "BATTERIA":
            Batteria = int(Parti[1])
    return "\n".join(Uscita)

async def GestisciHub():
    # BlueZ 5.87 va in crash se la ricerca Bluetooth e' filtrata per servizio (lo fa anche
    # Pybricks Code): si cerca senza filtro e si riconosce l'hub dai dati che riceve
    global Hub, Batteria, BloccoHub
    BloccoHub = asyncio.Lock()
    with open(FileBatteria, "w") as File:
        File.write(ProgrammaBatteria)
    UltimaLettura = 0
    while True:
        try:
            if Hub is None:
                ScollegaHubRimasti()
                Dispositivo = await bleak.BleakScanner.find_device_by_filter(EHub, timeout=5)
                if Dispositivo is None:
                    continue
                NuovoHub = PybricksHubBLE(Dispositivo)
                await NuovoHub.connect()
                Hub = NuovoHub
                UltimaLettura = 0
            if Hub.connection_state_observable.value != ConnectionState.CONNECTED:
                Hub = None
                Batteria = None
                continue
            if time.monotonic() - UltimaLettura > IntervalloBatteria and not BloccoHub.locked():
                UltimaLettura = time.monotonic()
                await EseguiSulHub(FileBatteria)
        except Exception:
            # bluetoothd riavviato, hub spento a meta' connessione...: si riprova
            if Hub is not None and Hub.connection_state_observable.value != ConnectionState.CONNECTED:
                Hub = None
                Batteria = None
            await asyncio.sleep(3)
        await asyncio.sleep(1)

def AvviaHub():
    global CicloHub, FileBatteria
    if bleak is None:
        return
    FileBatteria = os.path.join(tempfile.gettempdir(), "LTC_Batteria.py")
    CicloHub = asyncio.new_event_loop()
    threading.Thread(target=CicloHub.run_until_complete, args=(GestisciHub(),), daemon=True).start()

def ChiudiHub():
    # Senza disconnettere, BlueZ lascia l'hub collegato anche dopo la chiusura
    if Hub is not None:
        try:
            asyncio.run_coroutine_threadsafe(Hub.disconnect(), CicloHub).result(timeout=5)
        except Exception:
            pass
    Finestra.destroy()

def AggiornaBatteria():
    if Hub is None or Batteria is None:
        EtichettaBatteria.place_forget()
    else:
        # Percentuale lineare tra spegnimento e piena: e' una stima, la tensione e' il dato vero
        Percentuale = max(0, min(100, round((Batteria - BatteriaVuota) * 100 / (BatteriaPiena - BatteriaVuota))))
        Colore = "green" if Batteria >= BatteriaOk else "orange" if Batteria > BatteriaBassa else "red"
        EtichettaBatteria.config(text=f"Batteria {Percentuale}% ({Batteria / 1000:.2f} V)", fg=Colore)
        EtichettaBatteria.place(relx=1, rely=0, x=-10, y=10, anchor="ne")
    Finestra.after(500, AggiornaBatteria)

def Run():
    global LavoroHub, FileProgramma
    if LavoroHub is not None:
        return
    if CicloHub is None:
        tkinter.messagebox.showerror("Run", "pybricksdev non e' installato.\nInstallalo con: pip install pybricksdev")
        return
    if Hub is None:
        tkinter.messagebox.showerror("Run", "Hub non connesso.\n\nDeve essere acceso, con il firmware Pybricks, e non collegato a Pybricks Code o ad altri computer. LTC si collega da solo appena lo trova.")
        return
    Esporta()
    with open(IndirizzoProgrammaHub, "r") as File:
        Programma = File.read()
    Programma = Programma.replace('PERCORSO = ""', f'PERCORSO = """\n{Istruzioni()}"""', 1)
    FileProgramma = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False)
    FileProgramma.write(Programma)
    FileProgramma.close()
    LavoroHub = asyncio.run_coroutine_threadsafe(EseguiSulHub(FileProgramma.name), CicloHub)
    BottoneRun.config(text="Run...", state=tkinter.DISABLED)
    Finestra.after(200, ControllaRun)

def ControllaRun():
    # Il lavoro finisce quando il programma si ferma sull'hub
    global LavoroHub
    if not LavoroHub.done():
        Finestra.after(200, ControllaRun)
        return
    Lavoro = LavoroHub
    LavoroHub = None
    BottoneRun.config(text="Run", state=tkinter.NORMAL)
    os.remove(FileProgramma.name)
    if Lavoro.exception() is not None:
        tkinter.messagebox.showerror("Run", f"Errore durante il caricamento sull'hub:\n\n{Lavoro.exception()!r}")
    elif "Traceback" in Lavoro.result():
        tkinter.messagebox.showerror("Run", f"Errore nel programma sull'hub:\n\n{Lavoro.result()[-1500:]}")

def Salva():
    with open(IndirizzoPunti, "w") as File:
        json.dump(ListaPunti, File, indent=4)

def CaricaPunti(Punti):
    # Il vecchio formato era una lista di [X, Y, Tipo] in pixel
    Punti = [Punto if isinstance(Punto, dict) else NuovoPunto(Punto[0] / PPMVecchiFile, Punto[1] / PPMVecchiFile, Punto[2]) for Punto in Punti]
    SalvaStato()
    ListaPunti[:] = Punti
    AnnullaCurva()

def Apri():
    try:
        with open(IndirizzoPunti, "r") as File:
            Punti = json.load(File)
    except FileNotFoundError:
        tkinter.messagebox.showerror("Apri", f"{IndirizzoPunti} non esiste ancora: prima usa Salva.")
        return
    CaricaPunti(Punti)

def CaricaBackup():
    # Mette sulla mappa il percorso di un backup ZIP; Punti.txt non viene toccato finche' non si usa Salva
    os.makedirs(CartellaBackup, exist_ok=True)
    Indirizzo = tkinter.filedialog.askopenfilename(
        parent=Finestra,
        title="Carica un backup",
        initialdir=CartellaBackup,
        filetypes=[("Archivio ZIP", "*.zip")],
    )
    if not Indirizzo:
        return
    try:
        with zipfile.ZipFile(Indirizzo) as Archivio:
            Punti = json.loads(Archivio.read(os.path.basename(IndirizzoPunti)))
        if not isinstance(Punti, list) or not Punti:
            raise ValueError("percorso vuoto")
    except (zipfile.BadZipFile, KeyError, ValueError, OSError) as Errore:
        tkinter.messagebox.showerror("Carica backup", f"Backup non valido:\n{os.path.basename(Indirizzo)}\n\n{Errore}")
        return
    CaricaPunti(Punti)

def Backup():
    # ZIP col percorso attuale (anche se non salvato); il nome propone data e ora
    os.makedirs(CartellaBackup, exist_ok=True)
    Adesso = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    Indirizzo = tkinter.filedialog.asksaveasfilename(
        parent=Finestra,
        title="Backup del percorso",
        initialdir=CartellaBackup,
        initialfile=f"Backup_{Adesso}.zip",
        defaultextension=".zip",
        filetypes=[("Archivio ZIP", "*.zip")],
    )
    if not Indirizzo:
        return
    with zipfile.ZipFile(Indirizzo, "w", zipfile.ZIP_DEFLATED) as Archivio:
        Archivio.writestr(os.path.basename(IndirizzoPunti), json.dumps(ListaPunti, indent=4))

def Cancella():
    SalvaStato()
    ListaPunti.clear()
    AnnullaCurva()

def MovimentoCursore(event):
    Tela.coords(CursoreScalatoTkinterMouse, event.x, event.y)
    Tela.delete("Anteprima")
    if ModalitaCenter or Trascinato is not None or not ListaPunti:
        return

    # Anteprima del prossimo tratto con lunghezza e angolo
    Ultimo = ListaPunti[-1]
    X = InMm(event.x)
    Y = InMm(event.y)
    if PassaggioInSospeso is None and event.state & SHIFT and not event.state & CTRL:
        X, Y = Snap(X, Y)
    Arrivo = {"X": X, "Y": Y}
    DatiArco = Arco(Ultimo, PassaggioInSospeso, Arrivo) if PassaggioInSospeso is not None else None
    if DatiArco:
        Tela.create_line(*PuntiArco(Ultimo, DatiArco), fill="gray20", dash=(4, 4), tags="Anteprima")
        Testo = f"R {round(DatiArco[0]) if DatiArco[1] > 0 else -round(DatiArco[0])} mm  {round(abs(DatiArco[1]))}°"
    else:
        Tela.create_line(InPixel(Ultimo["X"]), InPixel(Ultimo["Y"]), InPixel(X), InPixel(Y), fill="gray20", dash=(4, 4), tags="Anteprima")
        Testo = f"{round(Distance(Ultimo, Arrivo))} mm  {round(Vicino(Angle(Ultimo, Arrivo), DirezioneFinale()) - Orientamento())}°"
    Etichetta = Tela.create_text(event.x + 15, event.y - 15, text=Testo, anchor="w", font=("TkDefaultFont", 10, "bold"), tags="Anteprima")
    X1, Y1, X2, Y2 = Tela.bbox(Etichetta)
    Sfondo = Tela.create_rectangle(X1-3, Y1-2, X2+3, Y2+2, fill="white", outline="black", tags="Anteprima")
    Tela.tag_raise(Etichetta, Sfondo)

Rotellina = -Orientamento() % 360
UltimoScatto = 0
PassoRotellinaMinimo = 2
PassoRotellinaMassimo = 15
# Sotto questo intervallo (ms) tra due scatti la rotazione accelera
IntervalloRotellinaLento = 60

def PassoRotellina(event):
    # Piu' gli scatti sono ravvicinati, piu' gradi ruota ogni scatto
    global UltimoScatto
    Intervallo = event.time - UltimoScatto
    UltimoScatto = event.time
    if Intervallo <= 0:
        return PassoRotellinaMassimo
    Passo = round(PassoRotellinaMinimo * IntervalloRotellinaLento / Intervallo)
    return max(PassoRotellinaMinimo, min(PassoRotellinaMassimo, Passo))

def MovimentoRotellinaSu(event):
    global Rotellina
    Rotellina = (Rotellina + PassoRotellina(event)) % 360
    ImpostaImmagine(Rotellina)

def MovimentoRotellinaGiu(event):
    global Rotellina
    Rotellina = (Rotellina - PassoRotellina(event)) % 360
    ImpostaImmagine(Rotellina)

def MovimentoRotellina(event):
    if event.delta > 0:
        MovimentoRotellinaSu(event)
    else:
        MovimentoRotellinaGiu(event)

CacheCursore = {}
AttesaRidimensionamento = None
DimensioniTela = (0, 0)

def Ridimensiona(event):
    # Aspetta che l'utente finisca di ridimensionare prima di riscalare le immagini
    global AttesaRidimensionamento
    if AttesaRidimensionamento is not None:
        Finestra.after_cancel(AttesaRidimensionamento)
    AttesaRidimensionamento = Finestra.after(100, ApplicaDimensioni, event.width, event.height)

def ApplicaDimensioni(Larghezza, Altezza):
    global PPM, TappetoGaraScalatoTkinter, ImmagineCursoreScalato, DimensioniTela, AttesaRidimensionamento
    AttesaRidimensionamento = None
    if (Larghezza, Altezza) == DimensioniTela or Larghezza < 10 or Altezza < 10:
        return
    DimensioniTela = (Larghezza, Altezza)
    PPM = min(Larghezza / LarghezzaImmagine_mm, Altezza / AltezzaImmagine_mm)
    # La tela e' grande come la mappa e resta al centro dell'area
    Tela.config(width=round(LarghezzaImmagine_mm * PPM), height=round(AltezzaImmagine_mm * PPM))

    TappetoGaraScalato = TappetoGara.resize((round(LarghezzaImmagine_mm * PPM), round(AltezzaImmagine_mm * PPM)))
    TappetoGaraScalatoTkinter = ImageTk.PhotoImage(TappetoGaraScalato)
    Tela.itemconfig(Tappeto, image=TappetoGaraScalatoTkinter)

    DimensioniRobotPixel = (max(1, round(DimensioniRobot[0]*PPM)), max(1, round(DimensioniRobot[1]*PPM)))
    ImmagineCursoreScalato = ImmagineCursore.resize(DimensioniRobotPixel, Image.NEAREST)
    CacheCursore.clear()
    ImpostaImmagine(Rotellina)
    Aggiorna()

def ImpostaImmagine(Gradi):
    # Ruota il cursore al volo e tiene in memoria le immagini gia' create
    if Gradi not in CacheCursore:
        CacheCursore[Gradi] = ImageTk.PhotoImage(ImmagineCursoreScalato.rotate(Gradi, expand=True))
    Tela.itemconfig(CursoreScalatoTkinterMouse, image=CacheCursore[Gradi])

Finestra = tkinter.Tk()
Finestra.title("Line-To-Code")

for Colonna in range(9):
    Finestra.columnconfigure(Colonna, weight=1)

Finestra.rowconfigure(1, weight=1)

# Parte a tutto schermo, la mappa si adatta allo spazio libero
try:
    Finestra.attributes("-zoomed", True)
except tkinter.TclError:
    Finestra.state("zoomed")

BottoneEsporta = tkinter.Button(Finestra, text="Esporta", command=Esporta, padx=16, pady=8)
BottoneEsporta.grid(row=0, column=0, sticky="nsew", padx=(10, 4), pady=(10, 6))
BottoneSalva = tkinter.Button(Finestra, text="Salva", command=Salva, padx=16, pady=8)
BottoneSalva.grid(row=0, column=1, sticky="nsew", padx=4, pady=(10, 6))
BottoneApri = tkinter.Button(Finestra, text="Apri", command=Apri, padx=16, pady=8)
BottoneApri.grid(row=0, column=2, sticky="nsew", padx=4, pady=(10, 6))
BottoneBackup = tkinter.Menubutton(Finestra, text="Backup ▾", relief=tkinter.RAISED, borderwidth=2, padx=16, pady=8)
MenuBackup = tkinter.Menu(BottoneBackup, tearoff=0)
MenuBackup.add_command(label="Crea backup...", command=Backup)
MenuBackup.add_command(label="Carica backup...", command=CaricaBackup)
BottoneBackup.config(menu=MenuBackup)
BottoneBackup.grid(row=0, column=3, sticky="nsew", padx=4, pady=(10, 6))
BottoneCancella = tkinter.Button(Finestra, text="Cancella", command=Cancella, padx=16, pady=8)
BottoneCancella.grid(row=0, column=4, sticky="nsew", padx=4, pady=(10, 6))
BottoneAnnulla = tkinter.Button(Finestra, text="Annulla", command=Annulla, padx=16, pady=8)
BottoneAnnulla.grid(row=0, column=5, sticky="nsew", padx=4, pady=(10, 6))
BottoneCenter = tkinter.Button(Finestra, text="Center", command=Center, padx=16, pady=8)
BottoneCenter.grid(row=0, column=6, sticky="nsew", padx=4, pady=(10, 6))
BottoneRun = tkinter.Button(Finestra, text="Run", command=Run, padx=16, pady=8)
BottoneRun.grid(row=0, column=7, sticky="nsew", padx=4, pady=(10, 6))
BottoneExit = tkinter.Button(Finestra, text="Exit", command=ChiudiHub, padx=16, pady=8)
BottoneExit.grid(row=0, column=8, sticky="nsew", padx=4, pady=(10, 6))

Area = tkinter.Frame(Finestra)
Area.grid(row=1, column=0, columnspan=9, sticky="nsew", padx=10, pady=(4, 10))
Tela = tkinter.Canvas(Area, width=LarghezzaImmagine_px // 2, height=AltezzaImmagine_px // 2, highlightthickness=0)
Tela.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)
EtichettaBatteria = tkinter.Label(Area, font=("TkDefaultFont", 11, "bold"))

PannelloEditor = tkinter.Frame(Finestra)
PannelloEditor.grid(row=0, column=9, rowspan=2, sticky="nsew", padx=(6, 10), pady=10)
PannelloEditor.rowconfigure(0, weight=1)
Editor = tkinter.Text(PannelloEditor, width=22, font=("TkFixedFont", 12), undo=False, wrap=tkinter.NONE, padx=8, pady=6)
Editor.grid(row=0, column=0, sticky="nsew")
BarraEditor = tkinter.Scrollbar(PannelloEditor, command=Editor.yview)
BarraEditor.grid(row=0, column=1, sticky="ns")
Editor.config(yscrollcommand=BarraEditor.set)
Editor.tag_config("Errore", background="#ffc0c0")
StatoEditor = tkinter.Label(PannelloEditor, justify=tkinter.LEFT, anchor="w", wraplength=200)
StatoEditor.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
Editor.bind("<KeyRelease>", ModificaTesto)
Editor.bind("<FocusOut>", EsciDalTesto)

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
Finestra.bind("<Escape>", AnnullaCurva)
Area.bind("<Configure>", Ridimensiona)

TappetoGara = Image.open(ImmagineTappeto)
Tappeto = Tela.create_image(0, 0, anchor=tkinter.NW, tags="Tappeto")

ImmagineCursore = Image.open(IndirizzoImmagineCursore).convert("RGBA")
CursoreScalatoTkinterMouse = Tela.create_image(LarghezzaImmagine_px/2, AltezzaImmagine_px/2, anchor="center", tags="Mouse")
ApplicaDimensioni(LarghezzaImmagine_px, AltezzaImmagine_px)
Finestra.protocol("WM_DELETE_WINDOW", ChiudiHub)
AvviaHub()
AggiornaBatteria()
Finestra.mainloop()
