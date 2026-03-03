"""
Entry point for the SQS worker process.

Run with:
    python src/worker/run_worker.py
"""

import os
import sys

# Add project root to Python path so src.* imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv()

import boto3

from src.utils.gemini_client import GeminiClient
from src.utils.chunking import TextChunker
from src.utils.opensearch_client import OpenSearchClient
from src.utils.s3_client import S3Client
from src.worker.document_processor import DocumentProcessor
from src.worker.sqs_worker import SQSWorker


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
