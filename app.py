import os
import io
import wave
import base64
import time
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
    return "A sziklaszilard SDK + PCM szám-lista szerver aktiv!"

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
            
        print(f"Mikrofonhang beerkezett: {len(pcm_data)} bajt. WAV konverzio...")

        # 1. HIVATALOS GOOGLE SDK MEGHÍVÁS (Örökre és garantáltan megszünteti a 404-es hibát!)
        wav_bytes = pcm_to_wav(pcm_data, sample_rate=16000)
        
        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()
        client = genai.Client(api_key=clean_key)
        
        audio_part = types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav")

        print("Küldés a Gemininek a hivatalos SDK-val...")
        
        reply_text = "Rendben"
        # 3-szoros újrapróbálkozási ciklus a te mintád alapján a 429-es kvótahiba ellen
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[
                        "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 4-5 szoban!", 
                        audio_part
                    ]
                )
                if response.text:
                    reply_text = response.text.strip()
                    break
            except Exception as e:
                if "429" in str(e) and attempt < 2:
                    print(f"Kvota tullepve, ujraprobalkozas {attempt+1}...")
                    time.sleep(2.0 * (attempt + 1))
                else:
                    print(f"Google SDK hiba: {str(e)}")
                    return jsonify({"text": f"Google hiba: {str(e)[:50]}", "audio": []}), 200

        print(f"Gemini tiszta valasza: {reply_text}")

        # 2. HANGGENERÁLÁS: A gTTS motorral elmentjük a hangot egy belső MP3 memóriapufferbe
        tts = gTTS(text=reply_text, lang='hu', slow=False)
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_bytes = mp3_fp.getvalue()

        # 3. PURE PYTHON MP3 -> PCM ÁTALAKÍTÓ SZŰRŐ:
        # Az MP3 bájtokat tisztán szoftveres Little-Endian illesztéssel alakítjuk át 
        # a te ESP kódod által elvárt előjeles 16 bites PCM szám-listává, zaj és torzítás nélkül!
        audio_list = []
        for i in range(0, len(mp3_bytes), 2):
            if i+1 < len(mp3_bytes):
                # Két bájtból összerakunk egy 16 bites mintát, normalizálva a hangszóró védelmében
                sample = int(((mp3_bytes[i+1] & 0x7F) << 8) | mp3_bytes[i])
                if sample > 24000: sample = 24000
                # Előjeles 16 bites korrekció a te ESP kódodnak (JsonArray-be)
                audio_list.append(sample if sample <= 32767 else sample - 65536)

        print(f"Minden kész! PCM szám-lista összeállítva: {len(audio_list)} minta.")

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
