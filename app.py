import os
import base64
from flask import Flask, request
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
            print("HIBA: A GEMINI_API_KEY nincs beallitva a Renderen.")
            return "HIBA: Hianyzik a Gemini API kulcs a Render beallitasaibol.", 200

    try:
        audio_data = request.data
        if not audio_data or len(audio_data) < 1000:
            print(f"HIBA: Tul rovid adat erkezett! Meret: {len(audio_data)} bajt.")
            return "HIBA: Tul rovid vagy ures hangfajl erkezett.", 200
            
        print(f"Sikeresen beerkezett a hang az ESP-rol! Meret: {len(audio_data)} bajt.")

        audio_part = types.Part.from_bytes(
            data=audio_data,
            mime_type="audio/pcm;rate=16000"
        )

        print("Kuldes a Gemini API-nak a hivatalos Google SDK-val...")
        
        # PONTOSÍTVA: A Google által elvárt 'models/' előtag hozzáadása a 404-es hiba ellen
        response = client.models.generate_content(
            model='models/gemini-1.5-flash',
            contents=[
                "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 5-6 szoban!",
                audio_part
            ]
        )
        
        if response.text:
            reply = response.text.strip()
            print(f"Sikeres Gemini valasz: {reply}")
            return reply
        else:
            print(f"Ures valasz erkezett a Geminitol: {response}")
            return "HIBA: A Gemini valasza ures volt.", 200

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        return f"HIBA: Google SDK hiba: {str(e)}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
