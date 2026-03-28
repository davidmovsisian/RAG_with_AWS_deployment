import os
import boto3

class S3Client:
    def __init__(self):
        region = os.getenv("AWS_REGION", "us-east-1")
        self.client = boto3.client("s3", region_name=region)
        self.bucket_name = os.getenv("S3_BUCKET_NAME", "")
        print(f"S3Client initialized (bucket={self.bucket_name})")

    def upload_file(self, file, prefix: str = "data/"):
        file.seek(0)
        key = f"{prefix.strip('/')}/{file.filename}"
        self.client.upload_fileobj(file, self.bucket_name, key)
        print(f"Uploaded content -> s3://{self.bucket_name}/{key}")
    
    def delete_file(self, filename: str, prefix: str = "data/"):
        key = f"{prefix.strip('/')}/{filename}" 
        self.client.delete_object(Bucket=self.bucket_name, Key=key)
        print(f"Deleted s3://{self.bucket_name}/{key}")
            
    def list_files(self, prefix: str = "data/") -> list:
        paginator = self.client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
        files = []
        for page in page_iterator:
            for obj in page.get('Contents', []):
                key = obj['Key']
                if not key.endswith('/'):
                    files.append(key)

        print(f"Listed {len(files)} files with prefix '{prefix}'")
        return files
