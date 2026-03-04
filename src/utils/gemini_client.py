"""
Gemini client for interacting with Google Gemini API for embeddings and LLM.
"""

import os
from typing import List

import google.generativeai as genai

class GeminiClient:
    """Client for Google Gemini API (embeddings and text generation)."""

    def __init__(self):
        """Initialize Gemini client with API key from environment."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")

        genai.configure(api_key=api_key)

        self.embedding_model = os.getenv("GEMINI_EMBEDDING_MODEL", "models/embedding-001")
        self.llm_model = os.getenv("GEMINI_LLM_MODEL", "gemini-1.5-flash")
        self.max_tokens = int(os.getenv("GEMINI_MAX_TOKENS", "4096"))
        self.temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))

        print(
            f"GeminiClient initialized (embedding={self.embedding_model}, "
            f"llm={self.llm_model})"
        )

    def get_embedding(self, text: str) -> List[float]:
        """Generate an embedding vector using Gemini embedding model."""
        try:
            result = genai.embed_content(
                model=self.embedding_model,
                content=text,
                task_type="retrieval_document",
            )
            embedding = result["embedding"]
            print(f"Generated embedding with {len(embedding)} dimensions")
            return embedding
        except Exception as e:
            print(f"Error generating embedding: {e}")
            raise

    def generate_answer(self, prompt: str) -> str:
        """Generate a text response using Gemini LLM."""
        try:
            model = genai.GenerativeModel(
                model_name=self.llm_model,
                generation_config={
                    "temperature": self.temperature,
                    "max_output_tokens": self.max_tokens,
                },
            )
            response = model.generate_content(prompt)
            answer = response.text
            print(f"Generated answer ({len(answer)} characters)")
            return answer
        except Exception as e:
            print(f"Error generating answer: {e}")
            raise
