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
    return "A végleges direkt Gemini PCM hang- és szövegszerver aktív!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY: 
        print("HIBA: Hiányzik a GEMINI_API_KEY a Render beállításaiból!")
        return "HIBA: Hiányzik a Gemini API kulcs.", 200
        
    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000: 
            print("HIBA: Üres vagy hibás mikrofonhang jött az ESP-ről.")
            return "HIBA: Üres hangadat.", 200
            
        print(f"Mikrofonhang beérkezett az ESP-ről: {len(pcm_data)} bájt.")

        # 1. Mikrofon PCM -> WAV konverzió a Gemini bemenetéhez
        wav_bytes = pcm_to_wav(pcm_data, sample_rate=16000)
        audio_base64 = base64.b64encode(wav_bytes).decode('utf-8')

        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()
        
        # Direkt HTTP POST kérés a Gemini felé
        gemini_url = "https://googleapis.com"
        
        # KÉNYSZERÍTÉS: Az "audio/pcm" kimenettel a Gemini natív 16kHz Mono PCM hangot gyárt le!
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Valaszolj a hallott hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 4-5 szoban!"},
                    {
                        "inlineData": {
                            "mimeType": "audio/wav", 
                            "data": audio_base64
                        }
                    }
                ]
            }],
            "generationConfig": {
                "responseMimeType": "audio/pcm"
            }
        }

        print("Küldés a Google Gemini felé direkt PCM és szöveg generálásra...")
        headers = {"Content-Type": "application/json"}
        gemini_response = requests.post(gemini_url, params={"key": clean_key}, json=payload, headers=headers, timeout=25)
        
        if gemini_response.status_code == 200:
            res_json = gemini_response.json()
            
            # Kikeressük a szöveges és a hang választ a Google közös JSON-jából
            reply_text = "Rendben"
            raw_voice_bytes = b""
            
            try:
                parts = res_json["candidates"][0]["content"]["parts"]
                for part in parts:
                    if "text" in part:
                        reply_text = part["text"].strip()
                    if "inlineData" in part and "data" in part["inlineData"]:
                        raw_voice_bytes = base64.b64decode(part["inlineData"]["data"])
            except Exception as e:
                print(f"JSON bontási hiba: {str(e)}")

            print(f"Gemini szöveges válasza: {reply_text}")
            print(f"Gemini gyári PCM hangválasza: {len(raw_voice_bytes)} bájt.")

            # Létrehozzuk a fix, 128 bájtos szöveges fejlécet az ESP32 soros monitorának
            header_packet = bytearray(128)
            text_bytes = reply_text.encode('utf-8')[:127]
            header_packet[:len(text_bytes)] = text_bytes
            
            # Összefűzzük a tiszta szöveget és a Google által gyártott nyers, tömörítetlen hangot
            final_payload = header_packet + raw_voice_bytes
            
            def generate_chunks():
                chunk_size = 1024
                for i in range(0, len(final_payload), chunk_size):
                    yield bytes(final_payload[i:i+chunk_size])
            
            print(f"Minden kész! Stream indítása az ESP32 felé. Teljes méret: {len(final_payload)} bájt.")
            return Response(stream_with_context(generate_chunks()), mimetype='application/octet-stream')
        else:
            print(f"Google API Hiba: {gemini_response.text}")
            return f"HIBA: Google hiba ({gemini_response.status_code})", 200

    except Exception as e:
        print(f"Súlyos hiba a szerveren: {str(e)}")
        return f"HIBA: Szerveroldali kivétel: {str(e)}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
