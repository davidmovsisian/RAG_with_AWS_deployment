import json
import os
import time
from typing import Optional
import boto3
import threading
from utils.s3_client import S3Client
from worker.document_processor import DocumentProcessor
from utils.pdf_extractor import PDFExtractor

"""
# read message from SQS, retrieve the S3 key from the message, 
# Read the file from S3,
# Process the document with DocumentProcessor,
# Delete the message from the queue 
"""
class SQSWorker:
    def __init__(self, 
                 sqs_client: boto3.client,
                 s3_client: "S3Client",
                 document_processor: "DocumentProcessor"):
        self.sqs_client = sqs_client
        self.s3_client = s3_client
        self.document_processor = document_processor

        self.queue_url = os.getenv("SQS_QUEUE_URL", "")
        self.poll_interval = int(os.getenv("WORKER_POLL_INTERVAL", "5"))
        self.max_messages = int(os.getenv("WORKER_MAX_MESSAGES", "10"))
        self.visibility_timeout = int(os.getenv("WORKER_VISIBILITY_TIMEOUT", "300"))
        
        self.stop_event = threading.Event()
        
        print(
            f"SQSWorker initialized (queue={self.queue_url}, "
            f"poll_interval={self.poll_interval}s, max_messages={self.max_messages})"
        )

    def stop(self):
        self.stop_event.set()

    def poll_and_process(self) -> None:
        print("Starting SQS worker polling loop...")
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
                    print("No messages received, waiting...")
                    time.sleep(self.poll_interval)
                    continue

                print(f"Received {len(messages)} message(s)")
                for message in messages:
                    self.process_message(message)
            except Exception as e:
                print(f"Error during polling: {e}")
                time.sleep(self.poll_interval)

    def process_message(self, message: dict) -> None:
        receipt_handle = message["ReceiptHandle"]
        try:
            body = json.loads(message["Body"])
            s3_key, event_name = self._extract_s3_info(body)
            print(f"Processing S3 object: {s3_key, event_name} from message")
            if not s3_key or not event_name:
                print(f"Could not extract S3 key or event name from message: {body}")
                self._delete_message(receipt_handle)
                return
            if event_name.startswith("ObjectCreated"):
                 self.proccees_document(receipt_handle, s3_key)
            elif event_name.startswith("ObjectRemoved"):
                self.remove_document(receipt_handle, s3_key)
        except Exception as e:
            print(f"error processing message (receipt_handle={receipt_handle}): {e}")

    def proccees_document(self, receipt_handle, s3_key: str):
        # Determine file, txt or pdf
        extension = self.s3_client.get_file_type(s3_key)
        
        print(f"Processing document {s3_key} of type {extension})")
        content = None

        if extension == ".txt":
            content = self.s3_client.read_file_content(s3_key)
            if content is None:
                print(f"Failed to read content for {s3_key}")
                self._delete_message(receipt_handle)
                return
        elif extension == ".pdf":
            pdf_bytes = self.s3_client.read_file_bytes(s3_key)
            if pdf_bytes is None:
                print(f"Failed to read content for {s3_key}")
                self._delete_message(receipt_handle)
                return
            pdf_extractor = PDFExtractor()
            content = pdf_extractor.extract_text_from_pdf(pdf_bytes, s3_key=s3_key)
            if content is None:
                print(f"Failed to extract text from PDF: {s3_key}")
                self._delete_message(receipt_handle)
                return
        else:
            print(f"Unsupported file type: {extension} for {s3_key}")
            self._delete_message(receipt_handle)
            return
        
        # Process the document content 
        filename = os.path.basename(s3_key)
        success = self.document_processor.process_document(content, filename)
        if success:
            print(f"{s3_key} processed successfully.")
        else:
            print(f"{s3_key} processing failed")
        self._delete_message(receipt_handle)
    
    def remove_document(self, receipt_handle, s3_key: str):
        filename = os.path.basename(s3_key)
        success = self.document_processor.remove_document(filename)
        if success:
            print(f"{s3_key} removed successfully.")
        else:
            print(f"{s3_key} removal failed")
        self._delete_message(receipt_handle)

    def _extract_s3_info(self, event: dict) -> Optional[str]:
        records = event.get("Records")
        if records:
            event_name = records[0].get("eventName", "")
            key = records[0]["s3"]["object"]["key"]
            return [key, event_name]
        return [event.get("s3_key"), event.get("event_name")]

    def _delete_message(self, receipt_handle: str):
        self.sqs_client.delete_message(
            QueueUrl=self.queue_url,
            ReceiptHandle=receipt_handle,
        )
        print("Message deleted from queue")