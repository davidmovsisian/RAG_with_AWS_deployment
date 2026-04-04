# from utils.chunking import TextChunker
# from utils.opensearch_client import OpenSearchClient
# from utils.bedrock_client import BedrockClient
# from opensearchpy.helpers import bulk

# class DocumentProcessor:
#     def __init__(
#         self,
#         bedrock_client: "BedrockClient",
#         opensearch_client: "OpenSearchClient",
#         text_chunker: "TextChunker",
#     ):
#         self.bedrock_client = bedrock_client
#         self.opensearch_client = opensearch_client
#         self.text_chunker = text_chunker
#         print("DocumentProcessor initialized")

#     def process_document(self, content: str, filename: str) -> bool:
#         print(f"Processing document: {filename}")
#         chunks = self.text_chunker.chunk_text(content)
#         if not chunks:
#             print(f"No chunks produced for {filename}")
#             return False

#         total_chunks = len(chunks)
#         print(f"Indexing {total_chunks} chunks for {filename}")

#         for chunk_id, chunk in enumerate(chunks):
#             embedding = self.bedrock_client.get_embedding(chunk)
#             metadata = {
#                 "filename": filename,
#                 "chunk_id": chunk_id,
#                 "total_chunks": total_chunks,
#             }
#             self.opensearch_client.index_document(chunk, embedding, metadata)
#             print(f"Indexed chunk {chunk_id + 1}/{total_chunks} for {filename}")

#         print(f"Successfully processed {filename} ({total_chunks} chunks)")
#         return True

#     def remove_document(self, filename: str) -> bool:
#         print(f"Processing removal of document: {filename}")
#         index_name = self.opensearch_client.index_name
#         client = self.opensearch_client.client

#         try:
#             query = {
#                 "query": {
#                     "term": { "metadata.filename": filename }
#                 },
#                 "_source": False  # We only need the IDs, not the content
#             }
            
#             search_response = client.search(index=index_name, body=query)
#             hits = search_response.get("hits", {}).get("hits", [])
            
#             if not hits:
#                 print(f"No documents found for {filename}")
#                 return False

#             # 2. Prepare bulk delete actions
#             actions = [
#                 {
#                     "_op_type": "delete",
#                     "_index": index_name,
#                     "_id": hit["_id"]
#                 }
#                 for hit in hits
#             ]

#             # 3. Execute bulk deletion
#             success_count, errors = bulk(client, actions)
            
#             if errors:
#                 print(f"Errors occurred during deletion: {errors}")
            
            
#             print(f"Successfully deleted {success_count} chunks for {filename}")
#             return success_count > 0

#         except Exception as e:
#             print(f"Failed to remove document {filename}: {e}")
#             return False
    
#     # def remove_document(self, filename: str) -> bool:
#     #     print(f"Processing removal of document: {filename}")
#     #     try:
#     #         results = self.opensearch_client.search_by_metadata(field="filename", value=filename)
#     #         if not results:
#     #             print(f"No indexed segments found for {filename}")
#     #             return False

#     #         deleted = 0
#     #         for result in results:
#     #             doc_id = result.get("_id")
#     #             if not doc_id:
#     #                 continue
#     #             if self.opensearch_client.delete_document(doc_id):
#     #                 deleted += 1

#     #         print(f"Fallback deletion removed {deleted}/{len(results)} segments for {filename}")
#     #         return deleted > 0
#     #     except Exception as e:
#     #         print(f"Error during fallback deletion: {type(e).__name__}: {e}")
#     #         return False
        
    