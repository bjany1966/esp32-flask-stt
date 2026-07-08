import os
import requests
import base64
from flask import Flask, request

app = Flask(__name__)

# A kulcsot a Render környezeti változóiból olvassuk be
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

@app.route('/')
def index():
    return "A kozponti hangfeldolgozo szerver aktiv es mukodik!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY:
        print("HIBA: A GEMINI_API_KEY nincs beallitva a Renderen.")
        return "HIBA: Hianyzik a Gemini API kulcs a Render beallitasaibol.", 200

    try:
        audio_data = request.data
        if not audio_data or len(audio_data) < 1000:
            print(f"HIBA: Tul rovid adat erkezett! Meret: {len(audio_data)} bajt.")
            return "HIBA: Tul rovid vagy ures hangfajl erkezett.", 200
            
        print(f"Sikeresen beerkezett a hang az ESP-rol! Meret: {len(audio_data)} bajt.")

        # FRISSÍTVE: v1beta helyett a stabil v1-es vegvonalat hasznaljuk a 404 hiba ellen!
        gemini_url = "https://googleapis.com"
        
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')

        payload = {
            "contents": [{
                "parts": [
                    {"text": "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 5-6 szoban!"},
                    {"inlineData": {"mimeType": "audio/pcm;rate=16000", "data": audio_base64}}
                ]
            }]
        }

        clean_key = str(GEMINI_API_KEY).strip()
        params = {"key": clean_key}
        headers = {"Content-Type": "application/json"}
        
        print("Kuldes a Gemini API-nak...")
        gemini_response = requests.post(gemini_url, params=params, json=payload, headers=headers, timeout=15)
        
        if gemini_response.status_code != 200:
            print(f"Gemini API hiba: {gemini_response.status_code} - {gemini_response.text}")
            return f"HIBA: Gemini hiba ({gemini_response.status_code}). Valasz: {gemini_response.text[:80]}", 200

        res_json = gemini_response.json()
        print(f"Nyers Gemini valasz: {res_json}")
        
        # Szigorú és biztonságos JSON ellenőrzés a válasz kibontásához
        if "candidates" in res_json and len(res_json["candidates"]) > 0:
            candidate = res_json["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"] and len(candidate["content"]["parts"]) > 0:
                part = candidate["content"]["parts"][0]
                if "text" in part:
                    reply = part["text"].strip()
                    print(f"Sikeres kibontas! Valasz: {reply}")
                    return reply

        return "HIBA: A Gemini valasza ures vagy rossz formatumu.", 200

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        return f"HIBA: Szerveroldali hiba: {str(e)}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
