import os
import signal
import boto3
from dotenv import load_dotenv
from utils.bedrock_client import BedrockClient
from utils.opensearch_client import OpenSearchClient
from utils.s3_client import S3Client
from utils.chunking import TextChunker
from utils.document_processor import DocumentProcessor
from worker.sqs_worker import SQSWorker

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))


def main():
    print("Starting SQS Worker...")

    region = os.getenv("AWS_REGION", "us-east-1")
    sqs_client = boto3.client("sqs", region_name=region)

    s3_client = S3Client()
    bedrock_client = BedrockClient()
    opensearch_client = OpenSearchClient()
    text_chunker = TextChunker()

    opensearch_client.create_index()

    document_processor = DocumentProcessor(
        bedrock_client,
        opensearch_client,
        text_chunker
    )

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