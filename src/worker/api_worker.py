from utils.opensearch_client import OpenSearchClient
from utils.s3_client import S3Client
from utils.bedrock_client import BedrockClient

class ApiWorker:
    def __init__(self):
        print("Initializing ApiWorker...")
        
        self.s3_client = S3Client()
        self.bedrock_client = BedrockClient()
        self.opensearch_client = OpenSearchClient()
        print("ApiWorker initialized successfully")
        
    def ask_question(self, question:str, top_k:int=5) ->dict:
        question_embedding = self.bedrock_client.get_embedding(question)
        chunks = self.opensearch_client.search(question_embedding, top_k=top_k)
        if not chunks:
            return {"error": "No documents indexed. Upload documents first."}
        context_parts = []         
        for i, result in enumerate(chunks):
            context_parts.append(f"[{i+1}] {result['content']}")
        context = "\n\n".join(context_parts)
        answer = self.bedrock_client.generate_answer(context, question)
        return {"question": question, "top_k": top_k, "context": chunks, "answer": answer}
        
    def upload_files(self, files):
        for file in files:
            self.s3_client.upload_file(file)
    
    def list_files(self):
        return self.s3_client.list_files()
    
    def delete_file(self, filename: str):
        self.s3_client.delete_file(filename)

    def check_document_indexed(self, filename: str) -> bool:
        return self.opensearch_client.check_document_indexed(filename)