import os
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
from worker.api_worker import ApiWorker

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

app = Flask(__name__, static_folder='static', static_url_path='')

# Global worker
worker = None
def init_worker():
    global worker
    if worker is None:
        worker = ApiWorker()

@app.route('/')
def index():
    if worker is None:  
        return jsonify({"error": "Worker not initialized"}), 503
    return send_from_directory(app.static_folder, 'index.html')

# return list of indexed documents
@app.route("/list-files", methods=["GET"])
def list_docs():
    if worker is None:  
        return jsonify({"error": "Worker not initialized"}), 503
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
    if worker is None:  
        return jsonify({"error": "Worker not initialized"}), 503
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

@app.route("/upload-files", methods=["POST"])
def upload_files():
    if worker is None:  
        return jsonify({"error": "Worker not initialized"}), 503
    if "files" not in request.files:
        return jsonify({"error": "No files in request"}), 400

    SUPPORTED_EXTENSIONS = ('.txt', '.pdf')
    uploaded_files = []
    
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files uploaded"}), 400
    
    bad_files = [f for f in files if not f.filename.lower().endswith(SUPPORTED_EXTENSIONS)]
    if bad_files:        
        print(f"Unsupported file type for files: {[f.filename for f in bad_files]}")
        return jsonify({
            "error": f"Unsupported file type for files: {[f.filename for f in bad_files]}"}), 400
    
    try:
        job_id = worker.upload_files(files)
        uploaded_files.append([f.filename for f in files])
        return jsonify({
            "message": "Files uploaded successfully", 
            "files": uploaded_files, 
            "job_id": job_id}), 200
    except Exception as e:
        print(f"Error uploading file: {e}")
        return jsonify({
            "error": f"An error occurred while uploading the files",
            "details": str(e)
        }), 500

@app.route("/delete-file", methods=["DELETE"])
def delete_file():
    if worker is None:  
        return jsonify({"error": "Worker not initialized"}), 503
    data = request.get_json()
    filename = data.get("filename", "").strip()
    if not filename:
        return jsonify({"error": "Filename is required"}), 400
    try:
        job_id = worker.delete_file(filename)
        return jsonify({
            "message": f"File {filename} deleted successfully",
            "job_id": job_id
        }), 200
    except Exception as e:
        print(f"Error deleting file: {e}")
        return jsonify({
            "error": f"An error occurred while deleting the file {filename}",
            "details": str(e)
        }), 500
    

# this endpoint is used to check sync status
@app.route("/check_sync_completion", methods=["POST"])
def check_sync_completion():
    """Check sync completion status for a given job ID."""
    if worker is None:  
        return jsonify({"error": "Worker not initialized"}), 503
    
    data = request.get_json()
    job_id = data.get("job_id", "").strip()
    
    if not job_id:
        return jsonify({"error": "No job ID provided"}), 400
    
    try:
        status = worker.check_sync_completion(job_id)
        return jsonify({
            "job_id": job_id,
            "status": status,
            "is_ready": status == "COMPLETED",
            "is_failed": status in ["FAILED", "STOPPED"]
        }), 200
    except Exception as e:
        print(f"Error checking status for {job_id}: {e}")
        return jsonify({
            "job_id": job_id,
            "error": str(e),
        }), 500
    
    

#application entry point - initialize worker and start Flask app 
init_worker()

if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", "5000"))
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    print("Running Flask dev server (use Gunicorn in production)")
    app.run(host=host, port=port, debug=False, use_reloader=False)