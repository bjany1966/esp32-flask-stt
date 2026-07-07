from flask import Flask, request, jsonify
from pathlib import Path
from werkzeug.utils import secure_filename

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

    filename = secure_filename("audio.raw")
    path = UPLOAD_DIR / filename
    with open(path, "wb") as f:
        f.write(data)

    return jsonify({"text": "teszt valasz", "saved": filename, "size": len(data)})
