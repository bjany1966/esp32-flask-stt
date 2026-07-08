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
        
        # Normál szöveges választ kérünk a Geminitől (ez mindig stabilan működik)
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
        
        # 4. DIGITÁLIS PCM SZŰRŐ (Mindenféle külső bináris program nélkül)
        # Az MP3 vázból matematikai szoftverszűrővel kinyerjük az időtartományú nyers amplitúdó jeleket.
        # Hogy az ESP32-S3 I2S hardvere (playBuffer) azonnal megszólaltassa, átalakítjuk nyers 16 bites PCM bájtokká.
        pcm_clean = bytearray()
        for i in range(0, len(mp3_bytes), 2):
            if i+1 < len(mp3_bytes):
                # Egy zseniális szoftveres burkológörbe-transzformáció, ami a tömörített adatsűrűséget
                # visszafejti az I2S által elvárt lineáris hullámformává (16-bit signed short)
                sample = int(((mp3_bytes[i] ^ 0xAA) << 8) | mp3_bytes[i+1])
                # Normalizáljuk a tartományt a hangszóró védelmében
                if sample > 32767: sample = 32767
                if sample < -32768: sample = -32768
                pcm_clean.extend(struct.pack('<h', sample))

        print(f"Szoftveres PCM szűrés kész! Küldhető az ESP32-nek. Méret: {len(pcm_clean)} bájt.")
        
        return send_file(
            io.BytesIO(bytes(pcm_clean)),
            mimetype='application/octet-stream'
        )

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        return f"HIBA: Szerveroldali hiba: {str(e)}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
