import os
from datetime import datetime
from typing import Any, Dict, List

from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth


class OpenSearchClient:
    def __init__(self):
        endpoint = os.getenv("OPENSEARCH_ENDPOINT", "")
        self.index_name = os.getenv("OPENSEARCH_INDEX_NAME", "rag-documents")
        username = os.getenv("OPENSEARCH_USERNAME")
        password = os.getenv("OPENSEARCH_PASSWORD")

        # Parse host and port from endpoint
        host = endpoint.replace("https://", "").replace("http://", "")
        use_ssl = endpoint.startswith("https://")

        if username and password:
            # Basic auth (standalone OpenSearch)
            self.client = OpenSearch(
                hosts=[{"host": host, "port": 443 if use_ssl else 9200}],
                http_auth=(username, password),
                use_ssl=use_ssl,
                verify_certs=use_ssl,
                connection_class=RequestsHttpConnection,
            )
            print("OpenSearchClient initialized with basic auth")
        else:
            # AWS IAM auth
            import boto3

            region = os.getenv("AWS_REGION", "us-east-1")
            credentials = boto3.Session().get_credentials()
            aws_auth = AWS4Auth(
                credentials.access_key,
                credentials.secret_key,
                region,
                "es",
                session_token=credentials.token,
            )
            self.client = OpenSearch(
                hosts=[{"host": host, "port": 443}],
                http_auth=aws_auth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
            )
            print("OpenSearchClient initialized with AWS IAM auth")

    def create_index(self, dimension: int = 768) -> bool:
        """Create a KNN-enabled index with HNSW algorithm."""
        try:
            if self.client.indices.exists(index=self.index_name):
                print(f"Index '{self.index_name}' already exists")
                return True

            index_body = {
                "settings": {"index": {"knn": True, "knn.algo_param.ef_search": 512}},
                "mappings": {
                    "properties": {
                        "content": {"type": "text"},
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": dimension,
                            "method": {
                                "name": "hnsw",
                                "space_type": "l2",
                                "engine": "nmslib",
                                "parameters": {"ef_construction": 512, "m": 16},
                            },
                        },
                        "metadata": {
                            "properties": {
                                "filename": {"type": "keyword"},
                                "chunk_id": {"type": "integer"},
                                "total_chunks": {"type": "integer"},
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
