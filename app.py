import os
import io
import wave
import base64
from flask import Flask, request, Response, stream_with_context
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

@app.route('/')
def index():
    return "A központi direkt Gemini HANG streamelő szerver aktív!"

@app.route('/upload', methods=['POST'])
def process_audio():
    global client
    if not client:
        raw_key = os.environ.get("GEMINI_API_KEY")
        if raw_key:
            clean_key = str(raw_key).replace("\n", "").replace("\r", "").strip()
            client = genai.Client(api_key=clean_key)
        else:
            return "HIBA: Hianyzo API kulcs.", 200

    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000: 
            return "HIBA: Ures vagy hibas hangfajl erkezett.", 200
        
        print(f"Mikrofonhang beerkezett az ESP-ről: {len(pcm_data)} bajt.")

        # 1. Mikrofon PCM -> WAV konverzió a Gemini bemenetének
        wav_data = pcm_to_wav(pcm_data, sample_rate=16000)
        audio_part = types.Part.from_bytes(data=wav_data, mime_type="audio/wav")

        print("Küldés a Google Gemini felé... Közvetlen HANG válasz kérése.")
        
        # Hivatalos, legújabb SDK konfiguráció a hang kimenethez (Puck férfi beszédhang)
        config = types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Puck"
                    )
                )
            )
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 4-5 szoban!",
                audio_part
            ],
            config=config
        )
        
        # 2. Kivesszük a beérkező nyers hangbájtokat a Google válaszból
        audio_bytes = None
        try:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    audio_bytes = base64.b64decode(part.inline_data.data)
                    break
        except Exception as e:
            print(f"Nem sikerült kivenni a hangbájtokat: {str(e)}")

        if audio_bytes:
            # Levágjuk az első 44 bájtot (WAV fejléc), hogy az ESP32 tiszta, Mono PCM-et kapjon
            pcm_clean = audio_bytes[44:] if len(audio_bytes) > 44 else audio_bytes
            print(f"A Gemini gyári tiszta hangválasza kicsomagolva! Méret: {len(pcm_clean)} bájt.")
            
            # 3. DARABOLT (CHUNKED) ÁTVITEL: 
            # 1024 bájtos darabokban küldjük vissza, így az ESP-nek nem fogy el a RAM-ja (nincs OOM)
            def generate_chunks():
                chunk_size = 1024
                for i in range(0, len(pcm_clean), chunk_size):
                    yield bytes(pcm_clean[i:i+chunk_size])
            
            return Response(stream_with_context(generate_chunks()), mimetype='application/octet-stream')
        else:
            print("A Gemini csak szöveggel válaszolt: ", response.text)
            return f"HIBA: Nem erkezett hang a Google-tol. Szoveg: {response.text}", 200

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        # BIZTONSÁGI FIX: Kivétel esetén SEM dobunk 500-at, hanem visszaküldjük a hibát 200 OK-val!
        return f"HIBA: Szerveroldali kivetel: {str(e)}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
