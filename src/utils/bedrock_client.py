import os
from typing import List
import json
import boto3
from botocore.exceptions import ClientError

class BedrockClient:
    def __init__(self):
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "amazon.titan-embed-text-v1")
        self.llm_model = os.getenv("LLM_MODEL", "us.anthropic.claude-3-5-haiku-20241022-v1:0")
        self.max_tokens = int(os.getenv("MAX_TOKENS", "4096"))
        self.temperature = float(os.getenv("TEMPERATURE", "0.7"))
        self.region = os.getenv("AWS_REGION", "us-east-1")
        self.client = boto3.client("bedrock-runtime", region_name=self.region)

        print("BedrockClient initialized")

    def get_embedding(self, text: str) -> List[float]:
        body = json.dumps({
            "inputText": text,
        })

        try:
            response = self.client.invoke_model(
                body=body, 
                modelId=self.embedding_model, 
                accept="application/json", 
                contentType="application/json"
            )

            # Parse the response body
            response_body = json.loads(response.get("body").read())
            
            # Titan returns the vector in the 'embedding' field
            embedding = response_body.get("embedding")
            
            return embedding

        except Exception as e:
            print(f"Error generating embedding: {e}")
            raise

    def generate_answer(self, context, question):
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": f"Answer the question based ONLY on the following context:\n{context}",
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": question}]}
            ]
        }

        try:
            resp = self.client.invoke_model(modelId=self.llm_model, body=json.dumps(body))
            payload = resp["body"].read() if hasattr(resp.get("body"), "read") else resp["body"]
            data = json.loads(payload)

            parts = data.get("content", [])
            text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
            return text.strip()
        except ClientError as e:
            raise RuntimeError(f"Bedrock InvokeModel failed: {e.response.get('Error', {}).get('Message')}") from e    