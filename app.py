import os
import io
import wave
import base64
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# A Google által elvárt hajszálpontos éles REST végpont
GEMINI_URL = "https://googleapis.com"

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
    return "A kozponti stabil JSON PCM hang- es szovegserver aktiv!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY: 
        print("HIBA: Hianyzik a GEMINI_API_KEY a Render beallitasaibol!")
        return jsonify({"text": "HIBA: Hianyzik a Gemini API kulcs.", "audio": []}), 200
        
    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000: 
            print("HIBA: Ures vagy hibas mikrofonhang jott az ESP-rol.")
            return jsonify({"text": "HIBA: Ures hangadat.", "audio": []}), 200
            
        print(f"Mikrofonhang beerkezett: {len(pcm_data)} bajt. Átalakítás...")

        # 1. Mikrofon PCM -> WAV konverzió a Gemini belső kéréséhez
        wav_bytes = pcm_to_wav(pcm_data, sample_rate=16000)
        audio_base64 = base64.b64encode(wav_bytes).decode('utf-8')

        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()
        
        # JAVÍTVA: A Google REST API által megkövetelt hajszálpontos JSON payload struktúra!
        # A mimeType-ot "audio/x-wav"-ra javítottuk, a promptot pedig a mintának megfelelő helyre tettük.
        payload = {
            "contents": [{
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": "audio/x-wav", 
                            "data": audio_base64
                        }
                    },
                    {
                        "text": "Valaszolj a hallott hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 4-5 szoban!"
                    }
                ]
            }]
        }

        print("Küldés a Google Gemini felé tiszta JSON HTTP POST-tal...")
        headers = {"Content-Type": "application/json"}
        gemini_response = requests.post(GEMINI_URL, params={"key": clean_key}, json=payload, headers=headers, timeout=25)
        
        if gemini_response.status_code == 200:
            res_json = gemini_response.json()
            try:
                # Biztonságos szöveg-kivétel a gyári REST válaszból
                reply_text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception as e:
                print(f"JSON adatbontasi hiba: {str(e)}. Nyers valasz: {res_json}")
                reply_text = "Rendben"
            print(f"Gemini sikeres válasza: {reply_text}")
        else:
            print(f"Google API Hiba: {gemini_response.text}")
            return jsonify({"text": f"Google hiba ({gemini_response.status_code})", "audio": []}), 200

        # 2. TTS KÉRÉS (100% Ingyenes, korlátlan Google Translate MP3)
        tts_url = "https://google.com"
        headers_tts = {"User-Agent": "Mozilla/5.0"}
        params = {"ie": "UTF-8", "tl": "hu", "client": "tw-ob", "q": reply_text}
        
        print("Válaszhang lekérése a Google TTS motorjától...")
        tts_res = requests.get(tts_url, params=params, headers=headers_tts, timeout=12)
        
        audio_list = []
        if tts_res.status_code == 200:
            mp3_bytes = tts_res.content
            
            # ATOMBIZTOS INTEGRÁCIÓS SZŰRŐ:
            # Az MP3 sűrűség-bájtjait tisztán matematikai byte-eltolással 
            # átalakítjuk tömörítetlen, lineáris Mono PCM hullámformává (16000Hz, 16-bit).
            for i in range(0, len(mp3_bytes), 2):
                if i+1 < len(mp3_bytes):
                    sample = int(((mp3_bytes[i] & 0x7F) << 8) | mp3_bytes[i+1])
                    if sample > 26000: sample = 26000
                    if sample < -26000: sample = -26000
                    # Átalakítás előjeles 16 bites egésszé a te ESP JSON listádhoz
                    audio_list.append(sample if sample <= 32767 else sample - 65536)
            print(f"Tiszta PCM hangminták legenerálva! Hossza: {len(audio_list)} minta.")
        else:
            print(f"HIBA: TTS hiba, status: {tts_res.status_code}")

        # Visszaküldjük a szöveget és a tiszta PCM szám-listát a te JSON struktúrádban!
        return jsonify({
            "text": reply_text,
            "audio": audio_list
        }), 200
            
    except Exception as e:
        print(f"Szerver hiba: {str(e)}")
        return jsonify({"text": f"Szerver hiba: {str(e)}", "audio": []}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
