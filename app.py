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
            return "HIBA: Hianyzik a Gemini API kulcs.", 200

    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000:
            return "HIBA: Ures vagy hibas hangfajl erkezett.", 200
            
        print(f"Beérkezett mikrofonhang az ESP-ről: {len(pcm_data)} bájt.")

        # 1. Mikrofon PCM -> WAV konverzió a Gemini bemenetéhez
        wav_data = pcm_to_wav(pcm_data, sample_rate=16000)
        audio_part = types.Part.from_bytes(data=wav_data, mime_type="audio/wav")

        print("Küldés a Gemini API-nak... Közvetlen AUDIO kimenet konfigurálása.")
        
        # BIZTONSÁGOS GENERÁLÁSI BEÁLLÍTÁS:
        # A response_mime_type megadásával kényszerítjük a Google szervereit, hogy
        # ne szöveget, hanem szabványos hangfájlt generáljanak válaszként!
        config = types.GenerateContentConfig(
            response_mime_type="audio/wav" 
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 5-6 szoban! A valaszod egybol HANG legyen!",
                audio_part
            ],
            config=config
        )
        
        # 3. A visszakapott nyers hangbájtok kinyerése a Google válasz-objektumából
        audio_bytes = None
        try:
            if hasattr(response, 'candidates') and response.candidates:
                for candidate in response.candidates:
                    if hasattr(candidate, 'content') and candidate.content:
                        for part in candidate.content.parts:
                            # Megkeressük az inline_data blokkot, ahol a Google a nyers hangot küldi base64-ben
                            if hasattr(part, 'inline_data') and part.inline_data:
                                if hasattr(part.inline_data, 'data') and part.inline_data.data:
                                    audio_bytes = base64.b64decode(part.inline_data.data)
                                    break
        except Exception as e:
            print(f"Hiba a hang kinyerése közben: {str(e)}")

        if audio_bytes:
            print(f"A Gemini gyári hangválasza sikeresen kicsomagolva! Méret: {len(audio_bytes)} bájt.")
            
            # Levágjuk az első 44 bájtot (WAV fejléc), hogy az ESP32 tiszta, nyers, lineáris PCM bájtokat kapjon
            if len(audio_bytes) > 44:
                pcm_only = audio_bytes[44:]
                return send_file(io.BytesIO(pcm_only), mimetype='application/octet-stream')
            
            return send_file(io.BytesIO(audio_bytes), mimetype='application/octet-stream')
        else:
            # Ha a modell mégis szöveggel válaszolt, kiírjuk a logba az okát
            print("A Gemini nem adott vissza hangot. Szöveg: ", response.text)
            return "HIBA: Nem erkezett hangvalasz a Google-tol.", 200

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        return f"HIBA: Szerveroldali hiba: {str(e)}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
