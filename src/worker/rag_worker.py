import os
import threading
import boto3
from flask import FileStorage, jsonify
from Lesson5.HW.infrastructure import worker
from Lesson5.HW.src.worker import sqs_worker
from Lesson5.HW.src.worker import sqs_worker
from utils.gemini_client import GeminiClient
from utils.opensearch_client import OpenSearchClient
from utils.s3_client import S3Client
from utils.chunking import TextChunker
from worker.document_processor import DocumentProcessor
from worker.sqs_worker import SQSWorker
import threading

class Worker:
    """
    Manages all clients and services for the RAG system.
    """
    def __init__(self):
        print("Initializing Worker...")
        
        # Initialize AWS clients
        region = os.getenv("AWS_REGION", "us-east-1")
        self.sqs_client = boto3.client("sqs", region_name=region)
        
        # Initialize service clients
        self.s3_client = S3Client()
        self.gemini_client = GeminiClient()
        self.opensearch_client = OpenSearchClient()
        self.text_chunker = TextChunker()
        # create index        
        self.opensearch_client.create_index()
        # document processor
        self.document_processor = DocumentProcessor(
            self.gemini_client,
            self.opensearch_client,
            self.text_chunker
        )
        self.sqs_worker = SQSWorker(self.sqs_client, self.s3_client, self.document_processor)
        self.sqs_worker_thread = None
        
    def upload_file(self, file:FileStorage) -> bool:
        try:
            content = file.read()
            self.s3_client.upload_file(content, key=file.filename)
        except Exception as e:
            raise

    def ask_question(self, question:str, top_k:int=5) ->str:
        try:
            question_embedding = self.gemini_client.get_embedding(question)
            chunks = self.opensearch_client.search(question_embedding, top_k=top_k)
            if not chunks:
                return jsonify({"error": "No documents indexed. Upload documents first."}), 400
            context_parts = []         
            for i, result in enumerate(chunks):
                context_parts.append(f"[{i+1}] {result['content']}")
            context = "\n\n".join(context_parts)
            answer = self.gemini_client.generate_answer(context, question)
            return jsonify({"question": question, "top_k": top_k, "context": chunks, "answer": answer})
        except Exception as e:
            raise
        
    def health_check(self) -> dict:
        status = {
            "status": "healthy",
            "services": {
                "s3": "unknown",
                "opensearch": "unknown",
                "gemini": "unknown",
                "sqs": "unknown"
            }
        }
        try:
            self.s3_client.client.list_buckets()
            status["services"]["s3"] = "healthy"
        except Exception as e:
            status["services"]["s3"] = "unhealthy"
            status["status"] = "degraded"
        try:
            self.opensearch_client.client.ping()
            status["services"]["opensearch"] = "healthy"
        except Exception as e:
            status["services"]["opensearch"] = "unhealthy"
            status["status"] = "degraded"
        try:
            self.gemini_client.get_embedding("health check")
            status["services"]["gemini"] = "healthy"
        except Exception as e:
            status["services"]["gemini"] = "unhealthy"
            status["status"] = "degraded"
        try:
            response = self.sqs_client.send_message(
                QueueUrl=self.sqs_worker.queue_url,
                MessageBody="health check"
            )
            if response.get("MessageId"):
                status["services"]["sqs"] = "healthy"
        except Exception as e:
            status["services"]["sqs"] = "unhealthy"
            status["status"] = "degraded"

        return status
    
    def start_sqs_worker(self):
        if self.sqs_worker_thread and self.sqs_worker_thread.is_alive():
            print("SQS Worker is already running.")
            return
        self.sqs_worker_thread = threading.Thread(target=self.sqs_worker.poll_and_process, daemon=True)
        self.sqs_worker_thread.start()
        print("SQS Worker started.")
    
    def stop_sqs_worker(self):
        if self.sqs_worker_thread and self.sqs_worker_thread.is_alive():
            print("Stopping SQS Worker...")
            self.sqs_worker.stop()
            self.sqs_worker_thread.join(timeout=10)
            print("SQS Worker stopped.")
        else:
            print("SQS Worker is not running.")