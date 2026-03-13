import os
from typing import Optional
import boto3
from botocore.exceptions import ClientError
import time
from io import BytesIO
from pypdf import PdfReader

#use AWS Textractor to extract text from PDF files. 
class PDFExtractor:
    # Max file size limits
    MAX_SYNC_PAGES = 1  # Synchronous API supports only single-page documents
    MAX_ASYNC_PAGES = 3000  # Asynchronous API supports up to 3,000 pages
    MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB max file size
    
    def __init__(self):
        region = os.getenv("AWS_REGION", "us-east-1")
        self.textract_client = boto3.client("textract", region_name=region)
        self.s3_client = boto3.client("s3", region_name=region)
        self.bucket_name = os.getenv("S3_BUCKET_NAME", "")
        print(f"PDFExtractor initialized with AWS Textract (region={region})")
    
    def extract_text_from_pdf(self, pdf_bytes: bytes, s3_key: str = None) -> Optional[str]:
        file_size = len(pdf_bytes)
        
        print(f"[Textract] Processing {s3_key}")

        if file_size > self.MAX_FILE_SIZE:
            print(f"[Textract] Error: File too large ({file_size} bytes). Max is {self.MAX_FILE_SIZE} bytes.")
            return None
        
        num_pages = self._count_pdf_pages(pdf_bytes)
        if num_pages is None:
            print(f"[Textract] Error: Could not determine page count for {s3_key}")
            return None
        if num_pages > self.MAX_ASYNC_PAGES:
            print(f"[Textract] Error: Too many pages ({num_pages}). Max is {self.MAX_ASYNC_PAGES} pages.")
            return None
        print(f"[Textract] PDF has {num_pages} page(s)")

        if num_pages == self.MAX_SYNC_PAGES:
            return self._extract_sync(pdf_bytes, s3_key)
        else:
            if s3_key:
                return self._extract_async(s3_key)
            else:
                print(f"[Textract] File exceeds {num_pages} but no S3 key provided. Cannot use async API.")
                return None
    
    def _count_pdf_pages(self, pdf_bytes: bytes) -> Optional[int]:
        try:
            pdf_file = BytesIO(pdf_bytes)
            reader = PdfReader(pdf_file)
            num_pages = len(reader.pages)
            return num_pages
        except Exception as e:
            print(f"[Textract] Error counting pages: {e}")
            return None
        
    def _extract_sync(self, pdf_bytes: bytes, s3_key: str) -> Optional[str]:
        try:
            response = self.textract_client.detect_document_text(
                Document={'Bytes': pdf_bytes}
            )
            text = self._parse_textract_response(response)
            if text:
                return text
            else:
                print(f"[Textract] No text extracted from {s3_key}")
                return None
        except Exception as e:
            print(f"[Textract] Error on text extraction: {e}")
            return None
    
    def _extract_async(self, s3_key: str) -> Optional[str]:
        try:
            # Start asynchronous job
            response = self.textract_client.start_document_text_detection(
                DocumentLocation={
                    'S3Object': {
                        'Bucket': self.bucket_name,
                        'Name': s3_key
                    }
                }
            )
            
            job_id = response['JobId']
            print(f"[Textract] Started job {job_id} for {s3_key}")
            
            # Poll for completion
            max_wait_time = 300  # 5 minutes
            poll_interval = 5  # 5 seconds
            elapsed_time = 0
            
            while elapsed_time < max_wait_time:
                time.sleep(poll_interval)
                elapsed_time += poll_interval
                
                result = self.textract_client.get_document_text_detection(JobId=job_id)
                status = result['JobStatus']
                print(f"[Textract] Job {job_id} status: {status} ({elapsed_time}s elapsed)")
                if status == 'SUCCEEDED':
                    # Extract text from all pages
                    text = self._parse_textract_async_response(job_id)
                    if text:
                        return text
                    else:
                        print(f"[Textract] No text extracted from {s3_key}")
                        return None
                        
                elif status == 'FAILED':
                    print(f"[Textract] Job {job_id} failed")
                    return None
            
            print(f"[Textract] Job {job_id} timed out after {max_wait_time}s")
            return None
        except Exception as e:
            print(f"[Textract] Error on text extraction: {e}")
            return None
    
    def _parse_textract_response(self, response: dict) -> Optional[str]:
        text_parts = []
        
        for block in response.get('Blocks', []):
            if block['BlockType'] == 'LINE':
                text = block.get('Text', '').strip()
                if text:
                    text_parts.append(text)
        
        if not text_parts:
            return None
        
        # Join lines with newline
        return '\n'.join(text_parts)
    
    def _parse_textract_async_response(self, job_id: str) -> Optional[str]:
        text_parts = []
        next_token = None
        
        while True:
            if next_token:
                response = self.textract_client.get_document_text_detection(
                    JobId=job_id,
                    NextToken=next_token
                )
            else:
                response = self.textract_client.get_document_text_detection(JobId=job_id)
            
            # Extract text from this page of results
            for block in response.get('Blocks', []):
                if block['BlockType'] == 'LINE':
                    text = block.get('Text', '').strip()
                    if text:
                        text_parts.append(text)
            
            # Check if there are more results
            next_token = response.get('NextToken')
            if not next_token:
                break
        
        if not text_parts:
            return None
        
        return '\n'.join(text_parts)