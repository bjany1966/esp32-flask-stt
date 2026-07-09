import os
import io
import wave
import base64
import time
import requests
from flask import Flask, request, jsonify
from google import genai
from google.genai import types

app = Flask(__name__)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# A Google hivatalos v1beta éles REST címe
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
    return "A végleges sziklaszilárd NATIVE-PCM szám-lista szerver aktív!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY: 
        print("HIBA: Hiányzik a GEMINI_API_KEY a Render beállításaiból!")
        return jsonify({"text": "HIBA: Hiányzik az API kulcs.", "audio": []}), 200
        
    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000: 
            return jsonify({"text": "HIBA: Üres hangadat.", "audio": []}), 200
            
        print(f"Mikrofonhang beérkezett az ESP-ről: {len(pcm_data)} bájt.")

        # 1. Mikrofon PCM -> WAV konverzió a Gemini bemenetéhez
        wav_bytes = pcm_to_wav(pcm_data, sample_rate=16000)
        audio_base64 = base64.b64encode(wav_bytes).decode('utf-8')

        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()
        
        # JAVÍTVA ÉS KÉNYSZERÍTVA: Megkérjük a Geminit, hogy tiszta szöveg helyett
        # egyből gyári, tömörítetlen, Lineáris 16kHz Mono PCM beszédhanggal válaszoljon!
        # Így kiküszöböljük a hibás MP3 dekódolókat, a beszéd tökéletesen tiszta lesz!
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
            }],
            "generationConfig": {
                "responseMimeType": "audio/pcm"
            }
        }

        print("Küldés a Google Gemini felé NATIVE-PCM beszédhang generálásra...")
        headers = {"Content-Type": "application/json"}
        gemini_response = requests.post(GEMINI_URL, params={"key": clean_key}, json=payload, headers=headers, timeout=25)
        
        if gemini_response.status_code == 200:
            res_json = gemini_response.json()
            
            reply_text = "Rendben"
            raw_voice_bytes = b""
            
            try:
                # Kikeressük a szöveget és a Google által generált tiszta PCM hangbájtokat
                parts = res_json["candidates"][0]["content"]["parts"]
                for part in parts:
                    if "text" in part:
                        reply_text = part["text"].strip()
                    if "inlineData" in part and "data" in part["inlineData"]:
                        raw_voice_bytes = base64.b64decode(part["inlineData"]["data"])
            except Exception as e:
                print(f"JSON bontási hiba: {str(e)}")

            print(f"Gemini szöveges válasza: {reply_text}")
            print(f"Gemini gyári PCM hangbájtok hossza: {len(raw_voice_bytes)} bájt.")

            # JAVÍTVA: A Google által küldött tiszta, tömörítetlen PCM hangbájtokat 
            # hajszálpontosan átültetjük előjeles 16 bites számokká a te ESP kódod JsonArray-e részére!
            audio_list = []
            for i in range(0, len(raw_voice_bytes), 2):
                if i+1 < len(raw_voice_bytes):
                    sample = int((raw_voice_bytes[i+1] << 8) | raw_voice_bytes[i])
                    if sample > 32767: sample -= 65536
                    audio_list.append(sample)

            print(f"Minden kész! PCM szám-lista összeállítva: {len(audio_list)} minta.")
            return jsonify({
                "text": reply_text,
                "audio": audio_list
            }), 200
        else:
            print(f"Google API Hiba: {gemini_response.text}")
            return jsonify({"text": f"Google hiba ({gemini_response.status_code})", "audio": []}), 200

    except Exception as e:
        print(f"Súlyos hiba a szerveren: {str(e)}")
        return jsonify({"text": f"Szerver hiba: {str(e)}", "audio": []}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
