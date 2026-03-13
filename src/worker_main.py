import os
import signal
import boto3
from dotenv import load_dotenv
from utils.gemini_client import GeminiClient
from utils.opensearch_client import OpenSearchClient
from utils.s3_client import S3Client
from utils.chunking import TextChunker
from worker.document_processor import DocumentProcessor
from worker.sqs_worker import SQSWorker

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))


def main():
    print("Starting standalone SQS Worker...")

    # Initialize AWS clients
    region = os.getenv("AWS_REGION", "us-east-1")
    sqs_client = boto3.client("sqs", region_name=region)

    # Initialize service clients
    s3_client = S3Client()
    gemini_client = GeminiClient(pool_size=int(os.getenv("GEMINI_POOL_SIZE", "5")))
    opensearch_client = OpenSearchClient()
    text_chunker = TextChunker()

    # Ensure index exists before processing
    opensearch_client.create_index()

    # Initialize document processor
    document_processor = DocumentProcessor(
        gemini_client,
        opensearch_client,
        text_chunker
    )

    # Initialize SQS worker
    sqs_worker = SQSWorker(sqs_client, s3_client, document_processor)

    # Handle shutdown gracefully
    def shutdown_handler(signum, frame):
        print("Shutting down SQS Worker...")
        sqs_worker.stop()
        print("SQS Worker stopped")

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Start polling loop (blocking)
    sqs_worker.poll_and_process()


if __name__ == "__main__":
    main()
