import os
import io
import wave
import base64
import requests
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
    return "A kozponti stabil JSON szoveges Gemini szerver aktiv!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY: 
        print("HIBA: Hianyzik a GEMINI_API_KEY a Render beallitasaibol!")
        return jsonify({"text": "HIBA: Hianyzik a Gemini API kulcs.", "audio": []}), 200
        
    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000: 
            print("HIBA: Ures mikrofonhang jott.")
            return jsonify({"text": "HIBA: Ures hangadat.", "audio": []}), 200
            
        print(f"Mikrofonhang beerkezett: {len(pcm_data)} bajt.")

        # Mikrofon nyers PCM -> WAV konverzió a Gemini bemenetéhez
        wav_bytes = pcm_to_wav(pcm_data, sample_rate=16000)
        audio_base64 = base64.b64encode(wav_bytes).decode('utf-8')

        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()
        
        # Atombiztos, standard Google REST JSON struktúra (Nincs többé 404!)
        payload = {
            "contents": [{
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": "audio/x-wav", 
                            "data": audio_base64
                        }
                    },
                    {
                        "text": "Valaszolj a hallott hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 4-5 szoban!"
                    }
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
            print(f"Gemini sikeres válasza: {reply_text}")
            
            # Visszaküldjük a tiszta szöveget, az audio listát pedig szándékosan üresen hagyjuk,
            # mert az ESP32 helyben fogja legenerálni a tiszta beszédhangot!
            return jsonify({
                "text": reply_text,
                "audio": []
            }), 200
        else:
            print(f"Google API Hiba: {gemini_response.text}")
            return jsonify({"text": f"Google hiba ({gemini_response.status_code})", "audio": []}), 200

    except Exception as e:
        print(f"Szerver hiba: {str(e)}")
        return jsonify({"text": f"Szerver hiba: {str(e)}", "audio": []}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
