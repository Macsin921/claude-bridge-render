
from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({"status": "ok", "message": "Bridge is running"})

@app.route("/ping")
def ping():
    return jsonify({"status": "ok", "bridge": "render"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
