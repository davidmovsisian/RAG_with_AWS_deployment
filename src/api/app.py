import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

from worker.rag_worker import Worker

app = Flask(__name__)

# Global worker
worker = None

@app.route("/health", methods=["GET"])
def health_check() -> tuple:
    status = worker.health_check()
    http_status = 200 if status["status"] == "healthy" else 503
    return jsonify(status), http_status


@app.route("/ask", methods=["POST"])
def ask_question() -> tuple:
    """
    Answer a question using RAG (Retrieval-Augmented Generation).
    
    Expects JSON body:
        {
            "question": "your question here",
            "top_k": 5  # optional, defaults to 5
        }
    
    Returns:
        JSON response with answer and sources
    """
    # Validate request
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400
    
    data = request.get_json()
    question = data.get("question", "").strip()
    top_k = data.get("top_k", 5)
    
    if not question:
        return jsonify({"error": "Question is required"}), 400
    
    if not isinstance(top_k, int) or top_k < 1 or top_k > 20:
        return jsonify({"error": "top_k must be an integer between 1 and 20"}), 400
    
    try:
        print(f"Processing question: {question}")
        
        gemini_client = worker.get_gemini_client()
        opensearch_client = worker.get_opensearch_client()
        
        # Step 1: Generate embedding for the question
        print("Generating question embedding...")
        question_embedding = gemini_client.get_embedding(question)
        
        # Step 2: Search OpenSearch for similar documents
        print(f"Searching OpenSearch for top {top_k} results...")
        search_results = opensearch_client.search(
            query_embedding=question_embedding.tolist(),
            top_k=top_k
        )
        
        if not search_results:
            return jsonify({
                "answer": "I couldn't find any relevant information to answer your question.",
                "sources": []
            }), 200
        
        # Step 3: Build context from retrieved chunks
        context_parts = []
        sources = []
        
        for i, result in enumerate(search_results):
            context_parts.append(f"[{i+1}] {result['content']}")
            sources.append({
                "chunk_id": i + 1,
                "filename": result["metadata"].get("filename", "unknown"),
                "score": result["score"],
                "content_preview": result["content"][:200] + "..." if len(result["content"]) > 200 else result["content"]
            })
        
        context = "\n\n".join(context_parts)
        print(f"Built context from {len(search_results)} chunks")
        
        # Step 4: Generate answer using Gemini LLM
        print("Generating answer with Gemini LLM...")
        answer = gemini_client.generate_answer(context, question)
        
        print("Answer generated successfully")
        return jsonify({
            "answer": answer,
            "sources": sources
        }), 200
        
    except Exception as e:
        print(f"Error processing question: {e}")
        return jsonify({
            "error": "An error occurred while processing your question",
            "details": str(e)
        }), 500


@app.route("/upload", methods=["POST"])
def upload_file() -> tuple:
    """
    Optional endpoint to upload a file directly to S3.
    Triggers document processing via S3 event -> SQS -> Worker.
    
    Expects:
        multipart/form-data with file field
    
    Returns:
        JSON response with upload confirmation
    """
    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400
    
    file = request.files["file"]
    
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    
    try:
        print(f"Uploading file: {file.filename}")
        
        s3_client = worker.get_s3_client()
        
        # Read file content
        content = file.read()
        
        # Upload to S3 (this will trigger S3 event -> SQS -> Worker)
        success = s3_client.upload_file_content(file.filename, content)
        
        if success:
            return jsonify({
                "message": "File uploaded successfully",
                "filename": file.filename,
                "status": "processing"
            }), 200
        else:
            return jsonify({"error": "Failed to upload file"}), 500
            
    except Exception as e:
        print(f"Error uploading file: {e}")
        return jsonify({
            "error": "An error occurred while uploading the file",
            "details": str(e)
        }), 500


@app.errorhandler(404)
def not_found(e) -> tuple:
    """Handle 404 errors."""
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(e) -> tuple:
    """Handle 500 errors."""
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    worker = Worker()
    print("Worker initialized successfully")
    
    # Get configuration from environment
    port = int(os.getenv("FLASK_PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)