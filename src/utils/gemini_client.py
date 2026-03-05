import os
from typing import List
from google import genai
from google.genai import types
import numpy as np

class GeminiClient:
    def __init__(self):
        _api_key = os.environ.get("GEMINI_API_KEY")
        if not _api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")

        self.embedding_model = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
        self.llm_model = os.getenv("GEMINI_LLM_MODEL", "gemini-2.5-flash")
        self.max_tokens = int(os.getenv("GEMINI_MAX_TOKENS", "4096"))
        self.temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))

        self.client = genai.Client(api_key=_api_key)
        print(
            f"GeminiClient initialized (embedding={self.embedding_model}, "
            f"llm={self.llm_model})"
        )

    def get_embedding(self, text: str) -> List[float]:
        try:
            result = self.client.models.embed_content(
                model=self.embedding_model,
                contents=text,
                config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
            )
            return np.array([e.values for e in result.embeddings], dtype="float32")
        except Exception as e:
            print(f"Error generating embedding: {e}")
            raise
    
    def generate_answer(self, context, question):
        prompt = f"""Use the following context to answer the question clearly.

    Context:
    {context}
    Question: {question}"""
        resp = self.client.models.generate_content(
            model=self.llm_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=1)  # keep it fast/light
            )
        )
        return (resp.text or "").strip()
    