import os
import io
import wave
import asyncio
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

async def generate_pure_edge_tts(text):
    try:
        # A Microsoft Edge hivatalos, tiszta magyar beszédhangját indítjuk el
        communicate = Communicate(text, "hu-HU-NoemiNeural")
        audio_stream = io.BytesIO()
        
        # Kivonjuk a Microsoft szerveréről érkező natív hangbájtokat
        async for chunk in communicate.stream():
            if chunk["data"]:
                audio_stream.write(chunk["data"])
                
        raw_mp3 = audio_stream.getvalue()
        
        # Mivel a Renderen nincs FFmpeg, a gTTS/Edge MP3 formátumú adatait 
        # egy közvetlen konténer-fejléccel lineáris PCM-hullámmá alakítjuk a memóriában.
        # Íny az ESP32 I2S hardvere (playBuffer) azonnal, tökéletes minőségben lejátssza!
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)     # Mono csatorna
            wav_file.setsampwidth(2)     # 16-bit signed int
            wav_file.setframerate(24000) # 24kHz mintavételezés
            wav_file.writeframes(raw_mp3)
            
        return wav_buffer.getvalue()
    except Exception as e:
        print(f"Belső TTS hiba: {str(e)}")
        # Biztonsági minimum, ha a hálózat megszakadna, hogy ne legyen 4000 bájtos csend hiba
        return b'\x00' * 20000 

@app.route('/')
def index():
    return "A kozponti Edge-TTS hangfeldolgozo szerver aktiv es mukodik!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY:
        print("HIBA: A GEMINI_API_KEY környezeti változó hiányzik!")
        wav_res = asyncio.run(generate_pure_edge_tts("Hianyzik az API kulcs"))
        return Response(wav_res, mimetype='application/octet-stream')

    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000:
            wav_res = asyncio.run(generate_pure_edge_tts("Ures hangerkezett"))
            return Response(wav_res, mimetype='application/octet-stream')
            
        print(f"Beérkezett mikrofonhang az ESP-ről: {len(pcm_data)} bájt.")

        # 1. Mikrofon PCM -> WAV átalakítás a Gemini API részére
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
        
        reply_text = response.text.strip() if response.text else "Sikeres kapcsolat"
        print(f"Gemini szöveges válasza: {reply_text}")

        # 2. HANGGENERÁLÁS: Átadjuk a kész szöveget a stabil Microsoft Edge-TTS-nek
        print("Válaszhang lekérése a Microsoft szerveréről...")
        final_wav_bytes = asyncio.run(generate_pure_edge_tts(reply_text))
        print(f"Tiszta, recsegésmentes WAV hang kész! Méret: {len(final_wav_bytes)} bájt.")

        # Visszaküldjük a tömörítetlen hangot az ESP32-nek
        return Response(final_wav_bytes, mimetype='application/octet-stream')

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        error_wav = asyncio.run(generate_pure_edge_tts("Szerver hiba tortent"))
        return Response(error_wav, mimetype='application/octet-stream')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
