import sounddevice as sd
import numpy as np
import wave
import tempfile
import os
import speech_recognition as sr

def hoeren_und_verstehen(dauer_in_sekunden=5):
    samplerate = 44100  # Standard-CD-Qualität
    
    print(f"\n🎤 MIKROFON AN: Bitte sprich jetzt... (Du hast {dauer_in_sekunden} Sekunden)")
    
    try:
        # 1. Wir nehmen den Ton über die moderne sounddevice-Bibliothek auf
        # dtype='int16' ist wichtig, damit die Daten das klassische Audioformat haben
        aufnahme = sd.rec(int(dauer_in_sekunden * samplerate), samplerate=samplerate, channels=1, dtype='int16')
        sd.wait()  # Wartet, bis die 5 Sekunden abgelaufen sind
        print("✅ Aufnahme beendet. KI denkt nach...\n")
        
        # 2. Wir erstellen eine temporäre Datei (wird später automatisch gelöscht)
        temp_wav = tempfile.mktemp(suffix=".wav")
        
        # 3. Wir verpacken die rohen Tondaten in eine saubere .wav Datei
        with wave.open(temp_wav, 'wb') as wf:
            wf.setnchannels(1)           # Mono
            wf.setsampwidth(2)           # 16-bit (2 Bytes)
            wf.setframerate(samplerate)
            wf.writeframes(aufnahme.tobytes())
            
        # 4. Jetzt übergeben wir die Datei an die Spracherkennung
        r = sr.Recognizer()
        with sr.AudioFile(temp_wav) as source:
            audio_daten = r.record(source)
            
        # 5. Wir schicken den Ton an Google zur Übersetzung
        erkannter_text = r.recognize_google(audio_daten, language="de-DE")
        
        print("-" * 40)
        print(f"🤖 Ich habe verstanden: '{erkannter_text}'")
        print("-" * 40)
        
    except sr.UnknownValueError:
        print("❌ Ich konnte leider kein klares Wort verstehen. (War es zu leise?)")
    except sr.RequestError as e:
        print(f"❌ Fehler bei der Verbindung zum Google-Sprachserver: {e}")
    except Exception as e:
        print(f"❌ Ein Systemfehler ist aufgetreten: {e}")
        
    finally:
        # 6. Spuren verwischen: Temporäre Audio-Datei wieder löschen
        if 'temp_wav' in locals() and os.path.exists(temp_wav):
            os.remove(temp_wav)

if __name__ == "__main__":
    hoeren_und_verstehen()