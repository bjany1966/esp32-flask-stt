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
            return "HIBA: Hianyzik az API kulcs a Render beallitasaibol.", 200

    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000:
            return "HIBA: Ures vagy hibas hangfajl erkezett.", 200
            
        print(f"Beérkezett mikrofonhang az ESP-ről: {len(pcm_data)} bájt.")

        # 1. Mikrofon PCM -> WAV konverzió a Geminihez
        wav_data = pcm_to_wav(pcm_data, sample_rate=16000)
        audio_part = types.Part.from_bytes(data=wav_data, mime_type="audio/wav")

        print("Küldés a Gemini API-nak... Közvetlen HANG válasz kérése.")
        
        config = types.GenerateContentConfig(
            response_modalities=["AUDIO"]  # Kényszeríti a hang alapú kimenetet
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 5-6 szoban!",
                audio_part
            ],
            config=config
        )
        
        # 3. Mély, univerzális és atombiztos JSON kereső a hangbájtok kinyeréséhez
        audio_bytes = None
        try:
            # Ha a válasz objektumként érkezik, átrakjuk dictionary formátumba a könnyebb keresésért
            res_dict = response.model_dump() if hasattr(response, 'model_dump') else str(response)
            
            # Megpróbáljuk a standard SDK útvonalat
            if hasattr(response, 'candidates') and response.candidates:
                for candidate in response.candidates:
                    if hasattr(candidate, 'content') and candidate.content:
                        for part in candidate.content.parts:
                            if hasattr(part, 'inline_data') and part.inline_data:
                                if hasattr(part.inline_data, 'data') and part.inline_data.data:
                                    audio_bytes = base64.b64decode(part.inline_data.data)
                                    break
                                    
            # TARTALÉK OPTIÓ: Ha az SDK struktúra változott, kézzel vadásszuk le a 'data' kulcsot a szótárból
            if not audio_bytes and isinstance(res_dict, dict):
                def find_audio_data(d):
                    if isinstance(d, dict):
                        for k, v in d.items():
                            if k == 'inline_data' and isinstance(v, dict) and 'data' in v:
                                return base64.b64decode(v['data'])
                            elif k == 'data' and isinstance(v, str) and len(v) > 1000:
                                try: return base64.b64decode(v)
                                except Exception: pass
                            ret = find_audio_data(v)
                            if ret: return ret
                    elif isinstance(d, list):
                        for item in d:
                            ret = find_audio_data(item)
                            if ret: return ret
                    return None
                audio_bytes = find_audio_data(res_dict)

        except Exception as json_e:
            print(f"Hiba a JSON parsolas kozben: {str(json_e)}")

        if audio_bytes:
            print(f"A Gemini gyári hangválasza sikeresen kicsomagolva! Méret: {len(audio_bytes)} bájt.")
            
            # Levágjuk az első 44 bájtot (WAV fejléc), hogy az ESP32 tiszta, nyers PCM bájtokat kapjon
            if len(audio_bytes) > 44:
                pcm_only = audio_bytes[44:]
                return send_file(io.BytesIO(pcm_only), mimetype='application/octet-stream')
            
            return send_file(io.BytesIO(audio_bytes), mimetype='application/octet-stream')
        else:
            # Ha nem jött hang, visszaküldjük a szöveget 200 OK-val, hogy az ESP32 kiírhassa!
            text_fallback = getattr(response, 'text', 'Ures valasz')
            print(f"A Gemini nem adott vissza hangot. Szöveges válasz lett: {text_fallback}")
            return f"HIBA: Nem erkezett hangadat. Szoveg: {text_fallback}", 200

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        # BIZTONSÁGI FIX: Kivétel esetén SEM dobunk 500-at, hanem visszaküldjük a hibát 200 OK-val!
        return f"HIBA: Szerveroldali hiba: {str(e)}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
