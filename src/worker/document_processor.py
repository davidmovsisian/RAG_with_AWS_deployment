"""
Document processor that orchestrates chunking, embedding, and indexing.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.utils.bedrock_client import BedrockClient
    from src.utils.chunking import TextChunker
    from src.utils.opensearch_client import OpenSearchClient


class DocumentProcessor:
    """Orchestrates chunking, embedding, and indexing of documents into OpenSearch."""

    def __init__(
        self,
        bedrock_client: "BedrockClient",
        opensearch_client: "OpenSearchClient",
        text_chunker: "TextChunker",
    ):
        """Initialize with utility clients.

        Args:
            bedrock_client: Client for generating embeddings via Amazon Bedrock.
            opensearch_client: Client for indexing documents into OpenSearch.
            text_chunker: Utility for splitting text into chunks.
        """
        self.bedrock_client = bedrock_client
        self.opensearch_client = opensearch_client
        self.text_chunker = text_chunker
        print("DocumentProcessor initialized")

    def process_document(self, content: str, filename: str) -> bool:
        """Chunk, embed, and index a document.

        Args:
            content: The raw text content of the document.
            filename: The original filename, stored as metadata.

        Returns:
            True if all chunks were successfully indexed, False otherwise.
        """
        try:
            print(f"Processing document: {filename}")
            chunks = self.text_chunker.chunk_text(content)
            if not chunks:
                print(f"No chunks produced for {filename}")
                return False

            total_chunks = len(chunks)
            print(f"Indexing {total_chunks} chunks for {filename}")

            for chunk_id, chunk in enumerate(chunks):
                embedding = self.bedrock_client.get_embedding(chunk)
                metadata = {
                    "filename": filename,
                    "chunk_id": chunk_id,
                    "total_chunks": total_chunks,
                }
                self.opensearch_client.index_document(chunk, embedding, metadata)
                print(f"Indexed chunk {chunk_id + 1}/{total_chunks} for {filename}")

            print(f"Successfully processed {filename} ({total_chunks} chunks)")
            return True
        except Exception as e:
            print(f"Error processing document {filename}: {e}")
            return False
