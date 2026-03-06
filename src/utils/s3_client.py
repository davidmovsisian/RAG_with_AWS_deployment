"""
S3 client for downloading, reading, and moving documents in S3.
"""
import os
from typing import Optional
import boto3

class S3Client:
    """Client for Amazon S3 file operations."""

    def __init__(self):
        region = os.getenv("AWS_REGION", "us-east-1")
        self.client = boto3.client("s3", region_name=region)
        self.bucket_name = os.getenv("S3_BUCKET_NAME", "")
        print(f"S3Client initialized (bucket={self.bucket_name})")

    def upload_file(self, content: str, key: str) -> bool:
        try:
            self.client.put_object(Bucket=self.bucket_name, Key=key, Body=content)
            print(f"Uploaded content -> s3://{self.bucket_name}/{key}")
            return True
        except Exception as e:
            raise

    def read_file_content(self, key: str) -> Optional[str]:
        """Read the content of an S3 file and extract text."""
        try:
            print(f"Reading S3 object: {key} from bucket: {self.bucket_name}")
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            file_bytes = response["Body"].read()
            try:
                content = file_bytes.decode("utf-8")
                print(
                    f"Read {len(content)} characters from "
                    f"s3://{self.bucket_name}/{key}"
                )
            except UnicodeDecodeError:
                print(f"Warning: File {key} is not UTF-8 text")
                return None

            return content

        except Exception as e:
            print(f"Error reading file {key}: {e}")
            return None
