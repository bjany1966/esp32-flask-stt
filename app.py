import os
import requests
from flask import Flask, jsonify

app = Flask(__name__)

# --- BIZTONSÁGOS BEÁLLÍTÁSOK ---
ESP32_IP = "192.168.1.169"  # Az ESP32-S3 kártyád helyi IP címe

# Az API kulcsot kizárólag a Render környezeti változóiból olvassuk be!
# A GitHubra feltöltött kódban NEM szerepel a titkos kulcs.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

@app.route('/')
def index():
    return "Az STT / Gemini Központi Szerver Fut!"

@app.route('/upload', methods=['POST', 'GET'])
def trigger_and_process():
    try:
        # Biztonsági ellenőrzés: ha elfelejtetted beállítani a Renderen a kulcsot, figyelmeztet
        if not GEMINI_API_KEY:
            print("HIBA: A GEMINI_API_KEY környezeti változó nincs beállítva a Render.com-on!")
            return "Szerveroldali konfiguracios hiba."

        # 1. Lekérjük a nyers PCM hangfájlt az ESP32 helyi webszerverétől
        print(f"Kapcsolódás az ESP32-höz: http://{ESP32_IP}/get_audio ...")
        esp_response = requests.get(f"http://{ESP32_IP}/get_audio", timeout=10)
        
        if esp_response.status_code != 200:
            return jsonify({"status": "error", "message": "Az ESP32 még nem rögzített hangot."}), 400
        
        audio_data = esp_response.content
        print(f"Hangfájl sikeresen letöltve az ESP-ről! Méret: {len(audio_data)} bájt.")

        # 2. Küldés közvetlenül a Google Gemini API-nak
        gemini_url = f"https://googleapis.com{GEMINI_API_KEY}"
        
        import base64
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
        print("Küldés a Gemini API-nak...")
        gemini_response = requests.post(gemini_url, json=payload, headers=headers, timeout=15)
        
        if gemini_response.status_code == 200:
            res_json = gemini_response.json()
            text_reply = res_json["candidates"]["content"]["parts"]["text"]
            print(f"Gemini válasza: {text_reply}")
            return text_reply
        else:
            print(f"Gemini Hiba: {gemini_response.text}")
            return "Hiba a Gemini kapcsolatban."

    except Exception as e:
        print(f"Szerveroldali hiba: {str(e)}")
        return "Szerveroldali hiba tortent."

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
