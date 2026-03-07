import os
import sys
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from worker.rag_worker import RagWorker

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

app = Flask(__name__, static_folder='static', static_url_path='')

# Global worker
worker = None

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route("/health", methods=["GET"])
def health_check():
    status = worker.health_check()
    http_status = 200 if status["status"] == "healthy" else 503
    return jsonify(status), http_status

@app.route("/ask", methods=["POST"])
def ask_question():
    data = request.get_json()
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "Question is required"}), 400
    top_k = min(data.get("top_k", 5), 5)
    try:
        answer = worker.ask_question(question, top_k)
    except Exception as e:
        print(f"Error processing question: {e}")
        return jsonify({
            "error": "Error processing question",
            "details": str(e)
        }), 500

    if "error" in answer: 
        return jsonify(answer), 400  
    return jsonify(answer), 200

@app.route("/upload", methods=["POST"])
def upload_file():
    if "files" not in request.files:
        return jsonify({"error": "No files in request"}), 400
    files = request.files.getlist("files")
    for f in files:
        if f.filename and f.filename.lower().endswith(".txt"):
            try:
                worker.upload_file(f)
            except Exception as e:
                print(f"Error uploading file: {e}")
                return jsonify({
                    "error": f"An error occurred while uploading the file {f.filename}",
                    "details": str(e)
                }), 500
    return jsonify({"message": "Files uploaded successfully"})

if __name__ == "__main__":
    worker = RagWorker()
    print("RagWorker initialized successfully")
    port = int(os.getenv("FLASK_PORT", "5000"))
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    app.run(host=host, port=port, debug=True)