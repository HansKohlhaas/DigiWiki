import sys
import traceback
import markdown
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QTextBrowser, QLineEdit)
from PyQt5.QtCore import QThread, pyqtSignal

# Wir importieren unser Orakel-Gehirn
from ask_wiki import frage_das_wiki

class WikiWorker(QThread):
    """Hintergrund-Arbeiter, der die Frage UND den bisherigen Verlauf transportiert."""
    antwort_fertig = pyqtSignal(dict)
    
    def __init__(self, frage, historie_text):
        super().__init__()
        self.frage = frage
        self.historie_text = historie_text
        
    def run(self):
        try:
            # Wir übergeben dem Orakel die Frage und das Kurzzeitgedächtnis
            ergebnis = frage_das_wiki(self.frage, self.historie_text)
            self.antwort_fertig.emit(ergebnis)
        except Exception as e:
            fehler_details = traceback.format_exc()
            fehler_html = f"<b style='color: #ef4444;'>KRITISCHER FEHLER IM HINTERGRUND:</b><br><pre style='font-size: 11px; background-color: #fee2e2; padding: 10px; border-radius: 5px;'>{fehler_details}</pre>"
            self.antwort_fertig.emit({"antwort": fehler_html, "quellen": []})

class WikiMasterUI(QMainWindow):
    """Die grafische Kommandozentrale für das DigiWiki mit Kurzzeitgedächtnis."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DigiWiki - Master Kommandozentrale")
        self.resize(900, 700)
        
        # --- NEU: Der Speicher für das Kurzzeitgedächtnis ---
        self.historie_daten = [] 
        self.aktuelle_frage = "" # Zwischenspeicher für die aktuelle Runde
        
        # Haupt-Widget und Layout einrichten
        haupt_widget = QWidget()
        self.setCentralWidget(haupt_widget)
        layout = QVBoxLayout(haupt_widget)
        
        # --- BEREICH 1: Der Chat-Verlauf ---
        self.chat_verlauf = QTextBrowser()
        self.chat_verlauf.setOpenExternalLinks(True)
        self.chat_verlauf.setStyleSheet("""
            background-color: #ffffff; 
            padding: 15px; 
            border: 1px solid #cbd5e1; 
            border-radius: 8px;
        """)
        layout.addWidget(self.chat_verlauf)
        
        # --- BEREICH 2: Die Eingabe ---
        self.eingabe = QLineEdit()
        self.eingabe.setPlaceholderText("Stelle eine Frage an das Wiki (z.B. nach bestimmten Kundendaten)...")
        self.eingabe.setStyleSheet("padding: 12px; font-size: 14px; border: 1px solid #cbd5e1; border-radius: 5px;")
        self.eingabe.returnPressed.connect(self.frage_senden)
        layout.addWidget(self.eingabe)
        
        # --- BEREICH 3: Die Buttons ---
        button_layout = QHBoxLayout()
        
        self.btn_senden = QPushButton("Senden")
        self.btn_senden.setStyleSheet("background-color: #0ea5e9; color: white; padding: 10px 20px; font-weight: bold; border-radius: 5px; font-size: 14px;")
        self.btn_senden.clicked.connect(self.frage_senden)
        button_layout.addWidget(self.btn_senden)
        
        # Beispiel für einen Schnell-Button
        self.btn_hexal = QPushButton("Briefing: Hexal")
        self.btn_hexal.setStyleSheet("padding: 10px; border-radius: 5px; background-color: #f1f5f9; border: 1px solid #cbd5e1;")
        self.btn_hexal.clicked.connect(lambda: self.frage_stellen("Gib mir eine kompakte Übersicht zum aktuellen Stand bei Hexal."))
        button_layout.addWidget(self.btn_hexal)
        
        layout.addLayout(button_layout)
        self.worker = None

    def frage_senden(self):
        frage = self.eingabe.text().strip()
        if frage:
            self.frage_stellen(frage)
            self.eingabe.clear()

    def frage_stellen(self, frage):
        """Bereitet die Daten vor und startet den gedächtnisunterstützten Worker."""
        self.btn_senden.setEnabled(False)
        self.btn_hexal.setEnabled(False)
        self.eingabe.setEnabled(False)
        
        # Wir merken uns die Frage für das Gedächtnis-Update später
        self.aktuelle_frage = frage
        
        # 1. Frage in der UI anzeigen
        self.chat_verlauf.append(f"<div style='margin-bottom: 10px;'><b style='color: #0ea5e9; font-size: 15px;'>Du:</b><br><span style='font-size: 14px;'>{frage}</span></div>")
        
        # 2. Den bisherigen Gesprächsverlauf als Fließtext für die KI zusammenbauen
        historie_string = "\n".join(self.historie_daten)
        
        # 3. Worker mit Frage UND Historie loslegen lassen
        self.worker = WikiWorker(frage, historie_string)
        self.worker.antwort_fertig.connect(self.zeige_antwort)
        self.worker.start()

    def zeige_antwort(self, ergebnis):
        """Wird aufgerufen, wenn das Gehirn geantwortet hat. Aktualisiert das Gedächtnis."""
        rohtext = ergebnis.get("antwort", "Keine Antwort erhalten.")
        quellen = ergebnis.get("quellen", [])
        
        # --- GEDÄCHTNIS AKTUALISIEREN ---
        # Nur wenn es kein technischer Fehler war, speichern wir die Runde im Kurzzeitgedächtnis
        if "KRITISCHER FEHLER IM HINTERGRUND" not in rohtext:
            self.historie_daten.append(f"Nutzer: {self.aktuelle_frage}")
            self.historie_daten.append(f"Assistenz: {rohtext}")
            
            # Wir halten das Gedächtnis schlank (die letzten 6 Einträge = 3 komplette Dialoge)
            # Das spart API-Kosten und verhindert, dass die KI verwirrt wird
            self.historie_daten = self.historie_daten[-6:]
        
        # Markdown in sauberes HTML übersetzen
        html_text = markdown.markdown(rohtext, extensions=['tables'])
        quellen_text = ", ".join(quellen) if quellen else "Keine spezifische Quelle"
        
        finale_ausgabe = f"""
        <div style='margin-bottom: 25px;'>
            <div style='background-color: #f8fafc; border-left: 4px solid #0ea5e9; padding: 15px; border-radius: 4px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; font-size: 14px; line-height: 1.5;'>
                <b style='color: #0ea5e9; font-size: 15px; margin-bottom: 8px; display: inline-block;'>DigiWiki:</b><br>
                {html_text}
            </div>
            <div style='margin-top: 5px; font-size: 11px; color: #64748b;'>
                <i>📚 Quellen: {quellen_text}</i>
            </div>
        </div>
        <hr style='border: none; border-top: 1px solid #e2e8f0; margin: 15px 0;'>
        """
        
        self.chat_verlauf.append(finale_ausgabe)
        
        self.btn_senden.setEnabled(True)
        self.btn_hexal.setEnabled(True)
        self.eingabe.setEnabled(True)
        self.eingabe.setFocus()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    fenster = WikiMasterUI()
    fenster.show()
    sys.exit(app.exec_())