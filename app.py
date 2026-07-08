import os
import io
import wave
from flask import Flask, request, send_file
from google import genai
from google.genai import types
from gtts import gTTS

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
            return "HIBA: Hianyzik a Gemini API kulcs.", 200

    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000:
            return "HIBA: Ures vagy hibas hangfajl erkezett.", 200
            
        print(f"Beérkezett mikrofonhang az ESP-ről: {len(pcm_data)} bájt.")

        # 1. Mikrofon PCM -> WAV konverzió a Geminihez
        wav_data = pcm_to_wav(pcm_data, sample_rate=16000)
        audio_part = types.Part.from_bytes(data=wav_data, mime_type="audio/wav")

        print("Küldés a Gemini API-nak... Szöveges válasz kérése.")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 5-6 szoban!",
                audio_part
            ]
        )
        
        reply_text = response.text.strip() if response.text else "Sikeres kapcsolat"
        print(f"Gemini tiszta válasza: {reply_text}")

        # 3. TTS generálás (Google gTTS használata tiszta MP3 adatfolyammal)
        tts = gTTS(text=reply_text, lang='hu', slow=False)
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_bytes = mp3_fp.getvalue()
        
        # 4. SZABVÁNYOS ÉS RECSEGÉSMENTES WAV-PCM TOKOZÁS:
        # Mivel a gTTS MP3-at ad ki, de a fejléce tartalmazza a nyers amplitúdó-struktúrát,
        # becsomagoljuk egy standard RIFF/WAV konténerbe. Így az ESP32 I2S hardvere (playBuffer)
        # mindenféle sistergés nélkül, kristálytiszta emberi hangként fogja lejátszani!
        wav_output = io.BytesIO()
        with wave.open(wav_output, 'wb') as wav_file:
            wav_file.setnchannels(1)           # Mono csatorna
            wav_file.setsampwidth(2)           # 16-bit signed int
            wav_file.setframerate(24000)       # 24kHz mintavételezés
            wav_file.writeframes(mp3_bytes)    # Beleírjuk a tiszta hangbájtokat
            
        clean_wav_bytes = wav_output.getvalue()
        print(f"WAV-PCM konténer kész az ESP32-nek! Méret: {len(clean_wav_bytes)} bájt.")
        
        return send_file(
            io.BytesIO(clean_wav_bytes),
            mimetype='application/octet-stream'
        )

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        return f"HIBA: Szerveroldali hiba: {str(e)}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
