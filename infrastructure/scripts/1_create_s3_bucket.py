"""
Script 1: Create and configure the S3 bucket for RAG document storage.
Usage: python 1_create_s3_bucket.py
Prerequisites: .env file with AWS_REGION, TEAM_NAME, PROJECT_NAME
"""

import os
import sys

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
TEAM_NAME = os.environ.get('TEAM_NAME', '')
PROJECT_NAME = os.environ.get('PROJECT_NAME', 'rag-class')


def create_s3_bucket(bucket_name: str, region: str) -> bool:
    """Create S3 bucket with encryption, versioning, and tags."""
    s3 = boto3.client('s3', region_name=region)

    print(f"Creating S3 bucket: {bucket_name} in {region}")
    try:
        if region == 'us-east-1':
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )
        print(f"Bucket {bucket_name} created.")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code in ('BucketAlreadyOwnedByYou', 'BucketAlreadyExists'):
            print(f"Bucket {bucket_name} already exists, skipping creation.")
        else:
            print(f"Error creating bucket: {e}")
            return False

    try:
        s3.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                'BlockPublicAcls': True,
                'IgnorePublicAcls': True,
                'BlockPublicPolicy': True,
                'RestrictPublicBuckets': True,
            }
        )
        print("Public access blocked.")

        s3.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={'Status': 'Enabled'}
        )
        print("Versioning enabled.")

        s3.put_bucket_encryption(
            Bucket=bucket_name,
            ServerSideEncryptionConfiguration={
                'Rules': [{
                    'ApplyServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'},
                    'BucketKeyEnabled': True,
                }]
            }
        )
        print("Server-side encryption (AES256) enabled.")

        s3.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={'TagSet': [
                {'Key': 'Project', 'Value': PROJECT_NAME},
                {'Key': 'Team', 'Value': TEAM_NAME},
                {'Key': 'Stage', 'Value': '1'},
                {'Key': 'ManagedBy', 'Value': 'script'},
            ]}
        )
        print("Tags applied.")

    except ClientError as e:
        print(f"Error configuring bucket: {e}")
        return False

    bucket_arn = f"arn:aws:s3:::{bucket_name}"
    print(f"\nS3 Bucket Ready")
    print(f"  Bucket Name : {bucket_name}")
    print(f"  Bucket ARN  : {bucket_arn}")
    print(f"  Region      : {region}")
    return True


def main():
    if not TEAM_NAME:
        print("Error: TEAM_NAME environment variable is required.")
        sys.exit(1)

    bucket_name = os.environ.get('S3_BUCKET', f"{PROJECT_NAME}-docs-{TEAM_NAME}")
    success = create_s3_bucket(bucket_name, AWS_REGION)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
