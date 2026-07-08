import os
import io
import wave
import requests
from flask import Flask, request, send_file
from google import genai
from google.genai import types

app = Flask(__name__)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Átmeneti globális változó a legutolsó legenerált hang tárolására
latest_mp3_bytes = b""

# Inicializáljuk a klienst biztonságosan az SDK-val
client = None
if GEMINI_API_KEY:
    try:
        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()
        client = genai.Client(api_key=clean_key)
    except Exception as e:
        print(f"Kliens inditasi hiba: {str(e)}")

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
    global latest_mp3_bytes, client
    
    if not client:
        raw_key = os.environ.get("GEMINI_API_KEY")
        if raw_key:
            try:
                clean_key = str(raw_key).replace("\n", "").replace("\r", "").strip()
                client = genai.Client(api_key=clean_key)
            except Exception as e:
                return f"HIBA: Nem sikerült indítani a Google klienst: {str(e)}", 200
        else:
            return "HIBA: Hianyzik a Gemini API kulcs a Render beallitasaibol.", 200
        
    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000:
            print("HIBA: Ures vagy hibas hang jott az ESP-rol.")
            return "HIBA: Ures hangfajl érkezett.", 200
        
        print(f"Mikrofonhang beerkezett: {len(pcm_data)} bajt. WAV konverzio...")

        # 1. Mikrofon PCM -> WAV konverzió a Gemini bemenetéhez
        wav_bytes = pcm_to_wav(pcm_data, sample_rate=16000)
        
        # JAVÍTVA: A hivatalos google-genai SDK szerinti pontos part-kezelés
        audio_part = types.Part.from_bytes(
            data=wav_bytes,
            mime_type="audio/wav"
        )

        print("Küldés a Google Gemini felé a hivatalos SDK-val...")
        # Kizárólag tiszta szöveges választ kérünk (ez az ingyenes szinten 100% stabil)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                "Valaszolj a hallott hangra tisztan magyarul, nagyon roviden, ekezetek nelkul, maximum 4-5 szoban!",
                audio_part
            ]
        )
        
        reply_text = response.text.strip() if response.text else "Rendben"
        print(f"Gemini tiszta válasza: {reply_text}")

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
            return "HIBA: Nem sikerült a beszédhang legenerálása.", 200
            
    except Exception as e:
        print(f"Sulyos hiba a szerveren: {str(e)}")
        # BIZTONSÁGI FIX: Kivétel esetén SEM dobunk 500-at, hanem visszaküldjük a hibát 200 OK-val!
        return f"HIBA: Szerveroldali kivétel: {str(e)}", 200

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
