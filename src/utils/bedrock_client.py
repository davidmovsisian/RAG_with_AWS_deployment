import os
import boto3
from botocore.exceptions import BotoCoreError, ClientError
import json

class BedrockClient:
    def __init__(self):
        self.region = os.getenv("REGION", "us-east-1")
        self.kb_id = os.getenv("KNOWLEDGE_BASE_ID", "")
        self.data_source_id = os.getenv("DATA_SOURCE_ID", "")
        self.s3_bucket_arn = os.getenv("S3_BUCKET_ARN", "")
        self.model_id = os.getenv("MODEL_ID", "")
        # 1. Runtime for Knowledge Bases and Retrieval-Augmented Generation
        self.client_runtime = boto3.client("bedrock-agent-runtime", region_name=self.region)
        # 2. Agent for Syncing/Managing
        self.client_agent = boto3.client('bedrock-agent', region_name=self.region)
        # 3. Standard Runtime for direct Model Invocation (Claude)
        self.client_model = boto3.client("bedrock-runtime", region_name=self.region)

        print("Initializing BedrockClient...")

    def retrieve_and_generate(self, query_text, top_k=3) -> str:
        """
        Uses Amazon Bedrock Agent Runtime to retrieve relevant documents
        from a knowledge base and generate an answer.    
        """
        try:
            model_arn = f"arn:aws:bedrock:{self.region}::foundation-model/{self.model_id}"
            response = self.client_runtime.retrieve_and_generate(
                input={
                    "text": query_text
                },
                retrieveAndGenerateConfiguration={
                    "type": "KNOWLEDGE_BASE",
                    "knowledgeBaseConfiguration": {
                        "knowledgeBaseId": self.kb_id,
                        "modelArn": model_arn,
                        "retrievalConfiguration": {
                            "vectorSearchConfiguration": {
                                "numberOfResults": top_k
                            }
                        }  
                    }
                }
            )

            # Extract and print the generated output
            output_text = response.get("output", {}).get("text", "")
            # print("Generated Answer:\n", output_text)
            return output_text
        except (BotoCoreError, ClientError) as e:
            print(f"Error calling retrieve_and_generate: {e}")
            return None
        
    def sync_data(self):
        """Synchronize data from an S3 bucket to a Bedrock knowledge base."""
        print(f"Starting data sync for KB: {self.kb_id} with S3 bucket: {self.s3_bucket_arn}")
        self.client_agent.update_data_source(
            knowledgeBaseId=self.kb_id,
            dataSourceId=self.data_source_id,
            name='DataFolderOnly',
            dataSourceConfiguration={
            'type': 'S3',
            's3Configuration': {
                'bucketArn': self.s3_bucket_arn, 
                'inclusionPrefixes': ['data/'] # additional layer of filtering
            }
        }
    )
        # Trigger the sync
        response = self.client_agent.start_ingestion_job(knowledgeBaseId=self.kb_id, dataSourceId=self.data_source_id)
        job_id = response['ingestionJob']['ingestionJobId']
        return job_id

    def check_for_sync_completion(self, job_id) -> str:
        """Check for the completion of the sync job"""
        response = self.client_agent.get_ingestion_job(
            knowledgeBaseId=self.kb_id,
            dataSourceId=self.data_source_id,
            ingestionJobId=job_id
        )
        status = response['ingestionJob']['status']
        print(f"Current Status: {status}")
        return status

    def retrieve_from_kb(self, retriev_equery):
        """Uses Amazon Bedrock Agent Runtime to retrieve relevant documents from a knowledge base."""
        try:
            response = self.client_runtime.retrieve(
            knowledgeBaseId=self.kb_id,
            retrievalQuery={
                'text': retriev_equery
            },
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'numberOfResults': 3
                }
            }
        )
            results = response.get("retrievalResults", [])
            context = ""
            for idx, res in enumerate(results, start=1):
                # print(f"Document {idx}: {res['content']['text']}\n")
                context += f"{idx}: {res['content']['text']}\n"
            return context
        except (BotoCoreError, ClientError) as e:
            print(f"Error calling retrieve: {e}")
            return None

    def claude_complete(self, prompt: str) -> str:
        """Invokes the specified Bedrock model with the given prompt and returns the generated text."""
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 400,
            "temperature": 0.2,
            # optional "system": "You are a concise assistant.",
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": prompt}]}
            ]
        }

        try:
            resp = self.client_model.invoke_model(modelId=self.model_id, body=json.dumps(body))
            payload = resp["body"].read() if hasattr(resp.get("body"), "read") else resp["body"]
            data = json.loads(payload)

            parts = data.get("content", [])
            text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
            return text.strip()
        except ClientError as e:
            raise RuntimeError(f"Bedrock InvokeModel failed: {e.response.get('Error', {}).get('Message')}") from e
