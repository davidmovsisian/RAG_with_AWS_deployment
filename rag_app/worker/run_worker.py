"""
Entry point for the SQS worker process.

Run with:
    python -m rag_app.worker.run_worker
"""

import os

from dotenv import load_dotenv

load_dotenv()

import boto3

from rag_app.utils.gemini_client import GeminiClient
from rag_app.utils.chunking import TextChunker
from rag_app.utils.opensearch_client import OpenSearchClient
from rag_app.utils.s3_client import S3Client
from rag_app.worker.document_processor import DocumentProcessor
from rag_app.worker.sqs_worker import SQSWorker


def main() -> None:
    """Create and start the SQS worker."""
    print("Initializing SQS worker...")

    region = os.getenv("AWS_REGION", "us-east-1")
    sqs_client = boto3.client("sqs", region_name=region)

    s3_client = S3Client()
    gemini_client = GeminiClient()
    opensearch_client = OpenSearchClient()
    text_chunker = TextChunker()

    document_processor = DocumentProcessor(gemini_client, opensearch_client, text_chunker)
    worker = SQSWorker(sqs_client, s3_client, document_processor)

    worker.poll_and_process()


if __name__ == "__main__":
    main()
