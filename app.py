import os
import io
import wave
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
    return "A kozponti stabil MP3 hangfeldolgozo aktiv!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY: 
        print("HIBA: Hianyzik a GEMINI_API_KEY a Render beallitasaibol!")
        return "HIBA: Hianyzik a Gemini API kulcs.", 200
        
    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000: 
            print(f"HIBA: Ures vagy tul rovid adat jott: {len(pcm_data) if pcm_data else 0} bajt.")
            return "HIBA: Ures vagy hibas hangfajl.", 200
            
        print(f"Mikrofonhang beerkezett: {len(pcm_data)} bajt.")

        # 1. Mikrofon PCM -> WAV konverzió a Geminihez
        wav_data = pcm_to_wav(pcm_data, sample_rate=16000)
        
        # A hivatalos Google SDK csomagok importalasa a try blokkon belul
        from google import genai
        from google.genai import types
        
        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()
        client = genai.Client(api_key=clean_key)

        print("Kuldes a Gemini API-nak...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 4-5 szoban!", 
                types.Part.from_bytes(data=wav_data, mime_type="audio/wav")
            ]
        )
        
        reply_text = response.text.strip() if response.text else "Rendben"
        print(f"Gemini tiszta valasza: {reply_text}")

        # 2. TTS kérés (Google Translate standard, tiszta MP3 folyam)
        tts_url = "https://google.com"
        headers = {"User-Agent": "Mozilla/5.0"}
        params = {
            "ie": "UTF-8",
            "tl": "hu",
            "client": "tw-ob",
            "q": reply_text
        }
        
        print("Válaszhang generalasa a Google TTS-sel...")
        tts_res = requests.get(tts_url, params=params, headers=headers, timeout=12)
        
        if tts_res.status_code == 200:
            mp3_data = tts_res.content
            print(f"Tiszta MP3 kész az ESP32-nek! Méret: {len(mp3_data)} bájt.")
            
            # Kényszerített fix Content-Length fejléc, hogy az ESP32 SPIFFS mentője pontosan tudja a méretet!
            return Response(
                mp3_data,
                mimetype='audio/mpeg',
                headers={'Content-Length': str(len(mp3_data))}
            )
        else:
            print(f"HIBA: Google TTS hiba, status code: {tts_res.status_code}")
            return f"HIBA: TTS hiba ({tts_res.status_code})", 200
            
    except Exception as e:
        print(f"Sulyos hiba a szerveren: {str(e)}")
        # JAVÍTVA: Kivétel esetén SEM dobunk 500-at, hanem visszaküldjük a hiba szövegét 200 OK-val, 
        # így az ESP32 kiírja a soros monitorra, és nem ragad be a kód!
        return f"HIBA: Szerveroldali kivetel: {str(e)}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
