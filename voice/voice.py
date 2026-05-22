import sounddevice as sd
import scipy.io.wavfile as wav
import speech_recognition as sr
from core.agent import debug_loop
import os

def record():
    fs = 44100
    duration = 5 # seconds
    print(f"Recording for {duration} seconds...")
    audio = sd.rec(int(duration * fs), samplerate=fs, channels=1)
    sd.wait()
    wav.write("cmd.wav", fs, audio)
    print("Recording finished.")

def run_voice():
    record()
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile("cmd.wav") as source:
            audio_data = recognizer.record(source)
            print("Transcribing...")
            cmd = recognizer.recognize_google(audio_data)
            print(f"JARVIS heard: {cmd}")
            
            # Use the debug_loop to allow tool execution
            debug_loop(cmd)
            
    except sr.UnknownValueError:
        print("JARVIS could not understand the audio.")
    except sr.RequestError as e:
        print(f"JARVIS error; {e}")
    finally:
        if os.path.exists("cmd.wav"):
            os.remove("cmd.wav")
