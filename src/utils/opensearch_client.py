import os
import time
from typing import Any, Dict, List
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

class OpenSearchClient:
    def __init__(self):
        endpoint = os.getenv("OPENSEARCH_ENDPOINT", "")
        self.index_name = os.getenv("OPENSEARCH_INDEX_NAME", "rag-documents")
        # Parse host and port from endpoint
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
        print("OpenSearchClient initialized with AWS IAM auth")

    def _knn_mapping_exists(self) -> bool:
        """Check if the index has a proper knn_vector mapping for 'embedding'."""
        try:
            mapping = self.client.indices.get_mapping(index=self.index_name)
            props = mapping[self.index_name]["mappings"].get("properties", {})
            return props.get("embedding", {}).get("type") == "knn_vector"
        except Exception:
            return False

    def create_index(self) -> bool:
        """Create a KNN-enabled index with HNSW algorithm."""
        dimension = int(os.getenv("EMBEDDING_DIMENSION", "1536"))
        try:
            if self.client.indices.exists(index=self.index_name):
                if self._knn_mapping_exists():
                    print(f"Index '{self.index_name}' already exists with correct mapping")
                    return True
                print(f"Index '{self.index_name}' exists but has wrong mapping — recreating")
                self.client.indices.delete(index=self.index_name)
                print(f"Deleted index '{self.index_name}'")

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
            print(f"Index '{self.index_name}' created successfully")
            return True
        except Exception as e:
            print(f"Error creating index: {e}")
            return False

    def index_document(self, content: str, embedding: List[float], metadata: Dict[str, Any]) -> str:
        """Index a document chunk with its embedding vector and metadata dict with filename, chunk_id, total_chunks."""
        document = {
            "content": content,
            "embedding": embedding,
            "metadata": metadata,
        }
        response = self.client.index(index=self.index_name, body=document)
        doc_id = response["_id"]
        print(f"Indexed document with id={doc_id}")
        return doc_id


    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """Perform KNN vector similarity search."""
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
            print(f"Search returned {len(results)} results")
            return results
        except Exception as e:
            print(f"Error performing search: {e}")
            raise

    def search_by_metadata(self, field: str, value: str, size: int = 100) -> List[Dict[str, Any]]:
        """Search documents by metadata field (e.g., filename)."""
        try:
            query = {
                "size": size,
                "query": {
                    "match": {
                        f"metadata.{field}": value
                    }
                }
            }
            response = self.client.search(index=self.index_name, body=query)
            results = []
            for hit in response["hits"]["hits"]:
                results.append({
                    "_id": hit["_id"],
                    "score": hit["_score"],
                    "content": hit["_source"].get("content", ""),
                    "metadata": hit["_source"].get("metadata", {}),
                })
            print(f"Found {len(results)} documents matching {field}={value}")
            return results
        except Exception as e:
            print(f"Error searching by metadata: {e}")
            return []
    
    def check_document_indexed(self, filename: str, retries: int = 10, delay: float = 3.0) -> bool:
        """Check if a document is indexed, retrying to account for OpenSearch propagation delay."""
        for attempt in range(1, retries + 1):
            try:
                results = self.search_by_metadata(field="filename", value=filename, size=1)
                if results:
                    return True
            except Exception as e:
                print(f"Error checking document status: {e}")
            print(f"Document '{filename}' not yet visible, retrying ({attempt}/{retries})...")
            time.sleep(delay)
        return False
        
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document by ID from the index."""
        try:
            self.client.delete(index=self.index_name, id=doc_id)
            for attempt in range(1, 6):
                try:
                    self.client.get(index=self.index_name, id=doc_id)
                    print(f"Document {doc_id} still exists after deletion attempt {attempt}")
                    time.sleep(5)
                except Exception:
                    print(f"Confirmed deletion of document with id={doc_id}")
                    return True
                time.sleep(5)
            print(f"Failed to delete document with id={doc_id}")
            return False
        except Exception as e:
            print(f"Error deleting document {doc_id}: {e}")
            return False
