import os
import io
import wave
import base64
import requests
from flask import Flask, request, Response, stream_with_context

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
    return "A kozponti direkt Gemini HANG streamelo szerver aktiv!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY: 
        return "Hianyzik a Gemini kulcs", 500
    try:
        pcm_data = request.data
        if not pcm_data: return "Ures hang", 400
        
        print(f"Mikrofonhang beerkezett az ESP-ről: {len(pcm_data)} bajt.")

        # 1. Mikrofon PCM -> WAV konverzió a Gemini bemenetének
        wav_data = pcm_to_wav(pcm_data, sample_rate=16000)
        audio_base64 = base64.b64encode(wav_data).decode('utf-8')

        # 2. Közvetlen HTTP kérés a Gemini 2.5 Flash felé - HANG kimenetet kérve szöveg helyett!
        gemini_url = f"https://googleapis.com{GEMINI_API_KEY}"
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Valaszolj a hallott hangra tisztan magyarul, nagyon roviden, ekezetek nelkul, maximum 5-6 szoban!"},
                    {"inlineData": {"mimeType": "audio/wav", "data": audio_base64}}
                ]
            }],
            # Ez a konfiguráció kényszeríti a Geminit, hogy HANGOT gyártson válaszként!
            "generationConfig": {
                "responseMimeType": "audio/wav",
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": "Puck" # Kiváló minőségű, tiszta férfi beszédhang
                        }
                    }
                }
            }
        }

        print("Küldés a Google Gemini felé HANG generálásra...")
        gemini_response = requests.post(gemini_url, json=payload, timeout=20)
        
        if gemini_response.status_code == 200:
            res_json = gemini_response.json()
            
            # Kikeressük a Google által visszaküldött nyers hangbájtokat a JSON struktúrából
            try:
                base64_audio_out = res_json["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
                raw_audio_out = base64.b64decode(base64_audio_out)
                print(f"A Gemini gyári WAV hangválasza megérkezett! Méret: {len(raw_audio_out)} bájt.")
                
                # Levágjuk az első 44 bájtot (WAV fejléc), hogy az ESP32 tiszta, lineáris PCM hangbájtokat kapjon
                pcm_clean = raw_audio_out[44:] if len(raw_audio_out) > 44 else raw_audio_out
            except Exception as e:
                print(f"Nem sikerült kivenni a hangot a JSON-ból: {str(e)}. Nyers válasz: {res_json}")
                return "JSON hiba", 500

            # 3. DARABOLT (CHUNKED) ÁTVITEL: 
            # 1024 bájtos darabokban (chunk) küldjük vissza a tiszta PCM hangot, hogy az ESP-nek ne fogyjon el a RAM-ja
            def generate_chunks():
                chunk_size = 1024
                for i in range(0, len(pcm_clean), chunk_size):
                    yield bytes(pcm_clean[i:i+chunk_size])
            
            print(f"Kristálytiszta PCM hangstream indítása az ESP32-nek... Méret: {len(pcm_clean)} bájt.")
            return Response(stream_with_context(generate_chunks()), mimetype='application/octet-stream')
            
        else:
            print(f"Google API Hiba: {gemini_response.text}")
            return "Google API Hiba", 500
            
    except Exception as e:
        print(f"Szerveroldali hiba: {str(e)}")
        return "Szerver hiba", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
