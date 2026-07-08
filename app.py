import os
import requests
import base64
import io
import wave
import struct
from flask import Flask, request, Response

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def generate_error_pcm_sound():
    """Matematikailag tiszta 24kHz-es PCM dallam arra az esetre, ha a Google nem adna hangot."""
    pcm_data = bytearray()
    # 0.5 másodperces pittyenés (440Hz szinusz)
    for i in range(12000): 
        import math
        signal = math.sin(2.0 * math.pi * 440.0 * (i / 24000))
        val = int(signal * 8000.0)
        pcm_data.extend(struct.pack('<h', val))
    return bytes(pcm_data)

@app.route('/')
def index():
    return "A kozponti hangfeldolgozo szerver aktiv es mukodik!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY:
        print("HIBA: Hianyzik a Gemini API kulcs.")
        return Response(generate_error_pcm_sound(), mimetype='application/octet-stream')

    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000:
            print("HIBA: Ures hang jott az ESP-rol.")
            return Response(generate_error_pcm_sound(), mimetype='application/octet-stream')
            
        print(f"Beérkezett mikrofonhang az ESP-ről: {len(pcm_data)} bájt.")

        # 1. Nyers PCM -> WAV átalakítás a Google kéréshez
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(pcm_data)
        wav_bytes = wav_io.getvalue()

        # 2. HTTP POST kérés a Gemini felé
        gemini_url = f"https://googleapis.com{GEMINI_API_KEY}"
        audio_base64 = base64.b64encode(wav_bytes).decode('utf-8')

        payload = {
            "contents": [{
                "parts": [
                    {"text": "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 4-5 szoban!"},
                    {"inlineData": {"mimeType": "audio/wav", "data": audio_base64}}
                ]
            }],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": "Puck"
                        }
                    }
                }
            }
        }

        print("Küldés a Google Gemini felé...")
        response = requests.post(gemini_url, json=payload, timeout=20)
        
        if response.status_code == 200:
            res_json = response.json()
            print(f"Sikeres Google valasz erkezett.")
            
            # ATOMBIZTOS REZIDUÁLIS VADÁSZ: 
            # Ha a Google struktúrája mélyen beágyazott listákból áll, egy rekurzív keresővel
            # addig túrjuk a JSON szótárt, amíg meg nem találjuk a leghosszabb Base64 hangadatot!
            audio_bytes = None
            
            def extract_base64_audio(data_obj):
                if isinstance(data_obj, dict):
                    for k, v in data_obj.items():
                        if k == 'data' and isinstance(v, str) and len(v) > 2000:
                            try: return base64.b64decode(v)
                            except Exception: pass
                        res = extract_base64_audio(v)
                        if res: return res
                elif isinstance(data_obj, list):
                    for item in data_obj:
                        res = extract_base64_audio(item)
                        if res: return res
                return None

            audio_bytes = extract_base64_audio(res_json)

            if audio_bytes:
                print(f"A Gemini gyári hangválasza sikeresen lehalászva! Méret: {len(audio_bytes)} bájt.")
                # Levágjuk az első 44 bájtot (WAV fejléc), hogy az ESP32 tiszta lineáris PCM-et kapjon
                if len(audio_bytes) > 44:
                    return Response(audio_bytes[44:], mimetype='application/octet-stream')
                return Response(audio_bytes, mimetype='application/octet-stream')
            else:
                print(f"HIBA: A JSON nem tartalmazott inline hangbájtokat. Nyers JSON: {res_json}")
                return Response(generate_error_pcm_sound(), mimetype='application/octet-stream')
        else:
            print(f"Google API Hiba: {response.text}")
            return Response(generate_error_pcm_sound(), mimetype='application/octet-stream')

    except Exception as e:
        print(f"Súlyos hiba a szerveren: {str(e)}")
        return Response(generate_error_pcm_sound(), mimetype='application/octet-stream')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
