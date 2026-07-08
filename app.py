import os
import io
import wave
import base64
import requests
from flask import Flask, request, Response

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
        return "HIBA: Hianyzik a Gemini kulcs a Render beallitasaibol.", 200
    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000: 
            return "HIBA: Ures vagy hibas hangfajl erkezett.", 200
        
        print(f"Mikrofonhang beerkezett az ESP-ről: {len(pcm_data)} bajt.")

        # 1. Mikrofon PCM -> WAV konverzió a Gemini bemenetének
        wav_data = pcm_to_wav(pcm_data, sample_rate=16000)
        audio_base64 = base64.b64encode(wav_data).decode('utf-8')

        # 2. HTTP POST kérés a Gemini 2.5 Flash felé
        gemini_url = f"https://googleapis.com{GEMINI_API_KEY}"
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Valaszolj a hallott hangra tisztan magyarul, nagyon roviden, ekezetek nelkul, maximum 4-5 szoban!"},
                    {"inlineData": {"mimeType": "audio/wav", "data": audio_base64}}
                ]
            }],
            "generation_config": {
                "response_mime_type": "audio/wav",
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {
                            "voice_name": "Puck" 
                        }
                    }
                }
            }
        }

        print("Küldés a Google Gemini felé HANG generálásra...")
        headers = {"Content-Type": "application/json"}
        gemini_response = requests.post(gemini_url, json=payload, headers=headers, timeout=20)
        
        if gemini_response.status_code == 200:
            res_json = gemini_response.json()
            
            audio_bytes = None
            try:
                def find_audio_data(d):
                    if isinstance(d, dict):
                        for k, v in d.items():
                            if k == 'inlineData' and isinstance(v, dict) and 'data' in v:
                                return base64.b64decode(v['data'])
                            elif k == 'data' and isinstance(v, str) and len(v) > 2000:
                                try: return base64.b64decode(v)
                                except Exception: pass
                            ret = find_audio_data(v)
                            if ret: return ret
                    elif isinstance(d, list):
                        for item in d:
                            ret = find_audio_data(item)
                            if ret: return ret
                    return None
                
                audio_bytes = find_audio_data(res_json)
            except Exception as json_e:
                print(f"Hiba a JSON parsolas közben: {str(json_e)}")

            if audio_bytes:
                # Levágjuk az első 44 bájtot (WAV fejléc), hogy tiszta PCM bájtokat kapjunk
                pcm_clean = audio_bytes[44:] if len(audio_bytes) > 44 else audio_bytes
                print(f"A Gemini gyári hangválasza kész! Méret: {len(pcm_clean)} bájt.")
                
                # JAVÍTVA: Fix, kényszerített Content-Length fejléc, hogy az ESP pontosan tudja, mikor kell leállnia!
                return Response(
                    bytes(pcm_clean),
                    mimetype='application/octet-stream',
                    headers={'Content-Length': str(len(pcm_clean))}
                )
            else:
                return "HIBA: Nem erkezett hangadat a Google-tol.", 200
        else:
            return f"HIBA: Google API hiba ({gemini_response.status_code}).", 200
            
    except Exception as e:
        return f"HIBA: Szerveroldali hiba: {str(e)}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
