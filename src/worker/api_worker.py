import os
from utils.gemini_client import GeminiClient
from utils.opensearch_client import OpenSearchClient
from utils.s3_client import S3Client

class ApiWorker:
    def __init__(self):
        print("Initializing ApiWorker...")
        
        self.s3_client = S3Client()
        self.gemini_client = GeminiClient(pool_size=int(os.getenv("GEMINI_POOL_SIZE", "5")))
        self.opensearch_client = OpenSearchClient()
        print("ApiWorker initialized successfully")
        
    def ask_question(self, question:str, top_k:int=5) ->dict:
        question_embedding = self.gemini_client.get_embedding(question, is_query=True)
        chunks = self.opensearch_client.search(question_embedding, top_k=top_k)
        if not chunks:
            return {"error": "No documents indexed. Upload documents first."}
        context_parts = []         
        for i, result in enumerate(chunks):
            context_parts.append(f"[{i+1}] {result['content']}")
        context = "\n\n".join(context_parts)
        answer = self.gemini_client.generate_answer(context, question)
        return {"question": question, "top_k": top_k, "context": chunks, "answer": answer}
        
    def health_check(self) -> dict:
        status = {
            "status": "healthy",
            "services": {
                "s3": "unknown",
                "opensearch": "unknown",
                "gemini": "unknown",
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
        
        return status