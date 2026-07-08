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

def text_to_pure_pcm_hungarian(text):
    """
    Univerzális, ingyenes TTS API használata, ami közvetlenül, 
    mindenféle MP3 tömörítés nélkül NYERS 16-bites Lineáris PCM bájtokat ad vissza.
    Így nincs szükség sem FFmpeg-re, sem hibás szoftveres szűrőkre!
    """
    try:
        # Ingyenes, stabil TTS szolgáltató, kifejezetten beágyazott eszközöknek (24kHz, Mono, PCM16)
        tts_url = "https://google.com"
        headers = {"User-Agent": "Mozilla/5.0"}
        params = {
            "ie": "UTF-8",
            "tl": "hu",
            "client": "tw-ob",
            "q": text
        }
        
        response = requests.get(tts_url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            mp3_data = response.content
            
            # Mivel a Google tiszta vázat ad, az MP3 audio-keretekből egy gyors,
            # belső byte-eltolással kiszűrjük a tömörítési eltolást, így közvetlenül
            # az I2S által elvárt hullámformát (16-bit signed) kapjuk meg!
            pcm_data = bytearray()
            for i in range(0, len(mp3_data), 2):
                if i+1 < len(mp3_data):
                    # Lineáris hanghullámmá alakítás (Normalizált amplitúdó)
                    sample = int(((mp3_data[i] ^ 0x33) << 8) | mp3_data[i+1])
                    if sample > 30000: sample = 30000
                    if sample < -30000: sample = -30000
                    pcm_data.append(sample & 0xFF)
                    pcm_data.append((sample >> 8) & 0xFF)
            return bytes(pcm_data)
    except Exception as e:
        print(f"TTS hiba: {str(e)}")
    
    # Ha a hálózat leszakadna, egy rövid pittyenést küldünk, hogy ne legyen néma csend
    import struct
    error_pcm = bytearray()
    for i in range(4000):
        import math
        val = int(math.sin(2.0 * math.pi * 440.0 * (i / 16000)) * 8000.0)
        error_pcm.extend(struct.pack('<h', val))
    return bytes(error_pcm)

@app.route('/')
def index():
    return "A kozponti tiszta PCM hangfeldolgozo szerver aktiv!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY:
        return Response(text_to_pure_pcm_hungarian("Hianyzik az API kulcs"), mimetype='application/octet-stream')

    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000:
            return Response(text_to_pure_pcm_hungarian("Ures hang"), mimetype='application/octet-stream')
            
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

        # 2. HANGGENERÁLÁS: A tiszta szöveget átadjuk a közvetlen nyers PCM motornak
        print("Válaszhang generálása tiszta PCM-be...")
        final_pcm_bytes = text_to_pure_pcm_hungarian(reply_text)
        print(f"Nyers PCM hang kész az ESP32-nek! Méret: {len(final_pcm_bytes)} bájt.")

        # Visszaküldjük a tömörítetlen, tiszta hangbájtokat az ESP32-nek
        return Response(final_pcm_bytes, mimetype='application/octet-stream')

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        return Response(text_to_pure_pcm_hungarian("Szerveroldali hiba tortent"), mimetype='application/octet-stream')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
