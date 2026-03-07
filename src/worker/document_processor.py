from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils.gemini_client import GeminiClient
    from utils.chunking import TextChunker
    from utils.opensearch_client import OpenSearchClient

class DocumentProcessor:
    def __init__(
        self,
        gemini_client: "GeminiClient",
        opensearch_client: "OpenSearchClient",
        text_chunker: "TextChunker",
    ):
        self.gemini_client = gemini_client
        self.opensearch_client = opensearch_client
        self.text_chunker = text_chunker
        print("DocumentProcessor initialized")

    def process_document(self, content: str, filename: str) -> bool:
        print(f"Processing document: {filename}")
        chunks = self.text_chunker.chunk_text(content)
        if not chunks:
            print(f"No chunks produced for {filename}")
            return False

        total_chunks = len(chunks)
        print(f"Indexing {total_chunks} chunks for {filename}")

        for chunk_id, chunk in enumerate(chunks):
            embedding = self.gemini_client.get_embedding(chunk)
            metadata = {
                "filename": filename,
                "chunk_id": chunk_id,
                "total_chunks": total_chunks,
            }
            self.opensearch_client.index_document(chunk, embedding, metadata)
            print(f"Indexed chunk {chunk_id + 1}/{total_chunks} for {filename}")

        print(f"Successfully processed {filename} ({total_chunks} chunks)")
        return True
