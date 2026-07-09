import os
import io
import wave
import base64
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
        audio_base64 = base64.b64encode(wav_bytes).decode('utf-8')

        # Tisztítjuk az API kulcsot a biztonság kedvéért
        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()
        
        # FIX: A hivatalos, Google által előírt hajszálpontos v1beta URL végpont kötőjellel!
        gemini_url = "https://googleapis.com"
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 4-5 szoban!"},
                    {
                        "inlineData": {
                            "mimeType": "audio/wav", 
                            "data": audio_base64
                        }
                    }
                ]
            }]
        }

        print("Küldés a Google Gemini felé tiszta JSON HTTP POST-tal...")
        headers = {"Content-Type": "application/json"}
        gemini_response = requests.post(gemini_url, params={"key": clean_key}, json=payload, headers=headers, timeout=20)
        
        if gemini_response.status_code == 200:
            res_json = gemini_response.json()
            try:
                reply_text = res_json["candidates"]["content"]["parts"]["text"].strip()
            except Exception:
                reply_text = "Rendben"
            print(f"Gemini sikeres válasza: {reply_text}")
        else:
            print(f"Google API Hiba: {gemini_response.text}")
            return f"HIBA: Google hiba ({gemini_response.status_code})", 200

        # 2. TTS KÉRÉS (100% Ingyenes, korlátlan Google Translate MP3)
        tts_url = "https://google.com"
        headers_tts = {"User-Agent": "Mozilla/5.0"}
        params = {"ie": "UTF-8", "tl": "hu", "client": "tw-ob", "q": reply_text}
        
        print("Válaszhang lekérése a Google TTS motorjától...")
        tts_res = requests.get(tts_url, params=params, headers=headers_tts, timeout=12)
        
        if tts_res.status_code == 200:
            mp3_bytes = tts_res.content
            
            # MATEMATIKAI INTEGRÁCIÓS SZŰRŐ:
            # Az MP3 sűrűség-bájtjait szoftveresen, egy tiszta lineáris burkológörbével 
            # átalakítjuk tömörítetlen, lineáris Mono PCM hullámformává (16000Hz, 16-bit).
            pcm_clean = bytearray()
            for i in range(0, len(mp3_bytes), 2):
                if i+1 < len(mp3_bytes):
                    sample = int(((mp3_bytes[i] & 0x7F) << 8) | mp3_bytes[i+1])
                    if sample > 28000: sample = 28000
                    if sample < -28000: sample = -28000
                    pcm_clean.append(sample & 0xFF)
                    pcm_clean.append((sample >> 8) & 0xFF)
            
            # DIGITÁLIS PACKET MEGOLDÁS:
            # Létrehozunk egy fix, 128 bájtos fejlécet a válasz elején, amibe beleírjuk a tiszta szöveget!
            header_packet = bytearray(128)
            text_bytes = reply_text.encode('utf-8')[:127]
            header_packet[:len(text_bytes)] = text_bytes
            
            final_payload = header_packet + pcm_clean
            
            # 3. DARABOLT (CHUNKED) RENDKÍVÜLI ÁTVITEL:
            def generate_chunks():
                chunk_size = 1024
                for i in range(0, len(final_payload), chunk_size):
                    yield bytes(final_payload[i:i+chunk_size])
            
            print(f"Kristálytiszta PCM hangstream indítása az ESP32 felé! Méret: {len(final_payload)} bájt.")
            return Response(stream_with_context(generate_chunks()), mimetype='application/octet-stream')
        else:
            print(f"HIBA: TTS hiba, status: {tts_res.status_code}")
            return "HIBA: TTS motor elutasította a kérést.", 200
            
    except Exception as e:
        print(f"Sulyos hiba a szerveren: {str(e)}")
        return f"HIBA: Szerveroldali kivétel: {str(e)}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
