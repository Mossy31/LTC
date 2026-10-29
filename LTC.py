#--------------------------------------#

# IndietroRobot
# CodiceBlocchi

#--------------------------------------#

from PIL import ImageTk
from PIL import Image
import screeninfo
import tkinter.messagebox
import subprocess
import tempfile
import tkinter
import shutil
import sys
import os
import copy
import math
import json

SogliaRimozionePunti = 10
SogliaTrascinamento = 3
Raggio = 5
PassoSnap = 45
RaggioMassimoCurva = 5000
ListaPunti = []
StoriaAnnulla = []
ImmagineTappeto = "Mappa.png"
IndirizzoImmagineCursore = "Cursore.png"
IndirizzoConfig = "Config.json"
IndirizzoPunti = "Punti.txt"
IndirizzoProgrammaHub = "Pybricks/Esegui.py"
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
        else:
            Gradi = Angle(Precedente, Punto)
            if Punto["Tipo"] == INDIETRO:
                Gradi += 180
            Direzione = Vicino(Gradi, Direzione)
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

def Istruzioni():
    Righe = []
    for Segmento in Segmenti():
        Punto = Segmento["A"]
        if abs(Segmento["Inizio"] - Segmento["Prima"]) >= 0.5:
            # Il robot azzera l'angolo alla partenza: gli angoli sono relativi all'orientamento iniziale
            Righe.append(f"G {round(Segmento['Inizio'] - Orientamento())}")
        if Segmento["Arco"]:
            RaggioArco, Angolo, _, _ = Segmento["Arco"]
            Righe.append(f"C {round(RaggioArco)} {round(Angolo)}")
        else:
            Distanza = Distance(Segmento["Da"], Punto)
            if Punto["Tipo"] == INDIETRO:
                Distanza = -Distanza
            Righe.append(f"A {round(Distanza)}")
        if Punto["Tipo"] == MOTORE:
            Righe.append(f"M {Punto['Target']} {Punto['Gradi']}")
    return "".join(Riga + "\n" for Riga in Righe)

def Esporta():
    with open("Output.txt", "w") as File:
        File.write(Istruzioni())

#--------------------------------------#
# Run: carica il percorso sull'hub via Bluetooth con pybricksdev e lo avvia

ProcessoHub = None

def ComandoPybricksdev():
    if shutil.which("pybricksdev"):
        return ["pybricksdev"]
    try:
        import pybricksdev
        return [sys.executable, "-m", "pybricksdev"]
    except ImportError:
        return None

def Run():
    global ProcessoHub, FileProgramma, FileLog
    if ProcessoHub is not None:
        return
    Comando = ComandoPybricksdev()
    if Comando is None:
        tkinter.messagebox.showerror("Run", "pybricksdev non e' installato.\nInstallalo con: pip install pybricksdev")
        return
    Esporta()
    with open(IndirizzoProgrammaHub, "r") as File:
        Programma = File.read()
    Programma = Programma.replace('PERCORSO = ""', f'PERCORSO = """\n{Istruzioni()}"""', 1)
    FileProgramma = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False)
    FileProgramma.write(Programma)
    FileProgramma.close()
    FileLog = tempfile.TemporaryFile("w+")
    Comando += ["run", "ble"]
    if NomeHub:
        Comando += ["--name", NomeHub]
    ProcessoHub = subprocess.Popen(Comando + [FileProgramma.name], stdout=FileLog, stderr=subprocess.STDOUT)
    BottoneRun.config(text="Run...", state=tkinter.DISABLED)
    Finestra.after(200, ControllaRun)

def ControllaRun():
    # Il processo resta aperto finche' il programma gira sull'hub
    global ProcessoHub
    Codice = ProcessoHub.poll()
    if Codice is None:
        Finestra.after(200, ControllaRun)
        return
    ProcessoHub = None
    BottoneRun.config(text="Run", state=tkinter.NORMAL)
    os.remove(FileProgramma.name)
    FileLog.seek(0)
    Uscita = FileLog.read().strip()
    FileLog.close()
    if Codice != 0:
        tkinter.messagebox.showerror("Run", f"Errore durante il caricamento sull'hub:\n\n{Uscita[-1500:]}")

def Salva():
    with open(IndirizzoPunti, "w") as File:
        json.dump(ListaPunti, File, indent=4)

def Apri():
    with open(IndirizzoPunti, "r") as File:
        Punti = json.load(File)
    # Il vecchio formato era una lista di [X, Y, Tipo] in pixel
    Punti = [Punto if isinstance(Punto, dict) else NuovoPunto(Punto[0] / PPMVecchiFile, Punto[1] / PPMVecchiFile, Punto[2]) for Punto in Punti]
    SalvaStato()
    ListaPunti[:] = Punti
    AnnullaCurva()

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
        Testo = f"R {round(DatiArco[0])} mm  {round(DatiArco[1])}°"
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

for Colonna in range(8):
    Finestra.columnconfigure(Colonna, weight=1)

Finestra.rowconfigure(1, weight=1)

# Parte a tutto schermo, la mappa si adatta allo spazio libero
try:
    Finestra.attributes("-zoomed", True)
except tkinter.TclError:
    Finestra.state("zoomed")

BottoneEsporta = tkinter.Button(Finestra, text="Esporta", command=Esporta, padx=10, pady=4)
BottoneEsporta.grid(row=0, column=0, sticky="nsew")
BottoneSalva = tkinter.Button(Finestra, text="Salva", command=Salva, padx=10, pady=4)
BottoneSalva.grid(row=0, column=1, sticky="nsew")
BottoneApri = tkinter.Button(Finestra, text="Apri", command=Apri, padx=10, pady=4)
BottoneApri.grid(row=0, column=2, sticky="nsew")
BottoneCancella = tkinter.Button(Finestra, text="Cancella", command=Cancella, padx=10, pady=4)
BottoneCancella.grid(row=0, column=3, sticky="nsew")
BottoneAnnulla = tkinter.Button(Finestra, text="Annulla", command=Annulla, padx=10, pady=4)
BottoneAnnulla.grid(row=0, column=4, sticky="nsew")
BottoneCenter = tkinter.Button(Finestra, text="Center", command=Center, padx=10, pady=4)
BottoneCenter.grid(row=0, column=5, sticky="nsew")
BottoneRun = tkinter.Button(Finestra, text="Run", command=Run, padx=10, pady=4)
BottoneRun.grid(row=0, column=6, sticky="nsew")
BottoneExit = tkinter.Button(Finestra, text="Exit", command=Finestra.destroy, padx=10, pady=4)
BottoneExit.grid(row=0, column=7, sticky="nsew")

Area = tkinter.Frame(Finestra)
Area.grid(row=1, column=0, columnspan=8, sticky="nsew")
Tela = tkinter.Canvas(Area, width=LarghezzaImmagine_px // 2, height=AltezzaImmagine_px // 2, highlightthickness=0)
Tela.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)

Aiuto = tkinter.Label(Finestra, justify=tkinter.LEFT, anchor="w", font=("TkDefaultFont", 9), text="Sinistro: punto (Shift = 0/45/90°) · Ctrl+click: passaggio curva, poi click: arrivo (Esc annulla) · Trascina: sposta · Click su punto: avanti/indietro (Ctrl: curva) · Centrale: motore · Destro: elimina (sul punto di partenza: orientamento) · Rotella: ruota robot · Ctrl+Z: annulla")
Aiuto.grid(row=2, column=0, columnspan=8, sticky="ew", padx=5, pady=2)
Aiuto.bind("<Configure>", lambda event: Aiuto.config(wraplength=event.width - 10))

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
Finestra.mainloop()
