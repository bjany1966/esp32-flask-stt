import os
import io
import wave
import urllib.parse
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
    return "A kozponti stabil darabolt PCM hangfeldolgozo aktiv!"

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
        
        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()
        client = genai.Client(api_key=clean_key)
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=["Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, max 4-5 szoban!", types.Part.from_bytes(data=wav_data, mime_type="audio/wav")]
        )
        reply_text = response.text.strip() if response.text else "Rendben"
        print(f"Gemini valasz: {reply_text}")

        # 2. KRISTÁLYTISZTA PCM HANGGENERÁLÁS: 
        # A szöveget biztonságosan URL-kódoljuk, és egy olyan publikus TTS átalakítón küldjük át, 
        # ami MP3 helyett gyárilag, natívan tömörítetlen LINEÁRIS PCM (16kHz, Mono, 16-bit) bájtokat ad vissza!
        encoded_text = urllib.parse.quote(reply_text)
        pcm_tts_url = f"https://voicerss.org{encoded_text}"
        
        print("Lekérés az online PCM hanggenerátortól...")
        tts_res = requests.get(pcm_tts_url, timeout=12, stream=True)
        
        if tts_res.status_code == 200:
            # DARABOLT (CHUNKED) STREAM: 
            # 1024 bájtos darabokban közvetlenül továbbítjuk a tiszta PCM bájtokat az ESP32-nek!
            def generate_chunks():
                # Biztonsági okokból átugorjuk az első 44 bájtot (WAV fejléc), ha jelen van
                first_chunk = True
                for chunk in tts_res.iter_content(chunk_size=1024):
                    if chunk:
                        if first_chunk and len(chunk) > 44:
                            first_chunk = False
                            yield chunk[44:]
                        else:
                            yield chunk
            
            print("Kristálytiszta PCM hangstream indítása az ESP32 felé...")
            return Response(stream_with_context(generate_chunks()), mimetype='application/octet-stream')
            
        return "TTS hiba", 500
    except Exception as e:
        print(str(e))
        return "Szerver Hiba", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
