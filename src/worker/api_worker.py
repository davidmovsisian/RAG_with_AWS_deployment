from utils.bedrock_client import BedrockClient
from utils.s3_client import S3Client

class ApiWorker:
    def __init__(self):
        print("Initializing ApiWorker...")
        
        self.s3_client = S3Client()
        self.bedrock_client = BedrockClient()
        print("ApiWorker initialized successfully")
        
    def ask_question(self, question:str, top_k:int=3) ->dict:
        answer = self.bedrock_client.retrieve_and_generate(question, top_k=top_k) 
        return {"answer": answer}
    
    def upload_files(self, files):
        for file in files:
            self.s3_client.upload_file(file)
        job_id = self.bedrock_client.sync_data()
        return job_id

    def delete_file(self, filename: str):
        self.s3_client.delete_file(filename)
        job_id = self.bedrock_client.sync_data()
        return job_id
    
    def check_sync_completion(self, job_id) -> str:
        return self.bedrock_client.check_for_sync_completion(job_id)        
