import os
import io
import wave
import base64
import time
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://googleapis.com{GEMINI_MODEL}:generateContent"

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
    return "A kombinált JSON + BASE64 MP3 hangasszisztens szerver aktív!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY:
        return jsonify({"text": "HIBA: missing_api_key", "audio": ""}), 200

    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000:
            return jsonify({"text": "HIBA: empty_audio", "audio": ""}), 200

        wav_bytes = pcm_to_wav(pcm_data, sample_rate=16000)
        audio_base64 = base64.b64encode(wav_bytes).decode('utf-8')
        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()

        payload = {
            "contents": [{
                "parts": [
                    {"text": "Valaszolj magyarul, nagyon roviden, ekezetek nelkul, maximum 4-5 szoban!"},
                    {"inlineData": {"mimeType": "audio/wav", "data": audio_base64}}
                ]
            }]
        }

        headers = {"Content-Type": "application/json"}

        reply_text = "Rendben"
        last_error = None
        
        # A te szuper 3-szoros újrapróbálkozási ciklusod
        for attempt in range(3):
            resp = requests.post(GEMINI_URL, params={"key": clean_key}, json=payload, headers=headers, timeout=25)

            if resp.status_code == 200:
                res_json = resp.json()
                try:
                    def find_text_in_json(d):
                        if isinstance(d, dict):
                            for k, v in d.items():
                                if k == 'text' and isinstance(v, str): return v
                                ret = find_text_in_json(v)
                                if ret: return ret
                        elif isinstance(d, list):
                            for item in d:
                                ret = find_text_in_json(item)
                                if ret: return ret
                        return None
                    extracted_text = find_text_in_json(res_json)
                    if extracted_text: reply_text = extracted_text.strip()
                except Exception:
                    pass
                break
            
            last_error = {"status_code": resp.status_code, "details": resp.text}
            if resp.status_code != 429: break
            time.sleep(1.5 * (attempt + 1))

        if last_error and resp.status_code != 200:
            return jsonify({"text": f"Google hiba ({last_error['status_code']})", "audio": ""}), 200

        # 2. TTS HANGGENERÁLÁS (Google Translate tiszta MP3)
        tts_url = "https://google.com"
        headers_tts = {"User-Agent": "Mozilla/5.0"}
        params = {"ie": "UTF-8", "tl": "hu", "client": "tw-ob", "q": reply_text}
        tts_res = requests.get(tts_url, params=params, headers=headers_tts, timeout=12)
        
        audio_encoded = ""
        if tts_res.status_code == 200:
            # Az MP3 bájtokat Base64 szöveggé alakítjuk a biztonságos JSON átvitelhez
            audio_encoded = base64.b64encode(tts_res.content).decode('utf-8')
            print(f"Sikeres hanggenerálás! MP3 mérete: {len(tts_res.content)} bájt.")

        # Visszaküldjük a szöveget ÉS a Base64 kódolt MP3 hangot együtt!
        return jsonify({
            "text": reply_text,
            "audio": audio_encoded
        }), 200

    except Exception as e:
        return jsonify({"text": f"Szerver hiba: {str(e)}", "audio": ""}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
