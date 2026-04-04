import os
import time
from typing import Any, Dict, List
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
from opensearchpy.helpers import bulk
from utils.bedrock_client import BedrockClient
import logging

logger = logging.getLogger(__name__)

class OpenSearchClient:
    def __init__(self, 
                 bedrock_client: "BedrockClient"):
        self.bedrock_client = bedrock_client
        endpoint = os.getenv("OPENSEARCH_ENDPOINT", "")
        self.index_name = os.getenv("OPENSEARCH_INDEX_NAME", "rag-documents")
        host = endpoint.replace("https://", "").replace("http://", "").split(':')[0]
        region = os.getenv("AWS_REGION", "us-east-1")
        service = "aoss"  # "aoss" for OpenSearch Serverless, "es" for managed domains
        credentials = boto3.Session().get_credentials()
        aws_auth = AWSV4SignerAuth(credentials, region, service)
        self.client = OpenSearch(
            hosts=[{"host": host, "port": 443}],
            http_auth=aws_auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=60,
            max_retries=3,
            retry_on_timeout=True,
        )
        logger.info("OpenSearchClient initialized")

    def _knn_mapping_exists(self) -> bool:
        """Check if the index has a proper knn_vector mapping for 'embedding'."""
        try:
            mapping = self.client.indices.get_mapping(index=self.index_name)
            props = mapping[self.index_name]["mappings"].get("properties", {})
            return props.get("embedding", {}).get("type") == "knn_vector"
        except Exception:
            return False

    def create_index(self):
        """Create a KNN-enabled index with HNSW algorithm."""
        logger.info(f"Creating OpenSearch index: {self.index_name}")
        dimension = int(os.getenv("EMBEDDING_DIMENSION", "1536"))
        try:
            if self.client.indices.exists(index=self.index_name):
                if self._knn_mapping_exists():
                    logger.info(f"Index '{self.index_name}' already exists with correct mapping")
                    return True
                logger.info(f"Index '{self.index_name}' exists but has wrong mapping — recreating")
                self.client.indices.delete(index=self.index_name)
            index_body = {
                "settings": {
                    "index": {"knn": True}
                },
                "mappings": {
                    "properties": {
                        "content": {"type": "text"},
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": dimension,
                            "method": {
                                "name": "hnsw",
                                "space_type": "l2",
                                "engine": "faiss",
                                "parameters": {"ef_construction": 512, "m": 16},
                            },
                        },
                        "metadata": {
                            "properties": {
                                "filename": {"type": "keyword"},
                                "chunk_id": {"type": "integer"},
                                "total_chunks": {"type": "integer"}
                            }
                        },
                    }
                },
            }
            self.client.indices.create(index=self.index_name, body=index_body)
        except Exception as e:
            logger.error(f"Error creating index: {e}")
            raise

    # bulk indexing the cnunks
    def index_document(self, chunks:list, filename: str):
        logger.info(f"Indexing document '{filename}' with {len(chunks)} chunks")
        actions = []
        total_chunks = len(chunks)

        try:
            for chunk_id, chunk in enumerate(chunks):
                embedding = self.bedrock_client.get_embedding(chunk)
                action = {
                    "_op_type": "index",  # or "create" if you want it to fail if ID exists
                    "_index": self.index_name,
                    "_source": {
                        "content": chunk,
                        "embedding": embedding,
                        "metadata": {
                            "filename": filename,
                            "chunk_id": chunk_id,
                            "total_chunks": total_chunks,
                        }
                    }
                }
                actions.append(action)
            success_count, errors = bulk(self.opensearch_client.client, actions, refresh=True)
            if errors:
                logger.error(f"Errors occurred during bulk index: {errors}")
                raise Exception(f"Errors occurred during bulk index: {errors}")
            logger.info(f"Successfully indexed {success_count}/{total_chunks} chunks for {filename}")
        except Exception as e:  
            logger.error(f"Error preparing bulk index actions: {e}")
            raise

    # def index_document(self, content: str, embedding: List[float], metadata: Dict[str, Any]) -> str:
    #     """Index a document chunk with its embedding vector and metadata dict with filename, chunk_id, total_chunks."""
    #     logger.info(f"Indexing document with metadata: {metadata}")
    #     try:
    #         document = {
    #             "content": content,
    #             "embedding": embedding,
    #             "metadata": metadata,
    #         }
    #         response = self.client.index(index=self.index_name, body=document)
    #         doc_id = response["_id"]
    #         logger.info(f"Indexed document with id={doc_id}")
    #         return doc_id
    #     except Exception as e:
    #         logger.error(f"Error indexing document: {e}")
    #         raise

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """Perform KNN vector similarity search."""
        logger.info(f"Performing search with top_k={top_k}")
        try:
            query = {
                "size": top_k,
                "query": {
                    "knn": {
                        "embedding": {"vector": query_embedding, "k": top_k}
                    }
                },
            }
            response = self.client.search(index=self.index_name, body=query)
            results = []
            for hit in response["hits"]["hits"]:
                results.append(
                    {
                        "id": hit["_id"],
                        "score": hit["_score"],
                        "content": hit["_source"].get("content", ""),
                        "metadata": hit["_source"].get("metadata", {}),
                    }
                )
            logger.info(f"Search returned {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"Error performing search: {e}")
            raise

    def check_document_indexed(self, filename: str, retries: int = 10, delay: float = 3.0) -> bool:
        """Check if a document is indexed, retrying to account for OpenSearch propagation delay."""
        logger.info(f"Checking if document '{filename}' is indexed in OpenSearch")
        query = {
                "query": {
                    "term": {
                        "metadata.filename": filename
                    }
                }
            }
        for attempt in range(1, retries + 1):
            try:
                response = self.client.search(index=self.index_name, body=query)
                hits = response.get("hits", {}).get("hits", [])
                if hits:
                    print(f"Document '{filename}' is indexed and visible in OpenSearch")
                    return True
            except Exception as e:
                logger.error(f"Error checking document status: {e}")
            logger.info(f"Document '{filename}' not yet visible, retrying ({attempt}/{retries})...")
            time.sleep(delay)
        return False
    
    def delete_document(self, filename: str) -> bool:
        """Delete all documents with the given filename from the index."""
        logger.info(f"Processing removal of document: {filename}")
        try:
            query = {
                "query": {
                    "term": { "metadata.filename": filename }
                },
                "_source": False  # We only need the IDs, not the content
            }
            
            search_response = self.client.search(index=self.index_name, body=query)
            hits = search_response.get("hits", {}).get("hits", [])
            
            if not hits:
                logger.info(f"No documents found for {filename}")
                return False

            # Prepare bulk delete actions
            actions = [
                {
                    "_op_type": "delete",
                    "_index": self.index_name,
                    "_id": hit["_id"]
                }
                for hit in hits
            ]

            # Execute bulk deletion
            success_count, errors = bulk(self.client, actions)  
            if errors:
                logger.error(f"Errors occurred during deletion: {errors}")

            while self.check_document_indexed(filename):
                logger.info(f"Waiting for document '{filename}' to be removed from OpenSearch...")
            
            logger.info(f"Successfully deleted {success_count} chunks for {filename}")
            return success_count > 0

        except Exception as e:
            logger.error(f"Error deleting document '{filename}': {e}")
            return False