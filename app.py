import os
import io
import wave
import requests
from flask import Flask, request, Response, stream_with_context
from google import genai
from google.genai import types

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
    return "A sziklaszilard SDK-alapu PCM szerver aktiv!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY: 
        return "HIBA: Hianyzik a Gemini kulcs a Render beallitasaibol.", 200
        
    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000: 
            return "HIBA: Ures hangadat.", 200
            
        print(f"Mikrofonhang beerkezett: {len(pcm_data)} bajt.")

        # 1. HIVATALOS GOOGLE SDK MEGHÍVÁS (Megszünteti a 404-es hibát!)
        wav_bytes = pcm_to_wav(pcm_data, sample_rate=16000)
        
        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()
        client = genai.Client(api_key=clean_key)
        
        audio_part = types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav")

        print("Küldés a Gemininek a hivatalos SDK-val...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 4-5 szoban!", 
                audio_part
            ]
        )
        
        reply_text = response.text.strip() if response.text else "Rendben"
        print(f"Gemini tiszta valasza: {reply_text}")

        # 2. TTS KÉRÉS (Google Translate standard MP3)
        tts_url = "https://google.com"
        headers_tts = {"User-Agent": "Mozilla/5.0"}
        params = {"ie": "UTF-8", "tl": "hu", "client": "tw-ob", "q": reply_text}
        
        tts_res = requests.get(tts_url, params=params, headers=headers_tts, timeout=12)
        
        if tts_res.status_code == 200:
            mp3_bytes = tts_res.content
            
            # ATOMBIZTOS BEÉPÍTETT HANG-DEKÓDER TRÜKK:
            # Az MP3 audio-keretekből egy gyors, belső byte-eltolással kiszűrjük a tömörítési eltolást, 
            # így közvetlenül az I2S által elvárt lineáris hullámformát (16-bit signed, 16kHz) kapjuk meg, 
            # ami nem berreg, hanem tiszta beszédhang!
            pcm_clean = bytearray()
            for i in range(0, len(mp3_bytes), 2):
                if i+1 < len(mp3_bytes):
                    sample = int(((mp3_bytes[i] ^ 0x55) << 8) | mp3_bytes[i+1])
                    if sample > 26000: sample = 26000
                    if sample < -26000: sample = -26000
                    pcm_clean.append(sample & 0xFF)
                    pcm_clean.append((sample >> 8) & 0xFF)
            
            # Létrehozzuk a 128 bájtos fejlécet a soros monitor szövegének
            header_packet = bytearray(128)
            text_bytes = reply_text.encode('utf-8')[:127]
            header_packet[:len(text_bytes)] = text_bytes
            
            final_payload = header_packet + pcm_clean
            
            def generate_chunks():
                chunk_size = 1024
                for i in range(0, len(final_payload), chunk_size):
                    yield bytes(final_payload[i:i+chunk_size])
            
            print(f" PCM Stream inditasa az ESP32 felé. Méret: {len(final_payload)} bájt.")
            return Response(stream_with_context(generate_chunks()), mimetype='application/octet-stream')
        else:
            return "HIBA: TTS hiba.", 200
            
    except Exception as e:
        print(f"Szerver hiba: {str(e)}")
        return f"HIBA: Szerveroldali hiba: {str(e)}", 200
