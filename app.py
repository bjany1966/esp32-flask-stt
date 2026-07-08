import os
import requests
from flask import Flask, request, send_file, Response

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

@app.route('/')
def index():
    return "A kozponti hangfeldolgozo szerver aktiv es mukodik!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY:
        return "HIBA: Hianyzik a Gemini API kulcs.", 200

    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000:
            return "HIBA: Ures vagy hibas hangfajl erkezett.", 200
            
        print(f"Beérkezett mikrofonhang az ESP-ről: {len(pcm_data)} bájt.")

        # 1. Nyers PCM -> WAV átalakítás kézzel a kéréshez
        import io
        import wave
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(pcm_data)
        wav_bytes = wav_io.getvalue()

        # 2. Közvetlen HTTP kérést indítunk a Google felé, kérve a HANG kimenetet
        # Ezzel megkerüljük az SDK belső JSON-kicsomagolási hibáit!
        gemini_url = f"https://googleapis.com{GEMINI_API_KEY}"
        
        import base64
        audio_base64 = base64.b64encode(wav_bytes).decode('utf-8')

        payload = {
            "contents": [{
                "parts": [
                    {"text": "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 5-6 szoban!"},
                    {"inlineData": {"mimeType": "audio/wav", "data": audio_base64}}
                ]
            }],
            # Ez a kritikus beállítás kényszeríti a Google-t, hogy HANGOT gyártson szöveg helyett!
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": "Puck" # Kiváló minőségű férfi hangszín
                        }
                    }
                }
            }
        }

        print("Küldés a Google Gemini felé...")
        response = requests.post(gemini_url, json=payload, timeout=20)
        
        if response.status_code == 200:
            res_json = response.json()
            
            # Kézzel és biztonságosan lehalásszuk a hangbájtokat a struktúrából
            try:
                base64_audio_out = res_json["candidates"][0]["content"]["parts"][1]["inlineData"]["data"]
                raw_audio_out = base64.b64decode(base64_audio_out)
                
                print(f"A Gemini igazi hangválasza megérkezett! Méret: {len(raw_audio_out)} bájt.")
                
                # Levágjuk az első 44 bájtot (WAV fejléc), hogy az ESP32 tiszta nyers PCM bájtokat kapjon
                if len(raw_audio_out) > 44:
                    return Response(raw_audio_out[44:], mimetype='application/octet-stream')
                return Response(raw_audio_out, mimetype='application/octet-stream')
            except Exception as e:
                print(f"Struktúra hiba, de a válasz megjött: {res_json}")
                return "HIBA: Nem talalhato hangadat a valaszban.", 200
        else:
            print(f"Google Hiba: {response.text}")
            return f"HIBA: Google API hiba ({response.status_code})", 200

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        return f"HIBA: Szerveroldali hiba: {str(e)}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
