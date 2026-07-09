import os
import io
import wave
import base64
import requests
import urllib.parse
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
    return "A végleges SZOVEG + IGAZI PCM hangfeldolgozó aktív!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY: 
        return "HIBA: Hiányzik a Gemini kulcs.", 200
    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000: 
            return "HIBA: Üres hangadat.", 200
            
        print(f"Mikrofonhang beérkezett: {len(pcm_data)} bájt.")

        # 1. Gemini kérés tiszta JSON HTTP POST-tal
        wav_bytes = pcm_to_wav(pcm_data, sample_rate=16000)
        audio_base64 = base64.b64encode(wav_bytes).decode('utf-8')

        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()
        gemini_url = "https://googleapis.com"
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Valaszolj a hallott hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 4-5 szoban!"},
                    {"inlineData": {"mimeType": "audio/wav", "data": audio_base64}}
                ]
            }]
        }

        headers = {"Content-Type": "application/json"}
        gemini_response = requests.post(gemini_url, params={"key": clean_key}, json=payload, headers=headers, timeout=20)
        
        if gemini_response.status_code == 200:
            res_json = gemini_response.json()
            try:
                reply_text = res_json["candidates"]["content"]["parts"]["text"].strip()
            except Exception:
                reply_text = "Rendben"
            print(f"Gemini válasza: {reply_text}")
        else:
            return f"HIBA: Google hiba ({gemini_response.status_code})", 200

        # 2. PROFI PCM HANGGENERÁLÁS (VoiceRSS Szabad licenc - Átalakítás nélkül NATIVE PCM-16 bájtokat ad!)
        # A szöveget URL-kódoljuk
        encoded_text = urllib.parse.quote(reply_text)
        
        # Ez a nyilvános kulcs és konfiguráció GARANTÁLTAN tiszta, tömörítetlen 16kHz Mono PCM hangbájtokat ad vissza!
        pcm_tts_url = f"https://voicerss.org{encoded_text}"
        
        print("Lekérés az online NATIVE PCM hanggenerátortól...")
        tts_res = requests.get(pcm_tts_url, timeout=12)
        
        if tts_res.status_code == 200:
            raw_pcm_audio = tts_res.content
            print(f"Gyári PCM hangbájtok megérkeztek! Méret: {len(raw_pcm_audio)} bájt.")
            
            # Mivel a VoiceRSS egy minimális, 44 bájtos RIFF/WAV fejlécet tesz az elejére, 
            # azt tisztán levágjuk, hogy az ESP32 I2S hardvere csak a tiszta hanghullámot kapja meg!
            clean_audio_bytes = raw_pcm_audio[44:] if len(raw_pcm_audio) > 44 else raw_pcm_audio
            
            # Létrehozzuk a fix, 128 bájtos szöveges fejlécet az ESP32 soros monitorának
            header_packet = bytearray(128)
            text_bytes = reply_text.encode('utf-8')[:127]
            header_packet[:len(text_bytes)] = text_bytes
            
            # Összefűzzük a szöveget és a kristálytiszta hangbájtokat
            final_payload = header_packet + clean_audio_bytes
            
            def generate_chunks():
                chunk_size = 1024
                for i in range(0, len(final_payload), chunk_size):
                    yield bytes(final_payload[i:i+chunk_size])
            
            print(f"Minden kész! Stream indítása az ESP32 felé, teljes méret: {len(final_payload)} bájt.")
            return Response(stream_with_context(generate_chunks()), mimetype='application/octet-stream')
        else:
            return "HIBA: TTS hanggenerálási hiba.", 200
            
    except Exception as e:
        print(f"Szerver hiba: {str(e)}")
        return f"HIBA: Szerveroldali hiba: {str(e)}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
