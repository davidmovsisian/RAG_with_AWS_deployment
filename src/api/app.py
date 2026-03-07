import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

from worker.rag_worker import Worker

app = Flask(__name__)

# Global worker
worker = None

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
    top_k = data.get("top_k", 5)
    try:
        answer = worker.ask_question(question, top_k)
    except Exception as e:
        print(f"Error processing question: {e}")
        return jsonify({
            "error": "Error processing question",
            "details": str(e)
        }), 500

    return answer

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
    worker = Worker()
    print("Worker initialized successfully")
    port = int(os.getenv("FLASK_PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)