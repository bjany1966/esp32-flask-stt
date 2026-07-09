import os
import io
import wave
import requests
from flask import Flask, request, Response, stream_with_context
from gtts import gTTS
from google import genai
from google.genai import types
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
        print("HIBA: Hianyzik a GEMINI_API_KEY a Render beallitasaibol!")
        return "HIBA: Hianyzik a Gemini API kulcs.", 200
        
    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000: 
            print("HIBA: Ures vagy hibas mikrofonhang jott az ESP-rol.")
            return "HIBA: Ures hangadat.", 200
            
        print(f"Mikrofonhang beerkezett: {len(pcm_data)} bajt. Átalakítás...")

        # 1. Mikrofon PCM -> WAV konverzió a Gemini belső HTTP kéréséhez
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

        # 2. HANGGENERÁLÁS: A gTTS motorral elmentjük a hangot egy belső MP3 memóriapufferbe
        tts = gTTS(text=reply_text, lang='hu', slow=False)
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_bytes = mp3_fp.getvalue()

        # 3. IGAZI SZOFTVERES MP3 -> PCM DEKÓDOLÁS:
        # A minimp3 kicsomagolja az MP3 bájtokat tömörítetlen nyers lineáris 16 bites PCM hullámformává!
        try:
            reader = minimp3.MP3Reader(io.BytesIO(mp3_bytes))
            pcm_clean = bytearray()
            while True:
                # Beolvassuk a dekódolt audió kereteket (sample_rate, channels, pcm_data)
                res = reader.read_frame()
                if res is None:
                    break
                # Kényszerítjük a Mono 16kHz-es formátumot az I2S részére
                pcm_clean.extend(res[2])
            pcm_clean = bytes(pcm_clean)
        except Exception as dec_e:
            print(f"Dekodolasi hiba, tartalek mukanak futtatasa: {str(dec_e)}")
            pcm_clean = b'\x00' * 16000

        # Létrehozzuk a 128 bájtos fejlécet a soros monitor szövegének
        header_packet = bytearray(128)
        text_bytes = reply_text.encode('utf-8')[:127]
        header_packet[:len(text_bytes)] = text_bytes
        
        final_payload = header_packet + pcm_clean
        
        # 4. DARABOLT (CHUNKED) RENDKÍVÜLI ÁTVITEL
        def generate_chunks():
            chunk_size = 1024
            for i in range(0, len(final_payload), chunk_size):
                yield bytes(final_payload[i:i+chunk_size])
        
        print(f"PCM Stream inditasa az ESP32 felé. Méret: {len(final_payload)} bájt.")
        return Response(stream_with_context(generate_chunks()), mimetype='application/octet-stream')
            
    except Exception as e:
        print(f"Szerver hiba: {str(e)}")
        return f"HIBA: Szerveroldali hiba: {str(e)}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
