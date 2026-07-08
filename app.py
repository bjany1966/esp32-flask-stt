import os
import base64
import io
import wave
from flask import Flask, request
from google import genai
from google.genai import types

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = None
if GEMINI_API_KEY:
    try:
        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()
        client = genai.Client(api_key=clean_key)
    except Exception as e:
        print(f"Kliens inditasi hiba: {str(e)}")

def pcm_to_wav(pcm_data, sample_rate=16000, channels=1, bits_per_sample=16):
    """Nyers PCM bájtok átalakítása szabványos WAV formátummá a memóriában."""
    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(bits_per_sample // 8)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    return wav_io.getvalue()

@app.route('/')
def index():
    return "A kozponti hangfeldolgozo szerver aktiv es mukodik!"

@app.route('/upload', methods=['POST'])
def process_audio():
    global client
    
    if not client:
        raw_key = os.environ.get("GEMINI_API_KEY")
        if raw_key:
            clean_key = str(raw_key).replace("\n", "").replace("\r", "").strip()
            client = genai.Client(api_key=clean_key)
        else:
            print("HIBA: A GEMINI_API_KEY nincs beallitva a Renderen.")
            return "HIBA: Hianyzik a Gemini API kulcs a Render beallitasaibol.", 200

    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000:
            print(f"HIBA: Tul rovid adat erkezett! Meret: {len(pcm_data)} bajt.")
            return "HIBA: Tul rovid vagy ures hangfajl erkezett.", 200
            
        print(f"Sikeresen beerkezett a PCM hang az ESP-rol! Meret: {len(pcm_data)} bajt.")

        # Átalakítás univerzális WAV formátummá, amit az API 100%, hogy elfogad
        wav_data = pcm_to_wav(pcm_data, sample_rate=16000)
        print(f"WAV konverzio kész. Új méret fejléccel: {len(wav_data)} bájt.")

        # Hang előkészítése a megfelelő mime-típussal (audio/wav)
        audio_part = types.Part.from_bytes(
            data=wav_data,
            mime_type="audio/wav"
        )

        print("Kuldes a Gemini API-nak a hivatalos Google SDK-val...")
        
        # A legújabb általános modell hívása, ami stabilan kezeli az audio tartalmakat
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[
                "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 5-6 szoban!",
                audio_part
            ]
        )
        
        if response.text:
            reply = response.text.strip()
            print(f"Sikeres Gemini valasz: {reply}")
            return reply
        else:
            print(f"Ures valasz erkezett a Geminitol: {response}")
            return "HIBA: A Gemini valasza ures volt.", 200

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        return f"HIBA: Google SDK hiba: {str(e)}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
