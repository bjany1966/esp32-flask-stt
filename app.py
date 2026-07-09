import os
import io
import base64
import subprocess
import tempfile

from flask import Flask, request, jsonify
from gtts import gTTS

from google import genai
from google.genai import types


app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")


def pcm_to_base64(mp3_bytes):
    """
    MP3 -> 16bit PCM 16000Hz mono
    """

    with tempfile.NamedTemporaryFile(
        suffix=".mp3",
        delete=True
    ) as mp3_file:

        with tempfile.NamedTemporaryFile(
            suffix=".raw",
            delete=True
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
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )


            pcm_file.seek(0)

            pcm_data = pcm_file.read()
            # ESP32 teszthez rövidebb hang
pcm_data = pcm_data[:32000]


    return base64.b64encode(
        pcm_data
    ).decode("ascii")



@app.route("/")
def index():

    return "ESP32 Gemini Voice Server OK"



@app.route("/upload", methods=["POST"])
def upload():

    try:

        pcm_data = request.data


        print(
            "ESP32 hang:",
            len(pcm_data),
            "byte"
        )

        if not pcm_data:

            return jsonify({
                "text":"Nincs hang",
                "audio":""
            })


        if not GEMINI_API_KEY:

            return jsonify({
                "text":"Hiányzik API kulcs",
                "audio":""
            })



        # WAV készítés Geminihez

        import wave


        wav_buffer = io.BytesIO()


        with wave.open(
            wav_buffer,
            "wb"
        ) as wav:

            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)

            wav.writeframes(
                pcm_data
            )


        wav_bytes = wav_buffer.getvalue()



        # Gemini

        client = genai.Client(
            api_key=GEMINI_API_KEY.strip()
        )


        audio_part = types.Part.from_bytes(
            data=wav_bytes,
            mime_type="audio/wav"
        )


        response = client.models.generate_content(

            model="gemini-2.5-flash",

            contents=[

                "Válaszolj magyarul nagyon röviden, maximum 5 szóban.",

                audio_part

            ]

        )


        if response.text:

            reply_text = response.text.strip()

        else:

            reply_text = "Rendben"



        print(
            "Gemini:",
            reply_text
        )



        # TTS

        tts = gTTS(
            text=reply_text,
            lang="hu",
            slow=False
        )


        mp3_buffer = io.BytesIO()


        tts.write_to_fp(
            mp3_buffer
        )


        mp3_bytes = mp3_buffer.getvalue()



        print(
            "MP3 méret:",
            len(mp3_bytes)
        )



        # MP3 -> PCM -> Base64

        audio_base64 = pcm_to_base64(
            mp3_bytes
        )


        print(
            "PCM Base64 méret:",
            len(audio_base64)
        )



        return jsonify({

            "text": reply_text,

            "audio": audio_base64

        }),200



    except Exception as e:


        print(
            "HIBA:",
            str(e)
        )


        return jsonify({

            "text":"Szerver hiba",

            "audio":""

        }),200




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
