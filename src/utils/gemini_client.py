import os
from typing import List
from google import genai
from google.genai import types
from queue import Queue, Empty
import threading

class GeminiClient:
    def __init__(self, pool_size=5):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")

        self.embedding_model = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
        self.llm_model = os.getenv("GEMINI_LLM_MODEL", "gemini-2.5-flash")
        self.max_tokens = int(os.getenv("GEMINI_MAX_TOKENS", "4096"))
        self.temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))
        self.embedding_dimension = int(os.getenv("EMBEDDING_DIMENSION", "768"))

        self.client_pool = Queue(maxsize=pool_size)
        # Initialize pool with client instances
        for i in range(pool_size):
            client = genai.Client(api_key=self.api_key)
            self.client_pool.put(client)

        # self.client = genai.Client(api_key=_api_key)
        print(
            f"GeminiClient initialized (embedding={self.embedding_model}, "
            f"llm={self.llm_model})"
        )

    def _get_client(self) -> genai.Client:
        try:
            return self.client_pool.get(timeout=10)  # wait for a client to be available
        except Empty:
            raise Exception("No Gemini client available in pool")
    
    def _release_client(self, client):
        self.client_pool.put(client)

    def get_embedding(self, text: str) -> List[float]:
        client = self._get_client()
        try:
            result = client.models.embed_content(
                model=self.embedding_model,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=self.embedding_dimension)
            )
            if not result.embeddings:
                return []
            # OpenSearch knn_vector expects a flat list of numbers.
            return list(result.embeddings[0].values)
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return []
        finally:
            self._release_client(client)
    
    def generate_answer(self, context, question):
        client = self._get_client()
        try:
            prompt = f"""Use the following context to answer the question clearly.

        Context:
        {context}
        Question: {question}"""
            resp = client.models.generate_content(
                model=self.llm_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_budget=1)  # keep it fast/light
                )
            )
            return (resp.text or "").strip()
        except Exception as e:
            print(f"Error generating answer: {e}")
        finally:
            self._release_client(client)
    