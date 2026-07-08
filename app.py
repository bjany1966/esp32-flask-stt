import os
import base64
import io
import wave
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
            
        print(f"Beérkezett mikrofonhang az ESP-ről: {len(pcm_data)} bájt.")

        # 1. Mikrofon PCM -> WAV konverzió a Geminihez
        wav_data = pcm_to_wav(pcm_data, sample_rate=16000)
        audio_part = types.Part.from_bytes(data=wav_data, mime_type="audio/wav")

        print("Küldés a Gemini API-nak... Közvetlen HANG válasz kérése.")
        
        # 2. Beállítjuk a Geminit, hogy HANG (audio) formátumban válaszoljon a szöveg helyett
        config = types.GenerateContentConfig(
            response_mime_type="audio/wav" # Szabványos, tömörítetlen hangot kérünk!
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 5-6 szoban! A valaszod egybol hang legyen!",
                audio_part
            ],
            config=config
        )
        
        # 3. Kivesszük a beérkező nyers hangbájtokat a Google válaszából
        audio_bytes = None
        try:
            # A Google SDK-ban a part.inline_data tartalmazza a nyers bájtokat base64-ben
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    audio_bytes = base64.b64decode(part.inline_data.data)
                    break
        except Exception as e:
            print(f"Nem sikerült kivenni a hangbájtokat: {str(e)}")

        if audio_bytes:
            print(f"A Gemini gyári hangválasza sikeresen kicsomagolva! Méret: {len(audio_bytes)} bájt.")
            
            # Az első 44 bájtot (a WAV fejlécet) levágjuk, hogy tiszta nyers PCM adatot kapjon az ESP32
            if len(audio_bytes) > 44:
                pcm_only = audio_bytes[44:]
                return send_file(io.BytesIO(pcm_only), mimetype='application/octet-stream')
            
            return send_file(io.BytesIO(audio_bytes), mimetype='application/octet-stream')
        else:
            print("A Gemini nem adott vissza hangot. Szöveg: ", response.text)
            return "HIBA: Nem erkezett hang a modelltol.", 200

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        return f"Szerver hiba: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
