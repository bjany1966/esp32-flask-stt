import os
import base64
from flask import Flask, request
from google import genai
from google.genai import types

app = Flask(__name__)

# A hivatalos Google kliens inicializálása a Render környezeti változóból
# Fontos: A kliens automatikusan a GEMINI_API_KEY nevű változót keresi!
client = None
if os.environ.get("GEMINI_API_KEY"):
    client = genai.Client()

@app.route('/')
def index():
    return "A kozponti hangfeldolgozo szerver aktiv es mukodik!"

@app.route('/upload', methods=['POST'])
def process_audio():
    global client
    
    # Ha indításkor nem volt meg a kulcs, megpróbáljuk újra beolvasni
    if not client:
        if os.environ.get("GEMINI_API_KEY"):
            client = genai.Client()
        else:
            print("HIBA: A GEMINI_API_KEY nincs beallitva a Renderen.")
            return "HIBA: Hianyzik a Gemini API kulcs a Render beallitasaibol.", 200

    try:
        # Beérkező nyers bájtok fogadása az ESP32-ről
        audio_data = request.data
        if not audio_data or len(audio_data) < 1000:
            print(f"HIBA: Tul rovid adat erkezett! Meret: {len(audio_data)} bajt.")
            return "HIBA: Tul rovid vagy ures hangfajl erkezett.", 200
            
        print(f"Sikeresen beerkezett a hang az ESP-rol! Meret: {len(audio_data)} bajt.")

        # Hang előkészítése a hivatalos Google formátumra
        audio_part = types.Part.from_bytes(
            data=audio_data,
            mime_type="audio/pcm;rate=16000"
        )

        print("Kuldes a Gemini API-nak a hivatalos Google SDK-val...")
        
        # Tartalom generálása a hivatalos és legújabb v1-es metódussal
        response = client.models.generate_content(
            model='gemini-1.5-flash',
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
            print(f"Üres válasz érkezett a Geminitől: {response}")
            return "HIBA: A Gemini valasza ures volt.", 200

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        return f"HIBA: Google SDK hiba: {str(e)}", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
