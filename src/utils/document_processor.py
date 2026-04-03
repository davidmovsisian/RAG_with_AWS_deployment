from utils.chunking import TextChunker
from utils.opensearch_client import OpenSearchClient
from utils.bedrock_client import BedrockClient

class DocumentProcessor:
    def __init__(
        self,
        bedrock_client: "BedrockClient",
        opensearch_client: "OpenSearchClient",
        text_chunker: "TextChunker",
    ):
        self.bedrock_client = bedrock_client
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

    def remove_document(self, filename: str) -> bool:
        print(f"Processing removal of document: {filename}")
        results = self.opensearch_client.search_by_metadata(field="filename", value=filename)
        if not results:
            return False
        for result in results:
            doc_id = result["_id"]
            self.opensearch_client.delete_document(doc_id)
        return True