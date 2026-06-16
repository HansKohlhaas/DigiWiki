import sys
import os
import wave
import tempfile
import traceback
import markdown
import numpy as np
import sounddevice as sd
import speech_recognition as sr
from collections import deque
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QTextBrowser, QLineEdit, QLabel)
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QPainter, QColor

# Wir importieren unser Orakel-Gehirn
from ask_wiki import frage_das_wiki

class WellenAnzeige(QWidget):
    """Live-Schallwellen-Anzeige: zeigt den Mikrofon-Pegel in Echtzeit,
    damit sofort sichtbar ist, ob das Mikro tatsaechlich Ton empfaengt."""

    def __init__(self, balken=120):
        super().__init__()
        self.max_balken = balken
        self.pegel = deque([0.0] * balken, maxlen=balken)
        self.aktiv = False
        self.setMinimumHeight(64)
        self.setStyleSheet("background-color: #0f172a; border-radius: 6px;")

    def push(self, wert):
        # Neue Werte links einfuegen -> die Welle laeuft von links nach rechts.
        self.pegel.appendleft(max(0.0, min(1.0, float(wert))))
        self.update()

    def reset(self, aktiv=False):
        self.aktiv = aktiv
        self.pegel = deque([0.0] * self.max_balken, maxlen=self.max_balken)
        self.update()

    def paintEvent(self, event):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing, True)
        breite = self.width()
        hoehe = self.height()
        mitte = hoehe / 2.0
        n = len(self.pegel)
        if n == 0:
            return
        # Ruhelinie in der Mitte
        qp.setPen(QColor("#334155"))
        qp.drawLine(0, int(mitte), breite, int(mitte))
        # Balken (gruen bei Aufnahme, gedaempft sonst)
        farbe = QColor("#22c55e") if self.aktiv else QColor("#475569")
        qp.setPen(Qt.NoPen)
        qp.setBrush(farbe)
        balken_breite = breite / float(n)
        for i, wert in enumerate(self.pegel):
            balken_hoehe = max(2.0, wert * (hoehe - 8))
            x = i * balken_breite
            y = mitte - balken_hoehe / 2.0
            qp.drawRect(int(x), int(y), max(1, int(balken_breite) - 1), int(balken_hoehe))

class DiktatWorker(QThread):
    """Wandelt eine aufgenommene WAV-Datei per Google Speech in Text um.
    Laeuft im Hintergrund, damit die UI waehrend des Netzwerkaufrufs nicht einfriert."""
    fertig = pyqtSignal(str)
    fehler = pyqtSignal(str)

    def __init__(self, wav_pfad):
        super().__init__()
        self.wav_pfad = wav_pfad

    def run(self):
        try:
            r = sr.Recognizer()
            with sr.AudioFile(self.wav_pfad) as quelle:
                audio = r.record(quelle)
            text = r.recognize_google(audio, language="de-DE")
            self.fertig.emit(text)
        except sr.UnknownValueError:
            self.fehler.emit("Konnte dich leider nicht verstehen.")
        except sr.RequestError:
            self.fehler.emit("Keine Verbindung zur Spracherkennung (Internet?).")
        except Exception as e:
            self.fehler.emit(f"Diktat-Fehler: {e}")
        finally:
            try:
                if os.path.exists(self.wav_pfad):
                    os.remove(self.wav_pfad)
            except OSError:
                pass

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
        
        # Live-Schallwellen-Anzeige (zeigt, ob das Mikro Ton empfaengt)
        self.wellen_anzeige = WellenAnzeige()
        layout.addWidget(self.wellen_anzeige)
        
        # Status-Anzeige fuer das Diktat (Mikrofon-Feedback)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #e67e22; font-style: italic; font-size: 12px; padding: 2px 0;")
        layout.addWidget(self.status_label)
        
        # --- BEREICH 3: Die Buttons ---
        button_layout = QHBoxLayout()
        
        self.btn_mikrofon = QPushButton("🎤 Diktieren")
        self.btn_mikrofon.setStyleSheet("background-color: #e74c3c; color: white; padding: 10px 20px; font-weight: bold; border-radius: 5px; font-size: 14px;")
        self.btn_mikrofon.clicked.connect(self.toggle_aufnahme)
        button_layout.addWidget(self.btn_mikrofon)
        
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
        
        # --- Diktat / Aufnahme-Status ---
        self.aufnahme_aktiv = False
        self.aufnahme_stream = None
        self.aufnahme_frames = []
        self.diktat_worker = None
        self.SAMPLERATE = 16000  # 16 kHz ist Standard fuer KI-Spracherkennung
        
        # Live-Pegel fuer die Wellenanzeige (Callback-Thread schreibt, Timer liest)
        self.aktueller_pegel = 0.0
        self.pegel_timer = QTimer(self)
        self.pegel_timer.setInterval(40)
        self.pegel_timer.timeout.connect(self._aktualisiere_welle)

    # --- DIKTAT / MIKROFON ---

    def toggle_aufnahme(self):
        """Ein Klick startet die Aufnahme, der naechste stoppt sie und transkribiert."""
        if self.aufnahme_aktiv:
            self._stoppe_aufnahme()
        else:
            self._starte_aufnahme()

    def _audio_callback(self, indata, frames, zeit, status):
        # Laeuft im PortAudio-Thread: Rohdaten sammeln + aktuellen Pegel merken.
        self.aufnahme_frames.append(indata.copy())
        try:
            self.aktueller_pegel = float(np.abs(indata).max()) / 32768.0
        except Exception:
            self.aktueller_pegel = 0.0

    def _aktualisiere_welle(self):
        # Pegel etwas verstaerken, damit normale Sprache deutlich ausschlaegt.
        self.wellen_anzeige.push(min(1.0, self.aktueller_pegel * 3.0))

    def _starte_aufnahme(self):
        try:
            self.aufnahme_frames = []
            self.aufnahme_stream = sd.InputStream(
                samplerate=self.SAMPLERATE, channels=1, dtype='int16',
                callback=self._audio_callback,
            )
            self.aufnahme_stream.start()
        except Exception as e:
            self.status_label.setText(f"❌ Mikrofon-Fehler: {e}")
            return
        self.aufnahme_aktiv = True
        self.aktueller_pegel = 0.0
        self.wellen_anzeige.reset(aktiv=True)
        self.pegel_timer.start()
        self.btn_mikrofon.setText("⏹ Aufnahme stoppen")
        self.status_label.setText("🎤 Aufnahme laeuft - sprich jetzt, dann erneut auf den Button klicken.")

    def _stoppe_aufnahme(self):
        self.aufnahme_aktiv = False
        self.pegel_timer.stop()
        self.wellen_anzeige.reset(aktiv=False)
        self.btn_mikrofon.setText("🎤 Diktieren")
        try:
            if self.aufnahme_stream is not None:
                self.aufnahme_stream.stop()
                self.aufnahme_stream.close()
        except Exception:
            pass
        self.aufnahme_stream = None

        if not self.aufnahme_frames:
            self.status_label.setText("⚠️ Keine Audiodaten aufgenommen.")
            return

        audio = np.concatenate(self.aufnahme_frames, axis=0)
        wav_pfad = tempfile.mktemp(suffix=".wav")
        try:
            with wave.open(wav_pfad, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # int16 = 2 Bytes
                wf.setframerate(self.SAMPLERATE)
                wf.writeframes(audio.tobytes())
        except Exception as e:
            self.status_label.setText(f"❌ Konnte Aufnahme nicht speichern: {e}")
            return

        self.status_label.setText("⏳ Verarbeite Sprache ...")
        self.btn_mikrofon.setEnabled(False)
        self.diktat_worker = DiktatWorker(wav_pfad)
        self.diktat_worker.fertig.connect(self._diktat_fertig)
        self.diktat_worker.fehler.connect(self._diktat_fehler)
        self.diktat_worker.start()

    def _diktat_fertig(self, text):
        self.btn_mikrofon.setEnabled(True)
        self.status_label.setText("✅ Erkannt - bitte pruefen/anpassen und auf 'Senden' klicken.")
        # Editierbar anzeigen: vorhandenen Text nicht ueberschreiben, sondern ergaenzen.
        vorhandener = self.eingabe.text().strip()
        self.eingabe.setText(f"{vorhandener} {text}".strip())
        self.eingabe.setFocus()

    def _diktat_fehler(self, meldung):
        self.btn_mikrofon.setEnabled(True)
        self.status_label.setText(f"❌ {meldung}")

    def frage_senden(self):
        frage = self.eingabe.text().strip()
        if frage:
            self.frage_stellen(frage)
            self.eingabe.clear()

    def frage_stellen(self, frage):
        """Bereitet die Daten vor und startet den gedächtnisunterstützten Worker."""
        self.btn_senden.setEnabled(False)
        self.btn_hexal.setEnabled(False)
        self.btn_mikrofon.setEnabled(False)
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
        self.btn_mikrofon.setEnabled(True)
        self.eingabe.setEnabled(True)
        self.eingabe.setFocus()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    fenster = WikiMasterUI()
    fenster.show()
    sys.exit(app.exec_())