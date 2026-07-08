import os
import io
import wave
import requests
from flask import Flask, request, send_file

app = Flask(__name__)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Átmeneti globális változó a legutolsó legenerált hang tárolására
latest_mp3_bytes = b""

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
    return "A kozponti MP3 streaming szerver aktiv!"

@app.route('/upload', methods=['POST'])
def process_audio():
    global latest_mp3_bytes
    if not GEMINI_API_KEY: 
        return "HIBA: Hianyzik a Gemini kulcs", 500
    try:
        pcm_data = request.data
        if not pcm_data: return "Ures hang", 400
        
        print(f"Mikrofonhang beerkezett: {len(pcm_data)} bajt.")

        # 1. Gemini szöveges kérés (ez ingyenesen és sziklaszilárdan működik)
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

        # 2. TTS kérés a Google Translate-től (Standard, tökéletes MP3)
        tts_url = "https://google.com"
        headers = {"User-Agent": "Mozilla/5.0"}
        params = {"ie": "UTF-8", "tl": "hu", "client": "tw-ob", "q": reply_text}
        
        tts_res = requests.get(tts_url, params=params, headers=headers, timeout=10)
        if tts_res.status_code == 200:
            latest_mp3_bytes = tts_res.content
            print(f"Tiszta MP3 elmentve a szerver memóriájába: {len(latest_mp3_bytes)} bájt.")
            return "OK"
        return "TTS hiba", 500
    except Exception as e:
        print(str(e))
        return "Szerver hiba", 500

# Ezen a végponton keresztül az ESP32 tiszta HTTP-n (SSL nélkül) éri el a hangot!
# Ez megszünteti az SSL miatti 720 KB-os pufferigényt és az OOM hibát!
@app.route('/get_audio_stream.mp3', methods=['GET'])
def get_audio_stream():
    global latest_mp3_bytes
    if len(latest_mp3_bytes) > 0:
        return send_file(
            io.BytesIO(latest_mp3_bytes),
            mimetype='audio/mpeg',
            as_attachment=False
        )
    return "Nincs kesz hang", 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
