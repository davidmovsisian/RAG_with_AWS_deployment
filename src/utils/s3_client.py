import os
from typing import Optional
import boto3

class S3Client:
    def __init__(self):
        region = os.getenv("AWS_REGION", "us-east-1")
        self.client = boto3.client("s3", region_name=region)
        self.bucket_name = os.getenv("S3_BUCKET_NAME", "")
        print(f"S3Client initialized (bucket={self.bucket_name})")

    def upload_file(self, file: str):
        file.seek(0)
        key = file.filename
        self.client.upload_fileobj(file, self.bucket_name, key)
        print(f"Uploaded content -> s3://{self.bucket_name}/{key}")
    
    def delete_file(self, key: str):
        self.client.delete_object(Bucket=self.bucket_name, Key=key)
        print(f"Deleted s3://{self.bucket_name}/{key}")
            
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
