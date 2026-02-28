"""
Bedrock client for interacting with Amazon Bedrock embedding and LLM models.
"""

import json
import os
from typing import List

import boto3


class BedrockClient:
    """Client for Amazon Bedrock services (embeddings and text generation)."""

    def __init__(self):
        """Initialize Bedrock runtime client and load configuration from environment variables."""
        region = os.getenv("AWS_REGION", "us-east-1")
        self.client = boto3.client("bedrock-runtime", region_name=region)
        self.embedding_model_id = os.getenv(
            "BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v1"
        )
        self.llm_model_id = os.getenv(
            "BEDROCK_LLM_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0"
        )
        self.max_tokens = int(os.getenv("BEDROCK_MAX_TOKENS", "4096"))
        self.temperature = float(os.getenv("BEDROCK_TEMPERATURE", "0.7"))
        print(
            f"BedrockClient initialized (embedding={self.embedding_model_id}, "
            f"llm={self.llm_model_id})"
        )

    def get_embedding(self, text: str) -> List[float]:
        """Generate an embedding vector for the given text using Amazon Titan.

        Args:
            text: The text to embed.

        Returns:
            A list of floats representing the embedding vector.
        """
        try:
            body = json.dumps({"inputText": text})
            response = self.client.invoke_model(
                modelId=self.embedding_model_id,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
            result = json.loads(response["body"].read())
            embedding = result["embedding"]
            print(f"Generated embedding with {len(embedding)} dimensions")
            return embedding
        except Exception as e:
            print(f"Error generating embedding: {e}")
            raise

    def generate_answer(self, prompt: str) -> str:
        """Generate a text response using the Claude LLM model.

        Args:
            prompt: The prompt to send to the model.

        Returns:
            The generated text response.
        """
        try:
            body = json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                    "messages": [{"role": "user", "content": prompt}],
                }
            )
            response = self.client.invoke_model(
                modelId=self.llm_model_id,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
            result = json.loads(response["body"].read())
            answer = result["content"][0]["text"]
            print(f"Generated answer ({len(answer)} characters)")
            return answer
        except Exception as e:
            print(f"Error generating answer: {e}")
            raise
