import os
import io
import wave
import base64
import tempfile
import subprocess

from flask import Flask, request, jsonify
from gtts import gTTS

from google import genai
from google.genai import types


app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")


def wav_from_pcm(pcm_data):
    wav_io = io.BytesIO()

    with wave.open(wav_io, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(pcm_data)

    return wav_io.getvalue()



def mp3_to_pcm(mp3_bytes):

    with tempfile.NamedTemporaryFile(
        suffix=".mp3"
    ) as mp3_file:

        with tempfile.NamedTemporaryFile(
            suffix=".pcm"
        ) as pcm_file:


            mp3_file.write(mp3_bytes)
            mp3_file.flush()


            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                mp3_file.name,
                "-ar",
                "16000",
                "-ac",
                "1",
                "-f",
                "s16le",
                pcm_file.name
            ]


            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )


            pcm_file.seek(0)

            pcm = pcm_file.read()
            pcm = pcm[:24000]

    return pcm



@app.route("/")
def home():

    return "ESP32 Voice Server OK"



@app.route("/upload", methods=["POST"])
def upload():

    try:

        pcm_input = request.data


        print(
            "ESP32 hang:",
            len(pcm_input),
            "byte"
        )


        if len(pcm_input) < 1000:

            return jsonify({
                "text": "Nincs hang",
                "audio": ""
            })


        # Gemini kliens

        client = genai.Client(
            api_key=GEMINI_API_KEY.strip()
        )


        wav_bytes = wav_from_pcm(
            pcm_input
        )


        audio_part = types.Part.from_bytes(
            data=wav_bytes,
            mime_type="audio/wav"
        )


        response = client.models.generate_content(

            model="gemini-2.5-flash",

            contents=[

                "Válaszolj magyarul maximum egy rövid mondatban. Ne magyarázz.",

                audio_part

            ]

        )


        if response.text:

            answer = response.text.strip()
            answer = answer[:60]

        else:

            answer = "Rendben"


        print(
            "Gemini:",
            answer
        )


        # TTS

        tts = gTTS(
            text=answer,
            lang="hu",
            slow=False
        )


        mp3_buffer = io.BytesIO()

        tts.write_to_fp(
            mp3_buffer
        )


        mp3_bytes = mp3_buffer.getvalue()


        print(
            "MP3:",
            len(mp3_bytes),
            "byte"
        )



        # MP3 -> PCM

        pcm_output = mp3_to_pcm(
            mp3_bytes
        )


        print(
            "PCM:",
            len(pcm_output),
            "byte"
        )


        audio64 = base64.b64encode(
            pcm_output
        ).decode("ascii")


        print(
            "Base64:",
            len(audio64)
        )


        return jsonify({

            "text": answer,

            "audio": audio64

        })


    except Exception as e:


        print(
            "HIBA:",
            str(e)
        )


        return jsonify({

            "text": "Szerver hiba",

            "audio": ""

        })



if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )


    app.run(
        host="0.0.0.0",
        port=port
    )
