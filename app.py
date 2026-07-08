import os
import base64
import io
import wave
from flask import Flask, request, send_file
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
            return "Hianyzik az API kulcs.", 500

    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000:
            return "Ures vagy hibas hangfajl.", 400
            
        print(f"Beérkezett mikrofonhang: {len(pcm_data)} bájt.")

        # 1. PCM -> WAV konverzió a bemenethez
        wav_data = pcm_to_wav(pcm_data, sample_rate=16000)
        audio_part = types.Part.from_bytes(data=wav_data, mime_type="audio/wav")

        print("Kuldes a Gemini API-nak közvetlen HANG kimeneti kéréssel...")
        
        # 2. Úgy állítjuk be a Gemini-t, hogy közvetlenül AUDIO formátumban válaszoljon!
        config = types.GenerateContentConfig(
            response_mime_type="audio/mp3" # vagy "audio/pcm" / "audio/wav"
        )
        
        # A válasznak egyből hangot kérünk a modelltől
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                "Valaszolj a hallott hangra tisztan magyarul, nagyon roviden, maximum 5-6 szoban!",
                audio_part
            ]
        )
        
        # Megkeressük a Gemini által visszaküldött nyers hangbájtokat a JSON struktúrában
        audio_bytes = None
        try:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    audio_bytes = base64.b64decode(part.inline_data.data)
                    break
        except Exception:
            pass

        if audio_bytes:
            print(f"A Gemini közvetlen hangválasza megérkezett! Méret: {len(audio_bytes)} bájt.")
            return send_file(
                io.BytesIO(audio_bytes),
                mimetype='application/octet-stream'
            )
        else:
            print("Nem sikerült közvetlen hangot kinyerni a Gemini válaszból. Szöveges válasz: ", response.text)
            return "HIBA: Nem erkezett hangvalasz a modelltol.", 200

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        return f"Szerver hiba: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
