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
    return "A vegleges direkt Gemini PCM hang- es szovegserver aktiv!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY:
        return jsonify({"error": "missing_gemini_api_key"}), 500

    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000:
            return jsonify({"error": "empty_audio"}), 400

        wav_bytes = pcm_to_wav(pcm_data, sample_rate=16000)
        audio_base64 = base64.b64encode(wav_bytes).decode('utf-8')

        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()

        gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Valaszolj magyarul, nagyon roviden, ekezetek nelkul."},
                    {
                        "inlineData": {
                            "mimeType": "audio/wav",
                            "data": audio_base64
                        }
                    }
                ]
            }]
        }

        headers = {"Content-Type": "application/json"}
        gemini_response = requests.post(
            gemini_url,
            params={"key": clean_key},
            json=payload,
            headers=headers,
            timeout=25
        )

        if gemini_response.status_code != 200:
            return jsonify({
                "error": "gemini_error",
                "status_code": gemini_response.status_code,
                "details": gemini_response.text
            }), 200

        res_json = gemini_response.json()
        reply_text = "rendben"

        try:
            reply_text = res_json["candidates"][0]["content"]["parts"][0].get("text", "rendben").strip()
        except Exception:
            pass

        return jsonify({
            "text": reply_text
        }), 200

    except Exception as e:
        return jsonify({
            "error": "server_error",
            "details": str(e)
        }), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
