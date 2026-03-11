import os
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
from worker.rag_worker import RagWorker
import atexit
import signal

# shutdown handler to stop the sqs_worker thread on exit
# def _shutdown(*_args):
#     if worker:
#         worker.stop_sqs_worker()

# atexit.register(_shutdown)
# signal.signal(signal.SIGINT, _shutdown)
# signal.signal(signal.SIGTERM, _shutdown)

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

app = Flask(__name__, static_folder='static', static_url_path='')

# Global worker
worker = None
def init_worker():
    """Initialize RagWorker (called once at startup)"""
    global worker
    if worker is None:
        worker = RagWorker()
        worker.start_sqs_worker()
        print("RagWorker initialized and SQS worker started")


def shutdown_handler(*_args):
    global worker
    if worker:
        print("Shutting down worker...")
        worker.stop_sqs_worker()
        print("Worker stopped")


# Register shutdown handlers
atexit.register(shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)


@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route("/health", methods=["GET"])
def health_check():
    status = worker.health_check()
    http_status = 200 if status["status"] == "healthy" else 503
    return jsonify(status), http_status

# return list of indexed documents
@app.route("/list-files", methods=["GET"])
def list_docs():
    try:
        files = worker.s3_client.list_files()
        return jsonify({"files": files}), 200
    except Exception as e:
        print(f"Error listing documents: {e}")
        return jsonify({
            "error": "Error listing documents",
            "details": str(e)
        }), 500
    
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
            print(f"Uploading file: {f.filename}")
            try:
                worker.s3_client.upload_file(f)
            except Exception as e:
                print(f"Error uploading file: {e}")
                return jsonify({
                    "error": f"An error occurred while uploading the file {f.filename}",
                    "details": str(e)
                }), 500
    return jsonify({"message": "Files uploaded successfully"})

@app.route("/delete-file", methods=["DELETE"])
def delete_file():
    data = request.get_json()
    filename = data.get("filename", "").strip()
    if not filename:
        return jsonify({"error": "Filename is required"}), 400
    try:
        worker.s3_client.delete_file(filename)
    except Exception as e:
        print(f"Error deleting file: {e}")
        return jsonify({
            "error": f"An error occurred while deleting the file {filename}",
            "details": str(e)
        }), 500
    return jsonify({"message": f"File {filename} deleted successfully"}), 200
    
if __name__ == "__main__":
    init_worker()
    port = int(os.getenv("FLASK_PORT", "5000"))
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    print("Running Flask dev server (use Gunicorn in production)")
    app.run(host=host, port=port, debug=False, use_reloader=False)