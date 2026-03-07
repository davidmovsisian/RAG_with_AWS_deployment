"""
S3 client for downloading, reading, and moving documents in S3.
"""
import os
from typing import Optional
import boto3

class S3Client:
    def __init__(self):
        region = os.getenv("AWS_REGION", "us-east-1")
        self.client = boto3.client("s3", region_name=region)
        self.bucket_name = os.getenv("S3_BUCKET_NAME", "")
        print(f"S3Client initialized (bucket={self.bucket_name})")

    def upload_file(self, content: str, key: str):
            self.client.put_object(Bucket=self.bucket_name, Key=key, Body=content)
            print(f"Uploaded content -> s3://{self.bucket_name}/{key}")

    def read_file_content(self, key: str) -> Optional[str]:
        print(f"Reading S3 object: {key} from bucket: {self.bucket_name}")
        response = self.client.get_object(Bucket=self.bucket_name, Key=key)
        file_bytes = response["Body"].read()
        content = file_bytes.decode("utf-8")
        print(f"Read {len(content)} characters from s3://{self.bucket_name}/{key}")
        return content
