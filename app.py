import os
import io
import wave
import base64
import requests
from flask import Flask, request, send_file

app = Flask(__name__)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Átmeneti globális változó a legutolsó legenerált hang tárolására
latest_mp3_bytes = b""

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
    return "A kozponti MP3 streaming szerver aktiv!"

@app.route('/upload', methods=['POST'])
def process_audio():
    global latest_mp3_bytes
    if not GEMINI_API_KEY: 
        print("HIBA: Hianyzik a GEMINI_API_KEY a Render beallitasaibol.")
        return "HIBA: Hianyzik az API kulcs.", 200
        
    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000:
            print("HIBA: Ures vagy hibas hang jott az ESP-rol.")
            return "HIBA: Ures hang", 200
        
        print(f"Mikrofonhang beerkezett: {len(pcm_data)} bajt.")

        # 1. Mikrofon PCM -> WAV konverzió a Gemini bemenetéhez
        wav_bytes = pcm_to_wav(pcm_data, sample_rate=16000)
        audio_base64 = base64.b64encode(wav_bytes).decode('utf-8')

        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()
        
        # JAVÍTVA: A hivatalos, Google által előírt hajszálpontos v1beta URL végpont a gemini-2.5-flash modellhez!
        gemini_url = "https://googleapis.com"
        
        # A Google API által elvárt pontos JSON struktúra
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 4-5 szoban!"},
                    {
                        "inlineData": {
                            "mimeType": "audio/wav", 
                            "data": audio_base64
                        }
                    }
                ]
            }]
        }

        print("Küldés a Google Gemini felé tiszta HTTP POST-tal...")
        headers = {"Content-Type": "application/json"}
        gemini_response = requests.post(gemini_url, params={"key": clean_key}, json=payload, headers=headers, timeout=20)
        
        if gemini_response.status_code == 200:
            res_json = gemini_response.json()
            try:
                # Kikeressük a szöveges választ a Google JSON-ból
                reply_text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception as e:
                print(f"JSON kibontasi hiba: {str(e)}. Nyers JSON: {res_json}")
                reply_text = "Rendben"
            print(f"Gemini tiszta valasza: {reply_text}")
        else:
            print(f"Google API Hiba: {gemini_response.text}")
            return f"HIBA: Google hiba ({gemini_response.status_code})", 200

        # 3. TTS kérés a Google Translate-től (Standard, tökéletes MP3)
        tts_url = "https://google.com"
        headers_tts = {"User-Agent": "Mozilla/5.0"}
        params = {"ie": "UTF-8", "tl": "hu", "client": "tw-ob", "q": reply_text}
        
        print("Válaszhang generálása a Google TTS-sel...")
        tts_res = requests.get(tts_url, params=params, headers=headers_tts, timeout=12)
        
        if tts_res.status_code == 200:
            latest_mp3_bytes = tts_res.content
            print(f"Tiszta MP3 elmentve a szerver memóriájába: {len(latest_mp3_bytes)} bájt.")
            return "OK"
        else:
            print(f"HIBA: TTS hiba, status: {tts_res.status_code}")
            return "HIBA: TTS hiba", 200
            
    except Exception as e:
        print(f"Sulyos hiba a szerveren: {str(e)}")
        return f"HIBA: Szerveroldali hiba: {str(e)}", 200

# Ezen a végponton keresztül az ESP32 tiszta HTTP-n (SSL nélkül) éri el a hangot!
@app.route('/get_audio_stream.mp3', methods=['GET'])
def get_audio_stream():
    global latest_mp3_bytes
    if len(latest_mp3_bytes) > 0:
        return send_file(
            io.BytesIO(latest_mp3_bytes),
            mimetype='audio/mpeg',
            as_attachment=False
        )
    return "Nincs kesz hang", 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
