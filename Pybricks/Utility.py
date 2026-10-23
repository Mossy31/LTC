Scripts = [

"""
G 0
A 463
G 89
A 745
M 0 0
""",

"""
G 45
A 300
"""

]

def Carica(Indice):
    Istruzioni = []
    for Riga in Scripts[Indice].split("\n"):
        Parti = Riga.split()
        if Parti:
            Istruzioni.append([Parti[0]] + [int(Valore) for Valore in Parti[1:]])
    return Istruzioni