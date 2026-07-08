import os
import base64
import io
import wave
from flask import Flask, request, send_file
from google import genai
from google.genai import types
from gtts import gTTS
from pydub import AudioSegment

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

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
    return "A kozponti hangfeldolgozo szerver aktiv es mukodik!"

@app.route('/upload', methods=['POST'])
def process_audio():
    global client
    if not client:
        raw_key = os.environ.get("GEMINI_API_KEY")
        if raw_key:
            clean_key = str(raw_key).replace("\n", "").replace("\r", "").strip()
            client = genai.Client(api_key=clean_key)
        else:
            return "Hianyzik az API kulcs.", 500

    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000:
            return "Ures vagy hibas hangfajl.", 400
            
        print(f"Beérkezett mikrofonhang: {len(pcm_data)} bájt.")

        # 1. PCM -> WAV konverzió a Geminihez
        wav_data = pcm_to_wav(pcm_data, sample_rate=16000)
        audio_part = types.Part.from_bytes(data=wav_data, mime_type="audio/wav")

        # 2. Gemini 2.5 Flash lekérdezés
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 5-6 szoban!",
                audio_part
            ]
        )
        
        reply_text = response.text.strip() if response.text else "Sikeres kapcsolat"
        print(f"Gemini válasza: {reply_text}")

        # 3. TTS (Szövegből beszéd generálása magyarul)
        tts = gTTS(text=reply_text, lang='hu', slow=False)
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)

        # 4. MP3 átalakítása az ESP32 hangszórójának megfelelő nyers 24000Hz PCM formátumra
        audio = AudioSegment.from_file(mp3_fp, format="mp3")
        audio = audio.set_frame_rate(24000).set_channels(1).set_sample_width(2) # 24kHz, Mono, 16-bit (2 bájt/minta)
        
        raw_output = audio.raw_data
        print(f"Válaszhang legenerálva! Méret: {len(raw_output)} bájt.")

        # Visszaküldjük a nyers hangbájtokat az ESP32-nek lejátszásra
        return send_file(
            io.BytesIO(raw_output),
            mimetype='application/octet-stream'
        )

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        return f"Szerver hiba: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
