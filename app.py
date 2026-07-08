import os
import requests
import base64
from flask import Flask, request

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

@app.route('/')
def index():
    return "A kozponti hangfeldolgozo szerver aktiv es kesz a fogadasra!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY:
        print("HIBA: A GEMINI_API_KEY nincs beallitva a Renderen.")
        return "Szerveroldali konfiguracios hiba.", 500

    try:
        audio_data = request.data
        if not audio_data or len(audio_data) < 1000:
            print(f"HIBA: Túl rövid adat érkezett! Méret: {len(audio_data)} bájt.")
            return "Ures vagy hibas hangfajl.", 400
            
        print(f"Sikeresen beerkezett a hang az ESP-rol! Meret: {len(audio_data)} bajt.")

        gemini_url = f"https://googleapis.com{GEMINI_API_KEY}"
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')

        payload = {
            "contents": [{
                "parts": [
                    {"text": "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul!"},
                    {"inlineData": {"mimeType": "audio/pcm;rate=16000", "data": audio_base64}}
                ]
            }]
        }

        headers = {"Content-Type": "application/json"}
        print("Kuldes a Gemini API-nak...")
        gemini_response = requests.post(gemini_url, json=payload, headers=headers, timeout=15)
        
        if gemini_response.status_code == 200:
            res_json = gemini_response.json()
            print(f"Nyers Gemini valasz: {res_json}")
            
            # ATOMBIZTOS JAVÍTÁS: A Gemini 1.5 Flash tömbstruktúrájának precíz, indexelt kibontása
            try:
                reply = res_json["candidates"][0]["content"]["parts"][0]["text"]
                print(f"Sikeres kibontas! Valasz: {reply}")
                return reply
            except (KeyError, IndexError, TypeError) as e:
                print(f"JSON struktura hiba a valasz kibontásakor: {str(e)}")
                return "Hiba a valasz kicsomagolasakor."
        else:
            print(f"Gemini API hiba: {gemini_response.status_code} - {gemini_response.text}")
            return "Gemini API hiba tortent."

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        return "Szerveroldali hiba tortent.", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
