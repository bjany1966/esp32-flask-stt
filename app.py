import os
import io
import wave
import json
import asyncio
import subprocess
import tempfile

from flask import Flask, request, jsonify
from google import genai
from google.genai import types
import edge_tts


app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")


# ---------------------------------------------------
# PCM -> WAV (bejövő ESP32 mikrofon)
# ---------------------------------------------------

def pcm_to_wav(pcm_data):

    wav_io = io.BytesIO()

    with wave.open(wav_io, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(pcm_data)

    return wav_io.getvalue()



# ---------------------------------------------------
# Edge TTS MP3 készítés
# ---------------------------------------------------

async def create_tts(text):

    mp3_file = tempfile.NamedTemporaryFile(
        suffix=".mp3",
        delete=False
    )

    communicate = edge_tts.Communicate(
        text,
        voice="hu-HU-TamasNeural"
    )

    await communicate.save(mp3_file.name)

    return mp3_file.name



# ---------------------------------------------------
# MP3 -> PCM 16bit mono 16kHz
# ---------------------------------------------------

def mp3_to_pcm(mp3_path):

    pcm_file = tempfile.NamedTemporaryFile(
        suffix=".pcm",
        delete=False
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        mp3_path,
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        pcm_file.name
    ]

    subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    with open(pcm_file.name, "rb") as f:
        pcm = f.read()

    return pcm



# ---------------------------------------------------
# PCM byte -> JSON lista
# ---------------------------------------------------

def pcm_to_list(pcm):

    result = []

    for i in range(0, len(pcm), 2):

        if i + 1 < len(pcm):

            sample = int.from_bytes(
                pcm[i:i+2],
                byteorder="little",
                signed=True
            )

            result.append(sample)

    return result


@app.route("/upload", methods=["POST"])
def upload():

    try:

        pcm_data = request.data

        print("ESP32 hang:", len(pcm_data), "byte")

        # ... itt van a Gemini rész ...

        pcm = mp3_to_pcm(mp3)

        import base64

        audio_base64 = base64.b64encode(pcm).decode("ascii")

        return jsonify({
            "text": reply,
            "audio": audio_base64
        }), 200


    except Exception as e:

        print("HIBA:", e)

        return jsonify({
            "text": "Szerver hiba",
            "audio": ""
        }), 200


        print(
            "HIBA:",
            e
        )


        return jsonify({

            "text":
            "Szerver hiba",

            "audio":[]

        })




if __name__ == "__main__":

    port=int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
