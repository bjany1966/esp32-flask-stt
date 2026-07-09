import os
import io
import wave
import base64
import requests
from flask import Flask, request, Response, stream_with_context
from google import genai
from google.genai import types

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

@app.route('/')
def index():
    return "A kozponti direkt Gemini PCM hang- es szovegserver aktiv!"

@app.route('/upload', methods=['POST'])
def process_audio():
    if not GEMINI_API_KEY: 
        print("HIBA: Hianyzik a GEMINI_API_KEY a Render beallitasaibol!")
        return "HIBA: Hianyzik a Gemini API kulcs.", 200
        
    try:
        pcm_data = request.data
        if not pcm_data or len(pcm_data) < 1000: 
            print("HIBA: Ures vagy hibas mikrofonhang jott az ESP-rol.")
            return "HIBA: Ures hangadat.", 200
            
        print(f"Mikrofonhang beerkezett az ESP-ről: {len(pcm_data)} bajt.")

        # 1. Mikrofon PCM -> WAV konverzió a Gemini bemenetéhez
        wav_bytes = pcm_to_wav(pcm_data, sample_rate=16000)
        
        clean_key = str(GEMINI_API_KEY).replace("\n", "").replace("\r", "").strip()
        client = genai.Client(api_key=clean_key)
        
        audio_part = types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav")

        print("Küldés a Google Gemini felé... Direkt PCM HANG válasz kérése.")
        
        # JAVÍTVA: Az új google-genai SDK szerinti pontos, hajszálpontos alsó vonalas konfiguráció
        # Kényszerítjük a Geminit, hogy hangbájtokat gyártson le, ne pedig tömörített MP3-at!
        config = types.GenerateContentConfig(
            response_mime_type="audio/pcm",
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Puck" # Kiváló minőségű, tiszta férfi beszédhang
                    )
                )
            )
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                "Valaszolj a hallott hangra tisztan magyarul, nagyon roviden, ekezetek nelkul, maximum 4-5 szoban!", 
                audio_part
            ],
            config=config
        )
        
        # 2. Kivesszük a szöveges és a hang választ a Google közös válaszobjektumából
        reply_text = "Rendben"
        raw_voice_bytes = b""
        
        try:
            # Végigmegyünk a válasz részein
            for part in response.candidates[0].content.parts:
                if part.text:
                    reply_text = part.text.strip()
                if part.inline_data and part.inline_data.data:
                    raw_voice_bytes = base64.b64decode(part.inline_data.data)
        except Exception as e:
            print(f"SDK adatbontási hiba: {str(e)}")

        print(f"Gemini szöveges válasza: {reply_text}")
        print(f"Gemini gyári PCM hangválasza: {len(raw_voice_bytes)} bájt.")

        # Létrehozzuk a fix, 128 bájtos szöveges fejlécet az ESP32 soros monitorának
        header_packet = bytearray(128)
        text_bytes = reply_text.encode('utf-8')[:127]
        header_packet[:len(text_bytes)] = text_bytes
        
        # Összefűzzük a tiszta szöveget és a Google által gyártott nyers, tömörítetlen hangot
        final_payload = header_packet + raw_voice_bytes
        
        # 3. DARABOLT (CHUNKED) ÁTVITEL AZ ESP32 SZÁMÁRA
        def generate_chunks():
            chunk_size = 1024
            for i in range(0, len(final_payload), chunk_size):
                yield bytes(final_payload[i:i+chunk_size])
        
        print(f"Minden kész! Stream indítása az ESP32 felé. Teljes méret: {len(final_payload)} bájt.")
        return Response(stream_with_context(generate_chunks()), mimetype='application/octet-stream')
            
    except Exception as e:
        print(f"Súlyos hiba a szerveren: {str(e)}")
        return f"HIBA: Szerveroldali hiba: {str(e)}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
