import speech_recognition as sr
import sounddevice as sd
import wave
import os

def mikrofon_test_modern():
    fs = 16000  # Samplerate (16kHz ist der absolute Standard für KI-Spracherkennung)
    dauer = 5   # Aufnahmezeit in Sekunden
    temp_datei = "temp_aufnahme.wav"
    
    print(f"\n🎤 Mikrofon bereit! Bitte sprich jetzt für {dauer} Sekunden klar und deutlich...")
    
    try:
        # 1. Aufnahme via sounddevice starten (Völlig ohne PyAudio-Zwang)
        audio_array = sd.rec(int(dauer * fs), samplerate=fs, channels=1, dtype='int16')
        sd.wait()  # Warten, bis die 5 Sekunden um sind
        print("⏳ Aufnahme beendet. Verarbeite Audiospur...")
        
        # 2. Die Aufnahme als temporäre Standard-WAV-Datei speichern
        with wave.open(temp_datei, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit entspricht 2 Bytes
            wf.setframerate(fs)
            wf.writeframes(audio_array.tobytes())
            
        # 3. SpeechRecognition auf die Datei ansetzen (Das erfordert KEIN PyAudio!)
        recognizer = sr.Recognizer()
        with sr.AudioFile(temp_datei) as source:
            audio_daten = recognizer.record(source)
            
            print("🧠 Sende Daten an Google Web Speech API...")
            text = recognizer.recognize_google(audio_daten, language="de-DE")
            print(f"\n✅ Erkannt: \"{text}\"")
            
    except sr.UnknownValueError:
        print("❌ Fehler: Tonspur wurde aufgezeichnet, aber der Text war zu undeutlich.")
    except sr.RequestError as e:
        print(f"❌ Fehler: Keine Verbindung zum Server möglich; {e}")
    except Exception as e:
        print(f"❌ Technischer Fehler bei der Aufnahme: {str(e)}")
    finally:
        # 4. Die temporäre Datei sauber wieder von der Festplatte löschen
        if os.path.exists(temp_datei):
            os.remove(temp_datei)

if __name__ == "__main__":
    mikrofon_test_modern()