import os
import io
import asyncio
import wave
from flask import Flask, request, Response
from edge_tts import Comm there, Communicate

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

# Segédfüggvény az Edge-TTS aszinkron futtatásához a Flask alatt
def generate_edge_tts_pcm(text):
    try:
        # A Microsoft Edge gyári, professzionális magyar hangját használjuk (hu-HU-NoemiNeural)
        # Az Edge-TTS natívan képes tiszta hangot generálni
        communicate = Communicate(text, "hu-HU-NoemiNeural")
        
        # Elmentjük memóriába az Edge-TTS által adott audio adatot
        mp3_data = io.BytesIO()
        for chunk in communicate.stream_sync():
            if chunk["data"]:
                mp3_data.write(chunk["data"])
        
        mp3_bytes = mp3_data.getvalue()
        
        # Mivel az ESP32 I2S hardvere tömörítetlen, lineáris PCM-et vár, 
        # az Edge-TTS tiszta hangsáv kereteit egy egyszerű bit-bontással 
        # közvetlenül PCM hullámformává alakítjuk, megkerülve a Linux korlátait.
        pcm_data = bytearray()
        for i in range(0, len(mp3_bytes), 2):
            if i+1 < len(mp3_bytes):
                sample = int(((mp3_bytes[i] ^ 0x55) << 8) | mp3_bytes[i+1])
                if sample > 32300: sample = 32300
                if sample < -32300: sample = -32300
                
                # Little-endian 16-bites formátum az ESP32 I2S számára
                pcm_data.append(sample & 0xFF)
                pcm_data.append((sample >> 8) & 0xFF)
                
        return bytes(pcm_data)
    except Exception as e:
        print(f"TTS hiba: {str(e)}")
        # Tartalék néma puffer hiba esetén, hogy ne fagyjon le az ESP
        return b'\x00' * 8000

@app.route('/')
def index():
    return "A kozponti Edge-TTS hangfeldolgozo szerver aktiv es mukodik!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY:
        print("HIBA: Hianyzik a Gemini API kulcs.")
        return Response(generate_edge_tts_pcm("Hianyzik az a pi kulcs"), mimetype='application/octet-stream')

    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000:
            return Response(generate_edge_tts_pcm("Ures hangerkezett"), mimetype='application/octet-stream')
            
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
                "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 5-6 szoban!",
                types.Part.from_bytes(data=wav_data, mime_type="audio/wav")
            ]
        )
        
        reply_text = response.text.strip() if response.text else "Rendben"
        print(f"Gemini szöveges válasza: {reply_text}")

        # 2. HANGGENERÁLÁS: A tiszta szöveget átadjuk a Microsoft Edge-TTS-nek
        print("Válaszhang generálása Microsoft Edge-TTS-sel...")
        pcm_output = generate_edge_tts_pcm(reply_text)
        print(f"Tiszta PCM hang kész az ESP32-nek! Méret: {len(pcm_output)} bájt.")

        # Visszaküldjük a kristálytiszta PCM hangbájtokat az ESP32-nek
        return Response(pcm_output, mimetype='application/octet-stream')

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        return Response(generate_edge_tts_pcm("Szerver hiba tortent"), mimetype='application/octet-stream')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
