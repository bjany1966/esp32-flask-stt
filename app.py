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
        return "HIBA: Hianyzik a Gemini kulcs a Render beallitasaibol.", 200
    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000: 
            return "HIBA: Ures vagy hibas hangfajl erkezett.", 200
        
        print(f"Mikrofonhang beerkezett az ESP-ről: {len(pcm_data)} bajt.")

        # 1. Mikrofon PCM -> WAV konverzió a Gemini bemenetének
        wav_data = pcm_to_wav(pcm_data, sample_rate=16000)
        audio_base64 = base64.b64encode(wav_data).decode('utf-8')

        # 2. Közvetlen HTTP kérés a Gemini 2.5 Flash felé - HANG kimenetet kérve szöveg helyett!
        gemini_url = f"https://googleapis.com{GEMINI_API_KEY}"
        
        # JAVÍTVA: A Google által elvárt hajszálpontos alsó vonalas JSON kulcsnevek (response_mime_type és speech_config)
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Valaszolj a hallott hangra tisztan magyarul, nagyon roviden, ekezetek nelkul, maximum 5-6 szoban!"},
                    {"inlineData": {"mimeType": "audio/wav", "data": audio_base64}}
                ]
            }],
            "generation_config": {
                "response_mime_type": "audio/wav",
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {
                            "voice_name": "Puck" # Kiváló minőségű, tiszta férfi beszédhang
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
            
            # Mély, univerzális kereső a hangbájtok kinyeréséhez a JSON-ból
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
                print(f"A Gemini gyári WAV hangválasza sikeresen kicsomagolva! Méret: {len(audio_bytes)} bájt.")
                # Levágjuk az első 44 bájtot (WAV fejléc), hogy az ESP32 tiszta, lineáris PCM hangbájtokat kapjon
                pcm_clean = audio_bytes[44:] if len(audio_bytes) > 44 else audio_bytes
                
                # 3. DARABOLT (CHUNKED) ÁTVITEL: 
                def generate_chunks():
                    chunk_size = 1024
                    for i in range(0, len(pcm_clean), chunk_size):
                        yield bytes(pcm_clean[i:i+chunk_size])
                
                print(f"Kristálytiszta PCM hangstream indítása az ESP32-nek... Méret: {len(pcm_clean)} bájt.")
                return Response(stream_with_context(generate_chunks()), mimetype='application/octet-stream')
            else:
                text_fallback = "Sikeres kapcsolat"
                try: text_fallback = res_json["candidates"][0]["content"]["parts"][0]["text"]
                except Exception: pass
                print(f"A Gemini nem adott vissza hangot. Szöveg lett helyette: {text_fallback}")
                return f"HIBA: A Gemini nem kulldott hangot, csak szoveget: {text_fallback}", 200
            
        else:
            print(f"Google API Hiba: {gemini_response.text}")
            return f"HIBA: Google API hiba ({gemini_response.status_code}).", 200
            
    except Exception as e:
        print(f"Szerveroldali hiba: {str(e)}")
        # BIZTONSÁGI FIX: Kivétel esetén SEM dobunk 500-at, hanem visszaküldjük a hibát 200 OK-val!
        return f"HIBA: Szerveroldali hiba: {str(e)}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
