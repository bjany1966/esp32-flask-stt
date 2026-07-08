import os
import base64
import io
import wave
from flask import Flask, request

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = None
if GEMINI_API_KEY:
    try:
        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()
        from google import genai
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
    return "A kozponti szerver aktiv es mukodik!"

@app.route('/upload', methods=['POST'])
def process_audio():
    global client
    if not client:
        raw_key = os.environ.get("GEMINI_API_KEY")
        if raw_key:
            clean_key = str(raw_key).replace("\n", "").replace("\r", "").strip()
            from google import genai
            client = genai.Client(api_key=clean_key)
        else:
            return "Hianyzik az API kulcs.", 200

    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000:
            return "Ures vagy hibas hangfajl erkezett.", 200
            
        print(f"Beerkezett a hang! Meret: {len(pcm_data)} bajt.")

        wav_data = pcm_to_wav(pcm_data, sample_rate=16000)
        
        from google.genai import types
        audio_part = types.Part.from_bytes(data=wav_data, mime_type="audio/wav")

        print("Kuldes a Gemini API-nak...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 3-4 szoban!",
                audio_part
            ]
        )
        
        # Kizárólag a tiszta, rövid szöveget küldjük vissza az ESP32-nek!
        reply_text = response.text.strip() if response.text else "Rendben"
        print(f"Sikeres Gemini valasz: {reply_text}")
        return reply_text

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        return "Hiba tortent probald kesobb", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
