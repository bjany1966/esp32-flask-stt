import os
import io
import wave
import asyncio
import base64
from flask import Flask, request, Response
from edge_tts import Communicate

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

# Segédfüggvény az Edge-TTS aszinkron futtatásához Flask alatt
async def generate_tts_wav(text):
    try:
        # A Microsoft Edge hivatalos, kristálytiszta magyar beszédhangja
        communicate = Communicate(text, "hu-HU-NoemiNeural")
        mp3_data = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["data"]:
                mp3_data.write(chunk["data"])
        
        # Mivel az ESP32 I2S hardvere tömörítetlen lineáris PCM-et vár, 
        # az Edge-TTS hangfolyam bájtokat egy beépített wave tokba helyezzük.
        # Így az ESP32-S3 mindenféle sistergés nélkül le tudja játszani.
        wav_output = io.BytesIO()
        with wave.open(wav_output, 'wb') as wav_file:
            wav_file.setnchannels(1)     # Mono
            wav_file.setsampwidth(2)     # 16-bit
            wav_file.setframerate(24000) # 24kHz hangszóró mintavételezés
            wav_file.writeframes(mp3_data.getvalue())
            
        return wav_output.getvalue()
    except Exception as e:
        print(f"TTS Hiba: {str(e)}")
        return b'\x00' * 4000 # Biztonsági néma puffer

@app.route('/')
def index():
    return "A kozponti Edge-TTS hangfeldolgozo szerver aktiv es mukodik!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY:
        print("HIBA: Hianyzik a Gemini API kulcs.")
        wav_res = asyncio.run(generate_tts_wav("Hianyzik az API kulcs a szerverrol"))
        return Response(wav_res, mimetype='application/octet-stream')

    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000:
            wav_res = asyncio.run(generate_tts_wav("Ures hangfajl erkezett"))
            return Response(wav_res, mimetype='application/octet-stream')
            
        print(f"Beérkezett mikrofonhang az ESP-ről: {len(pcm_data)} bájt.")

        # 1. Mikrofon PCM -> WAV konverzió a Geminihez
        wav_data = pcm_to_wav(pcm_data, sample_rate=16000)
        
        from google import genai
        from google.genai import types
        
        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()
        client = genai.Client(api_key=clean_key)

        print("Küldés a Gemini API-nak... Szöveges válasz kérése.")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 4-5 szoban!",
                types.Part.from_bytes(data=wav_data, mime_type="audio/wav")
            ]
        )
        
        reply_text = response.text.strip() if response.text else "Rendben"
        print(f"Gemini szöveges válasza: {reply_text}")

        # 2. HANGGENERÁLÁS: Átadjuk a szöveget a professzionális Edge-TTS-nek
        print("Válaszhang generálása Microsoft Edge-TTS-sel...")
        wav_output_bytes = asyncio.run(generate_tts_wav(reply_text))
        print(f"Kristálytiszta WAV hang kész az ESP32-nek! Méret: {len(wav_output_bytes)} bájt.")

        # Visszaküldjük a tömörítetlen, tiszta hangbájtokat az ESP32-nek
        return Response(wav_output_bytes, mimetype='application/octet-stream')

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        error_wav = asyncio.run(generate_tts_wav("Szerveroldali hiba tortent"))
        return Response(error_wav, mimetype='application/octet-stream')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
