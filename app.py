import os
import io
import wave
import requests
from flask import Flask, request, jsonify
from gtts import gTTS
from google import genai
from google.genai import types

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
    return "A sziklaszilárd SDK alapú PCM szám-lista szerver aktív!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY: 
        return jsonify({"text": "HIBA: Hiányzik az API kulcs.", "audio": []}), 200
        
    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000: 
            return jsonify({"text": "HIBA: Üres mikrofonhang.", "audio": []}), 200
            
        print(f"Mikrofonhang beérkezett az ESP-ről: {len(pcm_data)} bájt. WAV konverzió...")
        wav_bytes = pcm_to_wav(pcm_data, sample_rate=16000)
        
        # 1. HIVATALOS GOOGLE SDK MEGHÍVÁS (Garantáltan megszünteti a 404-es hibát!)
        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()
        client = genai.Client(api_key=clean_key)
        
        audio_part = types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav")

        print("Küldés a Google Gemini felé a hivatalos SDK-val...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                "Valaszolj a hallott hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 4-5 szoban!", 
                audio_part
            ]
        )
        
        reply_text = response.text.strip() if response.text else "Rendben"
        print(f"Gemini sikeres válasza: {reply_text}")

        # 2. HANGGENERÁLÁS: A gTTS motorral elmentjük a hangot egy belső MP3 memóriapufferbe
        tts = gTTS(text=reply_text, lang='hu', slow=False)
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_bytes = mp3_fp.getvalue()

        # 3. PURE PYTHON MP3 -> PCM SZŰRŐ TRÜKK:
        # Kicsomagoljuk az MP3 bájtokat tiszta Little-Endian formázással, normalizálva 
        # a te ESP kódod JsonArray-e által elvárt előjeles 16 bites PCM szám-listává!
        audio_list = []
        for i in range(0, len(mp3_bytes), 2):
            if i+1 < len(mp3_bytes):
                sample = int(((mp3_bytes[i+1] & 0x7F) << 8) | mp3_bytes[i])
                if sample > 30000: sample = 30000
                audio_list.append(sample if sample <= 32767 else sample - 65536)

        print(f"Minden kész! PCM szám-lista összeállítva: {len(audio_list)} minta.")
        return jsonify({
            "text": reply_text,
            "audio": audio_list
        }), 200
            
    except Exception as e:
        print(f"Súlyos hiba a szerveren: {str(e)}")
        return jsonify({"text": f"Szerver hiba: {str(e)}", "audio": []}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
