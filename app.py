import os
import base64
import io
import wave
import struct
from flask import Flask, request, send_file
from google import genai
from google.genai import types

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

def generate_fallback_pcm(text):
    """Ha a Gemini nem ad hangot, szoftveresen generálunk egy morze-szerű pittyegést a szöveg hossza alapján."""
    samples = 24000 * 2  # 2 másodperc fix hang
    pcm_data = bytearray()
    for i in range(samples):
        # 440Hz-es szinusz hullám generálása 24kHz-en
        import math
        signal = math.sin(2.0 * math.pi * 440.0 * (i / 24000))
        val = int(signal * 10000.0)
        pcm_data.extend(struct.pack('<h', val))
    return bytes(pcm_data)

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
            return "HIBA: Tul rovid vagy ures hangfajl erkezett.", 200
            
        print(f"Beérkezett mikrofonhang az ESP-ről: {len(pcm_data)} bájt.")

        # 1. Mikrofon PCM -> WAV konverzió a Geminihez
        wav_data = pcm_to_wav(pcm_data, sample_rate=16000)
        audio_part = types.Part.from_bytes(data=wav_data, mime_type="audio/wav")

        print("Küldés a Gemini API-nak... Közvetlen AUDIO kimenet és hangszín beállítása.")
        
        # JAVÍTVA: Hozzáadva a kötelező voice_config és beszédhang kiválasztás (Puck hangszín)
        config = types.GenerateContentConfig(
            response_mime_type="audio/wav",
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Puck"  # Hivatalos Google beszédhang
                    )
                )
            )
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 5-6 szoban!",
                audio_part
            ],
            config=config
        )
        
        # 3. A visszakapott nyers hangbájtok kinyerése
        audio_bytes = None
        try:
            if response.candidates:
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if part.inline_data and part.inline_data.data:
                                audio_bytes = base64.b64decode(part.inline_data.data)
                                break
        except Exception as e:
            print(f"Hiba a hang kinyerése közben: {str(e)}")

        if audio_bytes:
            print(f"A Gemini gyári hangválasza sikeresen megérkezett! Méret: {len(audio_bytes)} bájt.")
            # Levágjuk az első 44 bájtot (WAV fejléc), hogy az ESP32 tiszta, nyers PCM-et kapjon
            if len(audio_bytes) > 44:
                return send_file(io.BytesIO(audio_bytes[44:]), mimetype='application/octet-stream')
            return send_file(io.BytesIO(audio_bytes), mimetype='application/octet-stream')
        
        else:
            # TARTALÉK MEGOLDÁS: Ha a Google nem adott hangot, küldünk egy generált PCM-et, hogy az ESP ne legyen néma!
            print("A Gemini nem adott vissza hangot. Szöveges válasz: ", response.text)
            fallback_pcm = generate_fallback_pcm(response.text)
            return send_file(io.BytesIO(fallback_pcm), mimetype='application/octet-stream')

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        return f"HIBA: Szerveroldali hiba: {str(e)}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
