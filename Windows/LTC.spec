# PyInstaller: un solo LTC.exe con dentro Python, le librerie, la mappa e il programma dell'hub.
# Config.json, Punti.txt, Output.txt e Backup\ vengono creati accanto all'exe.
import os
from PyInstaller.utils.hooks import collect_all

Radice = os.path.abspath(os.path.join(SPECPATH, ".."))

Dati = [
    (os.path.join(Radice, "Mappa.png"), "."),
    (os.path.join(Radice, "Cursore.png"), "."),
    (os.path.join(Radice, "Config.json"), "."),
    (os.path.join(Radice, "Pybricks", "Esegui.py"), "Pybricks"),
]
Binari = []
# ImageTk lo carica di nascosto, PyInstaller non lo vede
Nascosti = ["PIL._tkinter_finder"]
# pybricksdev compila il programma con mpy-cross (un .exe dentro questi pacchetti),
# bleak usa le librerie winrt di Windows per il Bluetooth
for Pacchetto in ["pybricksdev", "mpy_cross_v5", "mpy_cross_v6", "bleak", "winrt"]:
    D, B, N = collect_all(Pacchetto)
    Dati += D
    Binari += B
    Nascosti += N

a = Analysis(
    [os.path.join(Radice, "LTC.py")],
    pathex=[Radice],
    binaries=Binari,
    datas=Dati,
    hiddenimports=Nascosti,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="LTC",
    console=False,
    upx=False,
)
