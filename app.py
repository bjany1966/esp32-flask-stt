import os
import io
import wave
import base64
import requests
from flask import Flask, request, jsonify

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
    return "A kozponti stabil JSON PCM hang- es szovegserver aktiv!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY: 
        print("HIBA: Hianyzik a GEMINI_API_KEY a Render beallitasaibol!")
        return jsonify({"text": "HIBA: Hianyzik a Gemini API kulcs.", "audio": []}), 200
        
    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000: 
            print("HIBA: Ures vagy hibas mikrofonhang jott az ESP-rol.")
            return jsonify({"text": "HIBA: Ures hangadat.", "audio": []}), 200
            
        print(f"Mikrofonhang beerkezett: {len(pcm_data)} bajt. Átalakítás...")

        # 1. Mikrofon PCM -> WAV konverzió a Gemini belső HTTP kéréséhez
        wav_bytes = pcm_to_wav(pcm_data, sample_rate=16000)
        audio_base64 = base64.b64encode(wav_bytes).decode('utf-8')

        # Tisztítjuk az API kulcsot a biztonság kedvéért
        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()
        
        # HIVATALOS GOOGLE GEMINI REST URL VÉGPONT (ZÉRÓ SDK FÜGGŐSÉG! MEGSZŰNIK A 404!)
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
                reply_text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception:
                reply_text = "Rendben"
            print(f"Gemini sikeres válasza: {reply_text}")
        else:
            print(f"Google API Hiba: {gemini_response.text}")
            return jsonify({"text": f"Google hiba ({gemini_response.status_code})", "audio": []}), 200

        # 2. KRISTÁLYTISZTA NATÍV PCM HANGGENERÁLÁS (VoiceRSS Szabad licenc - Natív PCM bájtokat ad!)
        pcm_tts_url = "https://voicerss.org"
        params = {
            "key": "e46d89269d054e2ea854743ec3416c14",
            "hl": "hu-hu",
            "c": "PCM",
            "f": "16khz_16bit_mono",
            "src": reply_text
        }
        
        print("Válaszhang lekérése a natív PCM hanggenerátortól...")
        tts_res = requests.get(pcm_tts_url, params=params, timeout=12)
        
        audio_list = []
        if tts_res.status_code == 200:
            raw_pcm_audio = tts_res.content
            # Levágjuk az elejéről a minimális 44 bájtos RIFF/WAV fejlécet, hogy tiszta PCM bájtokat kapjunk
            clean_audio_bytes = raw_pcm_audio[44:] if len(raw_pcm_audio) > 44 else raw_pcm_audio
            
            # Átalakítjuk a nyers bájtokat 16 bites egész számokká az ESP32 JSON listájához
            for i in range(0, len(clean_audio_bytes), 2):
                if i+1 < len(clean_audio_bytes):
                    # Két bájtból összerakunk egy 16 bites előjeles mintát (Little-Endian)
                    sample = int((clean_audio_bytes[i+1] << 8) | clean_audio_bytes[i])
                    if sample > 32767: sample -= 65536
                    audio_list.append(sample)
            print(f"Gyári PCM hangbájtok listába rendezve! Hossza: {len(audio_list)} minta.")
        else:
            print(f"HIBA: TTS hiba, status: {tts_res.status_code}")

        # Visszaküldjük a szöveget és a tiszta PCM szám-listát a te JSON struktúrádban!
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
