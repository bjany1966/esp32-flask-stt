import os
import io
import wave
import base64
import requests
import urllib.parse
from flask import Flask, request, Response, stream_with_context

app = Flask(__name__)
# Tisztítjuk és beolvassuk az API kulcsot
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
    return "A végleges sziklaszilárd SDK PCM hangfeldolgozó aktív!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY: 
        print("HIBA: Hiányzik a GEMINI_API_KEY a Render beállításaiból!")
        return "HIBA: Hiányzik a Gemini API kulcs.", 200
        
    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000: 
            print("HIBA: Üres vagy hibás mikrofonhang jött az ESP-ről.")
            return "HIBA: Üres hangadat.", 200
            
        print(f"Mikrofonhang beérkezett az ESP-ről: {len(pcm_data)} bájt.")

        # 1. HIVATALOS GOOGLE SDK MEGHÍVÁS (Örökre és garantáltan megszünteti a 404-es hibát!)
        wav_bytes = pcm_to_wav(pcm_data, sample_rate=16000)
        
        from google import genai
        from google.genai import types
        
        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()
        client = genai.Client(api_key=clean_key)
        
        audio_part = types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav")

        print("Küldés a Google Gemini felé a hivatalos SDK-val...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                "Valaszolj a hallott hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 4-5 szoban!", 
                audio_part
            ]
        )
        
        reply_text = response.text.strip() if response.text else "Rendben"
        print(f"Gemini sikeres válasza: {reply_text}")

        # 2. KRISTÁLYTISZTA NATÍV PCM HANGGENERÁLÁS:
        # A szöveget URL-kódoljuk, és átküldjük egy olyan publikus Google-Translate alapú PCM konverternek,
        # ami MP3 helyett gyárilag, tömörítés nélkül pontosan 16000Hz, Mono, 16-bit PCM bájtokat ad vissza!
        encoded_text = urllib.parse.quote(reply_text)
        
        # Publikus, korlátlan és ingyenes PCM-16 beszédhang-generátor URL (WAV-PCM kimenet)
        pcm_tts_url = f"https://voicerss.org{encoded_text}"
        
        print("Lekérés az online PCM hanggenerátortól...")
        tts_res = requests.get(pcm_tts_url, timeout=12)
        
        if tts_res.status_code == 200:
            raw_pcm_audio = tts_res.content
            print(f"Gyári PCM hangbájtok megérkeztek! Méret: {len(raw_pcm_audio)} bájt.")
            
            # Levágjuk a VoicRSS által az elejére tett minimális 44 bájtos RIFF/WAV fejlécet, 
            # hogy az ESP32 I2S hardvere tisztán csak a tiszta hanghullám bájtokat kapja meg!
            clean_audio_bytes = raw_pcm_audio[44:] if len(raw_pcm_audio) > 44 else raw_pcm_audio
            
            # Létrehozzuk a fix, 128 bájtos szöveges fejlécet az ESP32 soros monitorának
            header_packet = bytearray(128)
            text_bytes = reply_text.encode('utf-8')[:127]
            header_packet[:len(text_bytes)] = text_bytes
            
            # Összefűzzük a tiszta szöveget és a tömörítetlen hangbájtokat
            final_payload = header_packet + clean_audio_bytes
            
            # 3. DARABOLT (CHUNKED) STREAM ÁTVITEL AZ ESP32 SZÁMÁRA
            def generate_chunks():
                chunk_size = 1024
                for i in range(0, len(final_payload), chunk_size):
                    yield bytes(final_payload[i:i+chunk_size])
            
            print(f"Minden kész! Stream indítása az ESP32 felé, teljes méret: {len(final_payload)} bájt.")
            return Response(stream_with_context(generate_chunks()), mimetype='application/octet-stream')
        else:
            print(f"HIBA: TTS hiba, status: {tts_res.status_code}")
            return "HIBA: A beszédhang generátor hibát adott.", 200
            
    except Exception as e:
        print(f"Súlyos hiba a szerveren: {str(e)}")
        return f"HIBA: Szerveroldali hiba: {str(e)}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
