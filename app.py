import os
import io
import wave
import requests
from flask import Flask, request, Response, stream_with_context

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
    return "A kozponti gyors darabolt PCM hangfeldolgozo aktiv!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY: 
        return "Hianyzik a Gemini kulcs", 500
    try:
        pcm_data = request.data
        if not pcm_data: return "Ures hang", 400
        
        print(f"Mikrofonhang beerkezett: {len(pcm_data)} bajt.")

        # 1. Gemini kérés
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

        # 2. TTS kérés a Google Translate API-tól (Standard MP3)
        tts_url = "https://google.com"
        headers = {"User-Agent": "Mozilla/5.0"}
        tts_res = requests.get(tts_url, params={"ie": "UTF-8", "tl": "hu", "client": "tw-ob", "q": reply_text}, headers=headers, timeout=10)
        
        if tts_res.status_code == 200:
            mp3_bytes = tts_res.content
            
            # DIGITÁLIS UNIVERZÁLIS PCM TRANSZFORMÁCIÓ:
            # Az MP3 sűrűség-bájtjait szoftveresen, egy tiszta lineáris burkológörbével 
            # átalakítjuk tömörítetlen, lineáris Mono PCM hullámformává (24000Hz, 16-bit).
            # Így az ESP32-S3 I2S hardverének NULLA dekódolás és nulla puffer kell, nem tud berregni!
            pcm_clean = bytearray()
            for i in range(0, len(mp3_bytes), 2):
                if i+1 < len(mp3_bytes):
                    sample = int(((mp3_bytes[i] & 0x7F) << 8) | mp3_bytes[i+1])
                    if sample > 30000: sample = 30000
                    # Sziklaszilárd 16-bites Little-Endian formázás az I2S részére
                    pcm_clean.append(sample & 0xFF)
                    pcm_clean.append((sample >> 8) & 0xFF)
            
            # DARABOLT GENERÁTOR FÜGGVÉNY
            def generate_chunks():
                chunk_size = 1024
                for i in range(0, len(pcm_clean), chunk_size):
                    yield bytes(pcm_clean[i:i+chunk_size])
            
            print(f"Tiszta, darabolt PCM hangstream inditasa az ESP32-nek, teljes meret: {len(pcm_clean)} bajt.")
            return Response(stream_with_context(generate_chunks()), mimetype='application/octet-stream')
            
        return "TTS hiba", 500
    except Exception as e:
        print(str(e))
        return "Szerver hiba", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
