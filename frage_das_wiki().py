# In irgendeinem deiner anderen Automatisierungsskripte:
from 10_ask_wiki import frage_das_wiki

# Die Maschine stellt die Frage
ergebnis = frage_das_wiki("Wie lautet die Projektnummer von Hexal?")

# Die Maschine arbeitet mit dem reinen Text weiter
print("Die KI sagt: " + ergebnis["antwort"])
print("Gefunden in Datei: " + ergebnis["quellen"][0])