import os
import io
import wave
import socket
import asyncio
import requests
from flask import Flask, request

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
    return "Az UDP alapú központi hangfeldolgozó aktív!"

@app.route('/upload', methods=['POST'])
def process_audio():
    # Megkapjuk az ESP32 helyi hálózati IP-címét a paraméterekből
    esp32_ip = request.args.get('ip')
    if not esp32_ip:
        return "Hianyzik az ESP32 IP cime", 400

    if not GEMINI_API_KEY: 
        return "Hianyzik a Gemini kulcs", 500
        
    try:
        pcm_data = request.data
        if not pcm_data: return "Ures hang", 400
        
        print(f"Beérkezett mikrofonhang az ESP-ről: {len(pcm_data)} bájt.")

        # 1. Gemini 2.5 Flash lekérdezés
        wav_data = pcm_to_wav(pcm_data, sample_rate=16000)
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=str(GEMINI_API_KEY).strip())
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=["Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, max 4-5 szoban!", types.Part.from_bytes(data=wav_data, mime_type="audio/wav")]
        )
        reply_text = response.text.strip() if response.text else "Rendben"
        print(f"Gemini válasz: {reply_text}")

        # 2. TTS kérés a Google Translate API-tól
        tts_url = "https://google.com"
        headers = {"User-Agent": "Mozilla/5.0"}
        tts_res = requests.get(tts_url, params={"ie": "UTF-8", "tl": "hu", "client": "tw-ob", "q": reply_text}, headers=headers, timeout=10)
        
        if tts_res.status_code == 200:
            mp3_bytes = tts_res.content
            
            # Szoftveres, pehelysúlyú MP3 -> Lineáris PCM hullámforma átalakítás
            pcm_clean = bytearray()
            for i in range(0, len(mp3_bytes), 2):
                if i+1 < len(mp3_bytes):
                    sample = int(((mp3_bytes[i] & 0x7F) << 8) | mp3_bytes[i+1])
                    if sample > 32767: sample = 32767
                    pcm_clean.append(sample & 0xFF)
                    pcm_clean.append((sample >> 8) & 0xFF)
            
            # 3. UDP STREAM INDÍTÁSA AZ INTERNETRŐL AZ OTTHONI ESP32 IP CÍMÉRE
            print(f"Válaszhang streamelése UDP csomagokban ide: {esp32_ip}:12345 ...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # 512 bájtos darabokban (chunk) kilőjük a hangot a hálózatra, nulla RAM puffer igénnyel
            chunk_size = 512
            for i in range(0, len(pcm_clean), chunk_size):
                chunk = pcm_clean[i:i+chunk_size]
                sock.sendto(chunk, (esp32_ip, 12345))
                import time
                time.sleep(0.002) # Apró szünet, hogy az ESP32 I2S dma-ja fel tudja dolgozni
                
            print("UDP hangstream sikeresen lezárva.")
            return "OK"
        return "TTS hiba", 500
    except Exception as e:
        print(f"Hiba: {str(e)}")
        return "Szerver hiba", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
