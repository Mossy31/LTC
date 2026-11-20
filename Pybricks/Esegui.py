# Programma caricato dal bottone Run di LTC.py: esegue subito il percorso.
# La configurazione del robot deve restare uguale a quella di Test.py.

from pybricks.hubs import PrimeHub
from pybricks.parameters import Axis, Color, Direction, Port, Stop
from pybricks.pupdevices import Motor
from pybricks.robotics import DriveBase
from pybricks.tools import wait

# LTC.py sostituisce questa riga con il percorso esportato
PERCORSO = ""

Posizione = 1
Tuff = PrimeHub(top_side=Axis.Y, front_side=Axis.Z)
ChilyConCarne = Motor(Port.A, Direction.COUNTERCLOCKWISE)
Vortex = Motor(Port.B, Direction.CLOCKWISE)
Coso_Tuff = DriveBase(ChilyConCarne, Vortex, 62.4, 140)
PinoIlMotorino = Motor(Port.C, Direction.CLOCKWISE)
Gilberto = Motor(Port.D, Direction.CLOCKWISE)
# La gearbox parte a mano sul motore 1: quello e' lo 0
PinoIlMotorino.reset_angle(0)

def Motore(Target, Gradi):
    global Posizione
    if 1 <= Target <= 4:
        PinoIlMotorino.run_target(500, (1 - Target) * 180, Stop.HOLD)
        Tuff.display.off()
        Tuff.display.number(Target)
        Gilberto.run_angle(200, Gradi, Stop.BRAKE)
        Posizione = Target

Coso_Tuff.settings(straight_speed=600)
Coso_Tuff.settings(straight_acceleration=200)
Coso_Tuff.settings(turn_rate=100)
Coso_Tuff.settings(turn_acceleration=30)
Coso_Tuff.use_gyro(True)
Coso_Tuff.reset(0, 0)

for Riga in PERCORSO.split("\n"):
    Parti = Riga.split()
    if not Parti:
        continue
    Valori = [int(Valore) for Valore in Parti[1:]]
    if Parti[0] == "A":
        Coso_Tuff.straight(Valori[0])
    elif Parti[0] == "G":
        Coso_Tuff.turn(Valori[0], absolute=True)
    elif Parti[0] == "M":
        Motore(Valori[0], Valori[1])
    elif Parti[0] == "C":
        Coso_Tuff.arc(Valori[0], angle=Valori[1])
    else:
        Tuff.light.on(Color.RED)
        wait(1000)
        break

# Riporta la gearbox sul primo motore (ogni motore e' a 180 gradi dal successivo),
# cosi' il programma dopo parte dalla stessa posizione
PinoIlMotorino.run_target(500, 0, Stop.HOLD)
Posizione = 1

# LTC.py legge questa riga per mostrare la batteria
print("BATTERIA", Tuff.battery.voltage())
