import os
import io
import wave
import base64
import requests
import urllib.parse
from flask import Flask, request, jsonify

app = Flask(__name__)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

GEMINI_URL = "https://googleapis.com"

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
    return "A kozponti stabil JSON PCM hang- es szovegserver aktiv!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY: 
        return jsonify({"text": "HIBA: Hianyzik az API kulcs.", "audio": []}), 200
        
    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000: 
            return jsonify({"text": "HIBA: Ures hangadat.", "audio": []}), 200
            
        print(f"Mikrofonhang beerkezett: {len(pcm_data)} bajt. Kuldes a Gemininek...")

        # 1. Gemini kérés a sziklaszilárd közvetlen REST JSON formátummal (MimeType x-wav az éles STT-hez)
        wav_bytes = pcm_to_wav(pcm_data, sample_rate=16000)
        audio_base64 = base64.b64encode(wav_bytes).decode('utf-8')
        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()
        
        payload = {
            "contents": [{
                "parts": [
                    {"inlineData": {"mimeType": "audio/x-wav", "data": audio_base64}},
                    {"text": "Valaszolj a hallott hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 4-5 szoban!"}
                ]
            }]
        }

        headers = {"Content-Type": "application/json"}
        gemini_response = requests.post(GEMINI_URL, params={"key": clean_key}, json=payload, headers=headers, timeout=25)
        
        if gemini_response.status_code == 200:
            res_json = gemini_response.json()
            try:
                reply_text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception:
                reply_text = "Rendben"
            print(f"Gemini sikeres valasza: {reply_text}")
        else:
            print(f"Google API Hiba: {gemini_response.text}")
            return jsonify({"text": f"Google hiba ({gemini_response.status_code})", "audio": []}), 200

        # 2. KRISTÁLYTISZTA GYÁRI PCM HANGGENERÁLÁS (Tömörítés nélküli tiszta PCM-16 bájtok!)
        encoded_text = urllib.parse.quote(reply_text)
        pcm_tts_url = "https://voicerss.org"
        params = {
            "key": "e46d89269d054e2ea854743ec3416c14",
            "hl": "hu-hu",
            "c": "PCM",
            "f": "16khz_16bit_mono",
            "src": reply_text
        }
        
        tts_res = requests.get(pcm_tts_url, params=params, timeout=12)
        
        audio_list = []
        if tts_res.status_code == 200:
            raw_pcm_audio = tts_res.content
            # Tisztán levágjuk a 44 bájtos WAV fejlécet, hogy csak a tiszta hanghullám bájtok maradjanak
            clean_audio_bytes = raw_pcm_audio[44:] if len(raw_pcm_audio) > 44 else raw_pcm_audio
            
            # Két bájtonként haladva pontos előjeles 16 bites számokká alakítjuk az I2S részére
            for i in range(0, len(clean_audio_bytes), 2):
                if i+1 < len(clean_audio_bytes):
                    sample = int((clean_audio_bytes[i+1] << 8) | clean_audio_bytes[i])
                    if sample > 32767: sample -= 65536
                    audio_list.append(sample)
            print(f"Gyári PCM beszédhang sikeresen kinyerve! Hossza: {len(audio_list)} minta.")
        else:
            print(f"HIBA: TTS hiba, status: {tts_res.status_code}")

        return jsonify({
            "text": reply_text,
            "audio": audio_list
        }), 200
            
    except Exception as e:
        print(f"Szerver hiba: {str(e)}")
        return jsonify({"text": f"Szerver hiba: {str(e)}", "audio": []}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
