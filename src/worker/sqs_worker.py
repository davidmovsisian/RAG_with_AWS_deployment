import json
import os
import time
from typing import Optional
import boto3
import threading
from utils.s3_client import S3Client
from utils.textract_client import TextractClient
from utils.chunking import TextChunker
from utils.opensearch_client import OpenSearchClient
import logging

logger = logging.getLogger(__name__)

"""
# read message from SQS, retrieve the S3 key from the message, 
# Read the file from S3,
# Process the document,
# Delete the message from the queue 
"""
class SQSWorker:
    def __init__(self, 
                 sqs_client: boto3.client,
                 s3_client: "S3Client",
                 text_chunker: "TextChunker",
                 opensearch_client: "OpenSearchClient"):
        self.sqs_client = sqs_client
        self.s3_client = s3_client
        self.text_chunker = text_chunker
        self.opensearch_client = opensearch_client

        self.queue_url = os.getenv("SQS_QUEUE_URL", "")
        self.poll_interval = int(os.getenv("WORKER_POLL_INTERVAL", "5"))
        self.max_messages = int(os.getenv("WORKER_MAX_MESSAGES", "10"))
        self.visibility_timeout = int(os.getenv("WORKER_VISIBILITY_TIMEOUT", "300"))
        
        self.stop_event = threading.Event()
        
        logger.info(f"SQSWorker initialized (queue={self.queue_url})")

    def stop(self):
        self.stop_event.set()

    def poll_and_process(self):
        logger.info("Starting SQS worker polling loop...")
        while not self.stop_event.is_set():
            try:
                response = self.sqs_client.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=self.max_messages,
                    WaitTimeSeconds=20,
                    VisibilityTimeout=self.visibility_timeout,
                )
                messages = response.get("Messages", [])
                if not messages:
                    logger.info("No messages received, waiting...")
                    time.sleep(self.poll_interval)
                    continue

                logger.info(f"Received {len(messages)} message(s)")
                for message in messages:
                    self.process_message(message)
            except Exception as e:
                logger.error(f"Error during polling: {e}")
                time.sleep(self.poll_interval)

    def process_message(self, message: dict) -> None:
        logger.info(f"Processing message: {message.get('MessageId')}")
        receipt_handle = message["ReceiptHandle"]
        try:
            body = json.loads(message["Body"])
            s3_key, event_name = self._extract_s3_info(body)
            logger.info(f"Processing S3 object: {s3_key, event_name} from message")
            if event_name.startswith("ObjectCreated"):
                 self.proccees_document(s3_key)
            elif event_name.startswith("ObjectRemoved"):
                self.delete_document(s3_key)
            self._delete_message(receipt_handle)
        except Exception as e:
            logger.error(f"Error processing message (receipt_handle={receipt_handle}): {e}")

    def proccees_document(self, s3_key: str): 
        logger.info(f"Processing document {s3_key})")
        extension = self.s3_client.get_file_type(s3_key)
        content = None
        try:
            if extension == ".txt":
                content = self.s3_client.read_file_content(s3_key)            
            elif extension == ".pdf":
                pdf_bytes = self.s3_client.read_file_bytes(s3_key)
                textract_client = TextractClient()
                content = textract_client.extract_text_from_pdf(pdf_bytes, s3_key=s3_key)
            else:
                logger.warning(f"Unsupported file type: {extension} for {s3_key}")
                return
            # Process the document content 
            filename = os.path.basename(s3_key)
            self.process_content(content, filename)
        except Exception as e:
            logger.error(f"Error reading or extracting content for {s3_key}: {e}")
            raise

    def process_content(self, content: str, filename: str):
        logger.info(f"Processing document content: {filename}")
        try:
            chunks = self.text_chunker.chunk_text(content)
            if not chunks:
                logger.warning(f"No chunks produced for {filename}")
                return
            self.opensearch_client.index_document(chunks, filename)    
        except Exception as e:
            logger.error(f"Error processing content for {filename}: {e}")
            raise

    def delete_document(self, s3_key: str):
        logger.info(f"Deleting document {s3_key}")
        try:
            filename = os.path.basename(s3_key)
            self.opensearch_client.delete_document(filename)
            logger.info(f"Successfully deleted document {filename} from OpenSearch")
        except Exception as e:
            logger.error(f"Error deleting document for {s3_key}: {e}")
            raise

    def _extract_s3_info(self, event: dict) -> Optional[str]:
        logger.info(f"Extracting S3 info from event: {event}")
        try:
            records = event.get("Records")
            if records:
                event_name = records[0].get("eventName", "")
                key = records[0]["s3"]["object"]["key"]
                return [key, event_name]
            return [event.get("s3_key"), event.get("event_name")]
        except Exception as e:
            logger.error(f"Error extracting S3 info from event: {e}")
            return [None, None]

    def _delete_message(self, receipt_handle: str):
        logger.info("Deleting message from queue")
        try:
            self.sqs_client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle,
            )
        except Exception as e:
            logger.error(f"Error deleting message from queue: {e}")
