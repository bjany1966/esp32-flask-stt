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
    return "A kozponti stabil MP3 hangfeldolgozo aktiv!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY: 
        return "Hianyzik a Gemini kulcs", 500
    try:
        pcm_data = request.data
        if not pcm_data: return "Ures hang", 400
        
        print(f"Mikrofonhang beerkezett: {len(pcm_data)} bajt.")

        # 1. Gemini szöveges kérés
        wav_data = pcm_to_wav(pcm_data, sample_rate=16000)
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=str(GEMINI_API_KEY).strip())
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=["Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, max 4-5 szoban!", types.Part.from_bytes(data=wav_data, mime_type="audio/wav")]
        )
        reply_text = response.text.strip() if response.text else "Rendben"
        print(f"Gemini valasz: {reply_text}")

        # 2. TTS kérés (Google Translate standard, tiszta MP3)
        tts_url = "https://google.com"
        headers = {"User-Agent": "Mozilla/5.0"}
        tts_res = requests.get(tts_url, params={"ie": "UTF-8", "tl": "hu", "client": "tw-ob", "q": reply_text}, headers=headers, timeout=10)
        
        if tts_res.status_code == 200:
            mp3_data = tts_res.content
            print(f"Tiszta MP3 hang kesz az ESP-nek: {len(mp3_data)} bajt.")
            
            # Fix hosszt küldünk vissza, nem engedjük a Rendernek a darabolást!
            return Response(
                mp3_data,
                mimetype='audio/mpeg',
                headers={'Content-Length': str(len(mp3_data))}
            )
            
        return "TTS hiba", 500
    except Exception as e:
        print(str(e))
        return "Szerver hiba", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
