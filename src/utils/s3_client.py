import os
from typing import Optional, Tuple
import boto3

class S3Client:
    def __init__(self):
        region = os.getenv("AWS_REGION", "us-east-1")
        self.client = boto3.client("s3", region_name=region)
        self.bucket_name = os.getenv("S3_BUCKET_NAME", "")
        print(f"S3Client initialized (bucket={self.bucket_name})")

    def upload_file(self, file: str):
        content = file.read()
        key = file.filename
        self.client.put_object(Bucket=self.bucket_name, Key=key, Body=content)
        print(f"Uploaded content -> s3://{self.bucket_name}/{key}")
    
    def delete_file(self, key: str):
        self.client.delete_object(Bucket=self.bucket_name, Key=key)
        print(f"Deleted s3://{self.bucket_name}/{key}")

    def read_file_content(self, key: str) -> Optional[str]:
        print(f"Reading S3 object: {key} from bucket: {self.bucket_name}")
        response = self.client.get_object(Bucket=self.bucket_name, Key=key)
        file_bytes = response["Body"].read()
        content = file_bytes.decode("utf-8")
        print(f"Read {len(content)} characters from s3://{self.bucket_name}/{key}")
        return content

    def read_file_bytes(self, key: str) -> Optional[bytes]:
        print(f"Reading S3 object as bytes: {key}")
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            file_bytes = response["Body"].read()
            print(f"Read {len(file_bytes)} bytes from s3://{self.bucket_name}/{key}")
            return file_bytes
        except Exception as e:
            print(f"Error reading bytes from S3: {e}")
            return None
    
    def get_file_type(self, key: str) -> str:
        extension = os.path.splitext(key)[1].lower()
        if extension != '.pdf' and extension != '.txt':
            return 'unknown'
        else:
            return extension
            
    def list_files(self, prefix: str = "") -> list:
        paginator = self.client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
        files = []
        for page in page_iterator:
            contents = page.get('Contents', [])
            for obj in contents:
                files.append(obj['Key'])
        print(f"Listed {len(files)} files with prefix '{prefix}'")
        return files
