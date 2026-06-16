import sys
import pyttsx3
import speech_recognition as sr
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLineEdit, QTextEdit, QLabel, QCheckBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from ask_wiki import frage_das_wiki

# --- HINTERGRUND-ARBEITER ---

class WikiWorker(QThread):
    antwort_fertig = pyqtSignal(dict)
    def __init__(self, frage):
        super().__init__()
        self.frage = frage
    def run(self):
        ergebnis = frage_das_wiki(self.frage)
        self.antwort_fertig.emit(ergebnis)

class SpeakerWorker(QThread):
    def __init__(self, text):
        super().__init__()
        # Wir filtern Markdown-Zeichen heraus, damit sie nicht mitgelesen werden
        self.text = text.replace('*', '').replace('#', '')
    def run(self):
        engine = pyttsx3.init()
        # Stimme etwas flüssiger und schneller machen
        engine.setProperty('rate', 180) 
        engine.say(self.text)
        engine.runAndWait()

class ListenerWorker(QThread):
    text_erkannt = pyqtSignal(str)
    status_update = pyqtSignal(str)
    
    def run(self):
        r = sr.Recognizer()
        with sr.Microphone() as source:
            self.status_update.emit("🎤 Bitte jetzt sprechen...")
            # Passt sich kurz an die Hintergrundgeräusche an
            r.adjust_for_ambient_noise(source, duration=0.5) 
            try:
                audio = r.listen(source, timeout=5, phrase_time_limit=15)
                self.status_update.emit("⏳ Verarbeite Sprache...")
                text = r.recognize_google(audio, language="de-DE")
                self.text_erkannt.emit(text)
            except sr.UnknownValueError:
                self.text_erkannt.emit("FEHLER: Konnte dich leider nicht verstehen.")
            except sr.RequestError:
                self.text_erkannt.emit("FEHLER: Keine Verbindung zur Spracherkennung.")
            except Exception:
                self.text_erkannt.emit("FEHLER: Kein Mikrofon gefunden oder Timeout.")

# --- BENUTZEROBERFLÄCHE ---

class DigiWikiAudioUI(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('DigiWiki Voice-Assistent')
        self.resize(850, 650)
        self.setStyleSheet("background-color: #f4f5f7; color: #333;")

        layout = QVBoxLayout()

        # Header mit Audio-Option
        header_layout = QHBoxLayout()
        header = QLabel('🧠 DigiBest Knowledge Base')
        header.setFont(QFont('Arial', 16, QFont.Bold))
        header.setStyleSheet("padding: 10px; color: #2c3e50;")
        
        self.check_audio = QCheckBox("🔊 Antwort vorlesen")
        self.check_audio.setChecked(True) # Standardmäßig an
        self.check_audio.setStyleSheet("font-weight: bold; color: #2980b9;")
        
        header_layout.addWidget(header)
        header_layout.addStretch()
        header_layout.addWidget(self.check_audio)
        layout.addLayout(header_layout)

        # Chat-Verlauf
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont('Arial', 11))
        self.chat_display.setStyleSheet("background-color: white; border: 1px solid #ccc; border-radius: 5px; padding: 10px;")
        layout.addWidget(self.chat_display)

        # Status-Anzeige fürs Mikrofon
        self.status_label = QLabel('')
        self.status_label.setStyleSheet("color: #e67e22; font-style: italic;")
        layout.addWidget(self.status_label)

        # Eingabebereich
        input_layout = QHBoxLayout()
        
        self.btn_mikrofon = QPushButton('🎤 Sprechen')
        self.btn_mikrofon.setStyleSheet("""
            QPushButton { background-color: #e74c3c; color: white; border-radius: 5px; padding: 10px; font-weight: bold; }
            QPushButton:hover { background-color: #c0392b; }
        """)
        self.btn_mikrofon.clicked.connect(self.starte_zuhören)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText('Stelle eine Frage (Tippen oder Sprechen)...')
        self.input_field.setFont(QFont('Arial', 11))
        self.input_field.setStyleSheet("padding: 10px; border: 1px solid #ccc; border-radius: 5px;")
        self.input_field.returnPressed.connect(self.sende_freitext)
        
        self.btn_senden = QPushButton('Senden')
        self.btn_senden.setStyleSheet("""
            QPushButton { background-color: #2ecc71; color: white; border-radius: 5px; padding: 10px 20px; font-weight: bold; }
            QPushButton:hover { background-color: #27ae60; }
        """)
        self.btn_senden.clicked.connect(self.sende_freitext)

        input_layout.addWidget(self.btn_mikrofon)
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.btn_senden)
        layout.addLayout(input_layout)

        self.setLayout(layout)

    # --- LOGIK FÜR AUDIO UND TEXT ---

    def starte_zuhören(self):
        self.btn_mikrofon.setEnabled(False)
        self.btn_senden.setEnabled(False)
        self.input_field.setEnabled(False)
        
        self.listener = ListenerWorker()
        self.listener.status_update.connect(self.update_status)
        self.listener.text_erkannt.connect(self.verarbeite_sprache)
        self.listener.start()

    def update_status(self, text):
        self.status_label.setText(text)

    def verarbeite_sprache(self, text):
        self.status_label.setText('')
        self.btn_mikrofon.setEnabled(True)
        self.btn_senden.setEnabled(True)
        self.input_field.setEnabled(True)

        if text.startswith("FEHLER"):
            self.chat_display.append(f"<b style='color:#e74c3c;'>System:</b> {text}<br><hr>")
        else:
            self.input_field.setText(text)
            self.sende_freitext() # Schickt die erkannte Frage direkt ab!

    def sende_freitext(self):
        frage = self.input_field.text()
        if frage.strip():
            self.sende_frage(frage)
            self.input_field.clear()

    def sende_frage(self, frage):
        self.chat_display.append(f"<b style='color:#2980b9;'>Du:</b> {frage}<br>")
        self.chat_display.append("<i>DigiWiki durchsucht die Ordner...</i><br>")
        
        self.btn_senden.setEnabled(False)
        self.input_field.setEnabled(False)

        self.worker = WikiWorker(frage)
        self.worker.antwort_fertig.connect(self.zeige_antwort)
        self.worker.start()

    def zeige_antwort(self, ergebnis):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.End)
        self.chat_display.setTextCursor(cursor)
        
        antwort = ergebnis["antwort"]
        antwort_html = antwort.replace('\n', '<br>')
        self.chat_display.append(f"<b style='color:#27ae60;'>DigiWiki:</b> {antwort_html}<br>")
        self.chat_display.append("<hr>")

        # Audio-Ausgabe triggern, falls Checkbox aktiv ist
        if self.check_audio.isChecked():
            self.speaker = SpeakerWorker(antwort)
            self.speaker.start()

        self.btn_senden.setEnabled(True)
        self.input_field.setEnabled(True)
        self.input_field.setFocus()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = DigiWikiAudioUI()
    ex.show()
    sys.exit(app.exec_())