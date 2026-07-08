from flask import Flask, request, jsonify
from pathlib import Path

app = Flask(__name__)
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.get("/")
def home():
    return "OK"

@app.post("/upload")
def upload():
    data = request.get_data(cache=False, as_text=False, parse_form_data=False)
    if not data:
        return jsonify({"error": "no data"}), 400

    path = UPLOAD_DIR / "audio.raw"
    path.write_bytes(data)

    return jsonify({"text": "teszt valasz", "size": len(data)})
