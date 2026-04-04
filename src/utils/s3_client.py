import os
from typing import Optional
import boto3
import logging

logger = logging.getLogger(__name__)

class S3Client:
    def __init__(self):
        logger.info("Initializing S3Client...")
        region = os.getenv("AWS_REGION", "us-east-1")
        self.client = boto3.client("s3", region_name=region)
        self.bucket_name = os.getenv("S3_BUCKET_NAME", "")
        self.bucket_prefix  = os.getenv("S3_BUCKET_PREFIX", None)

    def upload_file(self, file: str):
        try:
            key = f"{self.bucket_prefix}/{file.filename}" if self.bucket_prefix else file.filename
            logger.info(f"Uploading file to s3://{self.bucket_name}/{key}")
            file.seek(0)
            self.client.upload_fileobj(file, self.bucket_name, key)
        except Exception as e:
            logger.error(f"Error uploading file to S3: {e}")
            raise

    def delete_file(self, filename: str):
        try:
            key = f"{self.bucket_prefix}/{filename}" if self.bucket_prefix else filename
            logger.info(f"Deleting file s3://{self.bucket_name}/{key}")
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
        except Exception as e:
            logger.error(f"Error deleting file from S3: {e}")
            raise

    def read_file_content(self, key: str) -> Optional[str]:
        try:
            key = f"{self.bucket_prefix}/{key}" if self.bucket_prefix else key
            logger.info(f"Reading S3 object: {key} from bucket: {self.bucket_name}")
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            file_bytes = response["Body"].read()
            content = file_bytes.decode("utf-8")
            return content
        except Exception as e:
            logger.error(f"Error reading file from S3: {e}")
            return None     

    def read_file_bytes(self, key: str) -> Optional[bytes]:
        try:
            key = f"{self.bucket_prefix}/{key}" if self.bucket_prefix else key
            logger.info(f"Reading S3 object as bytes: {key}")
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            file_bytes = response["Body"].read()
            return file_bytes
        except Exception as e:
            logger.error(f"Error reading bytes from S3: {e}")
            return None
    
    def get_file_type(self, key: str) -> str:
        extension = os.path.splitext(key)[1].lower()
        if extension != '.pdf' and extension != '.txt':
            return 'unknown'
        else:
            return extension
            
    def list_files(self) -> list:
        logger.info(f"Listing files in bucket: {self.bucket_name} with prefix: {self.bucket_prefix}")
        try:
            paginator = self.client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=self.bucket_name, 
                Prefix=self.bucket_prefix if self.bucket_prefix else "")
            files = []
            for page in page_iterator:
                contents = page.get('Contents', [])
                for obj in contents:
                    files.append(obj['Key'])
            logger.info(f"Listed {len(files)} files")
            return files
        except Exception as e:
            logger.error(f"Error listing files in S3: {e}")
            return []