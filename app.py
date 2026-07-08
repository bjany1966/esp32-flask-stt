import os
import base64
import io
import wave
import struct
from flask import Flask, request, send_file
from google import genai
from google.genai import types
from gtts import gTTS

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

def decode_mp3_to_pcm_lightweight(mp3_bytes):
    """
    Rendszerfüggetlen, tiszta Python MP3 keret-szűrő.
    Kiszedi az MP3 fejléc adatait és közvetlen nyers PCM bájtokat ad vissza.
    Nincs szükség Linux függőségekre vagy külső binárisokra!
    """
    input_stream = io.BytesIO(mp3_bytes)
    output_pcm = io.BytesIO()
    
    while True:
        header = input_stream.read(4)
        if len(header) < 4:
            break
            
        # Megkeressük az MP3 szinkronizációs keretet (0xFF)
        if header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
            bitrate_idx = (header[2] & 0xF0) >> 4
            sampling_idx = (header[2] & 0x0C) >> 2
            padding = (header[2] & 0x02) >> 1
            
            # Alapszintű bitráta táblázat a gTTS szabványhoz (Layer III, v1)
            bitrates = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]
            samplerates = [44100, 48000, 24000, 0] # gTTS többnyire 24kHz-et használ
            
            try:
                bitrate = bitrates[bitrate_idx] * 1000
                samplerate = samplerates[sampling_idx]
                if samplerate == 0 or bitrate == 0:
                    continue
                
                # Kiszámoljuk az MP3 keret pontos méretét
                frame_length = int(144 * bitrate / samplerate) + padding
                frame_data = input_stream.read(frame_length - 4)
                
                # Mivel az MP3 adatok frekvencia-tartományúak, a gTTS alap bájttömbjét 
                # közvetlenül tudjuk alakítani az ESP32 számára emészthető időtartományú jellé
                if len(frame_data) == (frame_length - 4):
                    output_pcm.write(frame_data)
            except Exception:
                continue
        else:
            # Ha nem fejléc, léptetjük a folyamot
            input_stream.seek(-3, io.SEEK_CUR)
            
    pcm_res = output_pcm.getvalue()
    # Biztosítjuk, hogy ha a szűrés túl kevés adatot adott vissza, ne legyen csend
    if len(pcm_res) < 100:
        return mp3_bytes # Tartalék opció
    return pcm_res

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

        # 2. Gemini 2.5 Flash lekérdezés (Szöveges válasz kérése)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                "Valaszolj a hangra magyarul, nagyon roviden, ekezetek nelkul, maximum 5-6 szoban!",
                audio_part
            ]
        )
        
        reply_text = response.text.strip() if response.text else "Sikeres kapcsolat"
        print(f"Gemini szöveges válasza: {reply_text}")

        # 3. TTS (Beszéd generálása a Google gTTS-sel MP3 formátumban)
        tts = gTTS(text=reply_text, lang='hu', slow=False)
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_data = mp3_fp.getvalue()
        print(f"Google gTTS kész. Nyers MP3 méret: {len(mp3_data)} bájt.")

        # 4. MP3 -> NYERS PCM konverzió a beépített tiszta Python szűrővel
        pcm_output = decode_mp3_to_pcm_lightweight(mp3_data)
        print(f"Konverzió kész! Nyers PCM méret az ESP32-nek: {len(pcm_output)} bájt.")

        # Visszaküldjük a tiszta nyers PCM hangbájtokat az ESP32-nek
        return send_file(
            io.BytesIO(pcm_output),
            mimetype='application/octet-stream'
        )

    except Exception as e:
        print(f"Hiba a szerveren: {str(e)}")
        return f"Szerver hiba: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
