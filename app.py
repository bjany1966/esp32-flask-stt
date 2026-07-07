from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from pathlib import Path

app = Flask(__name__)
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.get("/")
def home():
    return "OK"

@app.post("/upload")
def upload():
    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "empty filename"}), 400

    name = secure_filename(f.filename)
    path = UPLOAD_DIR / name
    f.save(path)

    return jsonify({"text": "teszt valasz", "saved": name})
