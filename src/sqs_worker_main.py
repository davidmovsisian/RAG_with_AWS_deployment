import os
import signal
import boto3
from dotenv import load_dotenv
# from utils.bedrock_client import BedrockClient
from utils.opensearch_client import OpenSearchClient
from utils.s3_client import S3Client
from utils.chunking import TextChunker
from worker.sqs_worker import SQSWorker
import logging

logger = logging.getLogger(__name__)
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))


def configure_logging() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )


def main():
    configure_logging()
    logger.info("Starting SQS Worker...")

    region = os.getenv("AWS_REGION", "us-east-1")
    sqs_client = boto3.client("sqs", region_name=region)

    s3_client = S3Client()
    # bedrock_client = BedrockClient()
    opensearch_client = OpenSearchClient()
    text_chunker = TextChunker()

    opensearch_client.create_index()
    sqs_worker = SQSWorker(sqs_client, s3_client, text_chunker, opensearch_client)

    # Handle shutdown gracefully
    def shutdown_handler(signum, frame):
        logger.info("Shutting down SQS Worker...")
        sqs_worker.stop()
        logger.info("SQS Worker stopped")

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Start polling loop
    sqs_worker.poll_and_process()


if __name__ == "__main__":
    main()