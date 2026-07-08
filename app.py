import os
import io
import wave
import requests
from flask import Flask, request, Response

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

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
    return "A kozponti MP3 hangfeldolgozo szerver aktiv!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY:
        return "HIBA: Hianyzik az API kulcs.", 500

    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000:
            return "HIBA: Ures hang", 400
            
        print(f"Beérkezett mikrofonhang az ESP-ről: {len(pcm_data)} bájt.")

        # 1. Mikrofon PCM -> WAV konverzió a Geminihez
        wav_data = pcm_to_wav(pcm_data, sample_rate=16000)
        
        from google import genai
        from google.genai import types
        
        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()
        client = genai.Client(api_key=clean_key)

        print("Küldés a Gemini API-nak... Szöveges válasz kérése.")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 4-5 szoban!",
                types.Part.from_bytes(data=wav_data, mime_type="audio/wav")
            ]
        )
        
        reply_text = response.text.strip() if response.text else "Rendben"
        print(f"Gemini szöveges válasza: {reply_text}")

        # 2. HANGGENERÁLÁS: Google TTS szabványos, tiszta MP3 folyam lekérése
        tts_url = "https://google.com"
        headers = {"User-Agent": "Mozilla/5.0"}
        params = {
            "ie": "UTF-8",
            "tl": "hu",
            "client": "tw-ob",
            "q": reply_text
        }
        
        tts_response = requests.get(tts_url, params=params, headers=headers, timeout=10)
        if tts_response.status_code == 200:
            print(f"Tiszta MP3 hang legenerálva! Méret: {len(tts_response.content)} bájt.")
            return Response(tts_response.content, mimetype='audio/mpeg')
        else:
            return "HIBA: Nem sikerult hangot generalni", 500

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        return f"HIBA: Szerver hiba: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
