from utils.opensearch_client import OpenSearchClient
from utils.s3_client import S3Client
from utils.bedrock_client import BedrockClient
import logging
import os

logger = logging.getLogger(__name__)
def configure_logging() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )

configure_logging()

class ApiWorker:
    def __init__(self):
        logger.info("Initializing ApiWorker...")
                
        self.s3_client = S3Client()
        self.bedrock_client = BedrockClient()
        self.opensearch_client = OpenSearchClient()
        
    def ask_question(self, question:str, top_k:int=5) ->dict:
        logger.info(f"Received question: '{question}' with top_k={top_k}")
        try:
            question_embedding = self.bedrock_client.get_embedding(question)
            chunks = self.opensearch_client.search(question_embedding, top_k=top_k)
            if not chunks:
                return {"error": "No documents indexed. Upload documents first."}
            context_parts = []         
            for i, result in enumerate(chunks):
                context_parts.append(f"[{i+1}] {result['content']}")
            context = "\n\n".join(context_parts)
            answer = self.bedrock_client.generate_answer(context, question)
            logger.info(f"Generated answer: {answer}")
            return {"question": question, "top_k": top_k, "context": chunks, "answer": answer}
        except Exception as e:
            logger.error(f"Error processing question: {e}")
            return {"error": str(e)}
        
    def upload_files(self, files):
        logger.info(f"Uploading {len(files)} files")
        try:
            for file in files:
                self.s3_client.upload_file(file)
        except Exception as e:
            logger.error(f"Error uploading files: {e}") 
            raise
        
    def list_files(self):
        logger.info("Listing files in S3 bucket")
        try:
            return self.s3_client.list_files()
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return []
    
    def delete_file(self, filename: str):
        logger.info(f"Deleting file: {filename}")
        try:
            self.s3_client.delete_file(filename)
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            raise

    def check_document_indexed(self, filename: str, isExists: bool = True) -> bool:
        logger.info(f"Checking if document is indexed: {filename}")
        try:
            return self.opensearch_client.check_document_indexed(filename, isExists=isExists)
        except Exception as e:
            logger.error(f"Error checking if document is indexed: {e}")
            return False