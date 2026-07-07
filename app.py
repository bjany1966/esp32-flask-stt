from flask import Flask, request, jsonify

app = Flask(__name__)

@app.get("/")
def home():
    return "OK"

@app.post("/upload")
def upload():
    data = request.get_data()
    if not data:
        return jsonify({"error": "no data"}), 400
    with open("uploads/audio.raw", "wb") as f:
        f.write(data)
    return jsonify({"text": "teszt valasz"})
