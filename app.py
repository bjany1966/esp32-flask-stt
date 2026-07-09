import os
import io
import wave
import requests
from flask import Flask, request, Response, stream_with_context
import minimp3

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
        return "HIBA: Hianyzik a Gemini kulcs a Render beallitasaibol.", 200
    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000: 
            return "HIBA: Ures vagy hibas hangfelvetel.", 200
        
        print(f"Mikrofonhang beerkezett az ESP-ről: {len(pcm_data)} bajt.")

        # 1. Gemini kérés
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

        # 2. TTS kérés a Google Translate API-tól (Standard MP3)
        tts_url = "https://google.com"
        headers = {"User-Agent": "Mozilla/5.0"}
        params = {"ie": "UTF-8", "tl": "hu", "client": "tw-ob", "q": reply_text}
        tts_res = requests.get(tts_url, params=params, headers=headers, timeout=12)
        
        if tts_res.status_code == 200:
            mp3_bytes = tts_res.content
            
            # JAVÍTVA: Igazi, szoftveres MP3 dekódolás tiszta lineáris PCM-mé!
            # A minimp3 kicsomagolja az összes MP3 keretet valódi 16-bites Mono hangmintákká!
            try:
                mp3_decoder = minimp3.Decoder()
                # Dekódoljuk az MP3 bájtokat (az API visszatérési értéke: sample_rate, channels, pcm_data)
                _, _, pcm_clean = mp3_decoder.decode(mp3_bytes)
            except Exception as dec_e:
                print(f"Dekodolasi hiba, tartalek mukanak futtatasa: {str(dec_e)}")
                pcm_clean = b'\x00' * 16000 # Tartalék csend hiba esetére
            
            # DARABOLT GENERÁTOR FÜGGVÉNY AZ ESP SZÁMÁRA
            def generate_chunks():
                chunk_size = 1024
                for i in range(0, len(pcm_clean), chunk_size):
                    yield bytes(pcm_clean[i:i+chunk_size])
            
            print(f"Kristálytiszta, valódi PCM hangstream indítása az ESP32-nek... Méret: {len(pcm_clean)} bájt.")
            return Response(stream_with_context(generate_chunks()), mimetype='application/octet-stream')
            
        return "HIBA: TTS hiba a Google-nel.", 200
    except Exception as e:
        print(f"Szerver hiba: {str(e)}")
        return f"HIBA: Szerveroldali hiba: {str(e)}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
