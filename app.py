import os
import requests
import base64
from flask import Flask, request, jsonify

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

@app.route('/')
def index():
    return "A kozponti hangfeldolgozo szerver aktiv!"

@app.route('/upload', methods=['GET', 'POST'])
def process_audio():
    # Az ESP32 elküldi a saját belső IP-jét paraméterként (pl. 192.168.1.137)
    esp32_ip = request.args.get('ip')
    
    if not esp32_ip:
        return "Hianyzik az ESP32 IP cime.", 400
        
    if not GEMINI_API_KEY:
        return "A GEMINI_API_KEY nincs beallitva a Renderen.", 500

    try:
        # Letöltjük a hangot az ESP32-től a kapott IP-cím alapján
        esp_url = f"http://{esp32_ip}/get_audio"
        print(f"Hang letoltese innen: {esp_url}")
        esp_response = requests.get(esp_url, timeout=12)
        
        if esp_response.status_code != 200:
            return "Az ESP32-n nem talalhato hangfajl.", 400
            
        audio_data = esp_response.content
        print(f"Sikeres letoltes! Meret: {len(audio_data)} bajt.")

        # Beküldés a Google Gemini 1.5 Flash API-nak
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

        print("Kuldes a Gemini-nek...")
        gemini_response = requests.post(gemini_url, json=payload, timeout=15)
        
        if gemini_response.status_code == 200:
            reply = gemini_response.json()["candidates"][0]["content"]["parts"][0]["text"]
            print(f"Sikeres valasz: {reply}")
            return reply
        else:
            return f"Gemini API hiba: {gemini_response.status_code}"

    except Exception as e:
        print(f"Hiba: {str(e)}")
        return "Szerveroldali hiba tortent."

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
