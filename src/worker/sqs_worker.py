"""
SQS worker that polls for document upload messages and processes them.
"""

import json
import os
import time
from typing import TYPE_CHECKING, Optional

import boto3

if TYPE_CHECKING:
    from utils.s3_client import S3Client
    from worker.document_processor import DocumentProcessor


class SQSWorker:
    """Polls an SQS queue for S3 upload events and processes documents."""

    def __init__(
        self,
        sqs_client: boto3.client,
        s3_client: "S3Client",
        document_processor: "DocumentProcessor",
    ):
        """Initialize the worker with AWS clients and configuration from environment.

        Args:
            sqs_client: A boto3 SQS client.
            s3_client: S3Client instance for reading and moving files.
            document_processor: DocumentProcessor instance for processing documents.
        """
        self.sqs_client = sqs_client
        self.s3_client = s3_client
        self.document_processor = document_processor

        self.queue_url = os.getenv("SQS_QUEUE_URL", "")
        self.poll_interval = int(os.getenv("WORKER_POLL_INTERVAL", "5"))
        self.max_messages = int(os.getenv("WORKER_MAX_MESSAGES", "10"))
        self.visibility_timeout = int(os.getenv("WORKER_VISIBILITY_TIMEOUT", "300"))

        print(
            f"SQSWorker initialized (queue={self.queue_url}, "
            f"poll_interval={self.poll_interval}s, max_messages={self.max_messages})"
        )

    def poll_and_process(self) -> None:
        """Poll the SQS queue in a loop and process incoming document messages.

        Runs indefinitely until interrupted with KeyboardInterrupt.
        """
        print("Starting SQS worker polling loop...")
        try:
            while True:
                try:
                    response = self.sqs_client.receive_message(
                        QueueUrl=self.queue_url,
                        MaxNumberOfMessages=self.max_messages,
                        WaitTimeSeconds=20,
                        VisibilityTimeout=self.visibility_timeout,
                    )
                    messages = response.get("Messages", [])
                    if not messages:
                        print("No messages received, waiting...")
                        time.sleep(self.poll_interval)
                        continue

                    print(f"Received {len(messages)} message(s)")
                    for message in messages:
                        self._process_message(message)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f"Error during polling: {e}")
                    time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            print("Worker stopped by user (KeyboardInterrupt)")

    def _process_message(self, message: dict) -> None:
        """Process a single SQS message.

        Parses the message body, reads the document from S3, processes it,
        moves the file to processed/ or failed/, then deletes the message.

        Args:
            message: The SQS message dict containing Body and ReceiptHandle.
        """
        receipt_handle = message["ReceiptHandle"]
        try:
            body = json.loads(message["Body"])
            s3_key = self._extract_s3_key(body)
            if not s3_key:
                print(f"Could not extract S3 key from message: {body}")
                self._delete_message(receipt_handle)
                return

            print(f"Processing S3 object: {s3_key}")
            content = self.s3_client.read_file_content(s3_key)
            if content is None:
                print(f"Failed to read content for {s3_key}, moving to failed/")
                self.s3_client.move_to_failed(s3_key)
                self._delete_message(receipt_handle)
                return

            filename = os.path.basename(s3_key)
            success = self.document_processor.process_document(content, filename)
            if success:
                print(f"Document processed successfully, moving {s3_key} to processed/")
                self.s3_client.move_to_processed(s3_key)
            else:
                print(f"Document processing failed, moving {s3_key} to failed/")
                self.s3_client.move_to_failed(s3_key)

            self._delete_message(receipt_handle)
        except Exception as e:
            print(f"Unhandled error processing message (receipt_handle={receipt_handle}): {e}")

    def _extract_s3_key(self, event: dict) -> Optional[str]:
        """Extract the S3 object key from an S3 event notification or custom format.

        Supports:
        - Standard S3 event notification: ``Records[0].s3.object.key``
        - Custom test format: top-level ``s3_key`` field

        Args:
            event: The parsed message body dict.

        Returns:
            The S3 object key string, or None if it cannot be extracted.
        """
        try:
            records = event.get("Records")
            if records:
                return records[0]["s3"]["object"]["key"]
            return event.get("s3_key") or None
        except (KeyError, IndexError, TypeError) as e:
            print(f"Error extracting S3 key: {e}")
            return None

    def _delete_message(self, receipt_handle: str) -> None:
        """Delete a message from the SQS queue.

        Args:
            receipt_handle: The receipt handle of the message to delete.
        """
        try:
            self.sqs_client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle,
            )
            print("Message deleted from queue")
        except Exception as e:
            print(f"Error deleting message: {e}")
