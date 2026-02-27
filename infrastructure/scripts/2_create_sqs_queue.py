"""
Script 2: Create SQS queue for S3 document event messages.
Usage: python 2_create_sqs_queue.py
Prerequisites: .env file with AWS_REGION, TEAM_NAME, PROJECT_NAME
"""

import json
import os
import sys

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
TEAM_NAME = os.environ.get('TEAM_NAME', '')
PROJECT_NAME = os.environ.get('PROJECT_NAME', 'rag-class')


def get_account_id() -> str:
    sts = boto3.client('sts')
    return sts.get_caller_identity()['Account']


def create_sqs_queue(queue_name: str, bucket_name: str, region: str, account_id: str) -> bool:
    """Create SQS queue with long polling and S3 send-message policy."""
    sqs = boto3.client('sqs', region_name=region)

    queue_arn = f"arn:aws:sqs:{region}:{account_id}:{queue_name}"
    bucket_arn = f"arn:aws:s3:::{bucket_name}"

    queue_policy = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "AllowS3SendMessage",
            "Effect": "Allow",
            "Principal": {"Service": "s3.amazonaws.com"},
            "Action": "sqs:SendMessage",
            "Resource": queue_arn,
            "Condition": {"ArnEquals": {"aws:SourceArn": bucket_arn}},
        }]
    })

    print(f"Creating SQS queue: {queue_name}")
    try:
        response = sqs.create_queue(
            QueueName=queue_name,
            Attributes={
                'VisibilityTimeout': '300',
                'MessageRetentionPeriod': '345600',
                'ReceiveMessageWaitTimeSeconds': '20',
                'Policy': queue_policy,
            }
        )
        queue_url = response['QueueUrl']
        print(f"Queue created: {queue_url}")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'QueueAlreadyExists':
            print(f"Queue {queue_name} already exists, fetching URL.")
            queue_url = sqs.get_queue_url(QueueName=queue_name)['QueueUrl']
            sqs.set_queue_attributes(
                QueueUrl=queue_url,
                Attributes={
                    'VisibilityTimeout': '300',
                    'MessageRetentionPeriod': '345600',
                    'ReceiveMessageWaitTimeSeconds': '20',
                    'Policy': queue_policy,
                }
            )
        else:
            print(f"Error creating queue: {e}")
            return False

    try:
        sqs.tag_queue(
            QueueUrl=queue_url,
            Tags={
                'Project': PROJECT_NAME,
                'Team': TEAM_NAME,
                'Stage': '1',
                'ManagedBy': 'script',
            }
        )

        attrs = sqs.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['QueueArn']
        )
        actual_arn = attrs['Attributes']['QueueArn']
    except ClientError as e:
        print(f"Error tagging or fetching queue attributes: {e}")
        return False

    print(f"\nSQS Queue Ready")
    print(f"  Queue Name : {queue_name}")
    print(f"  Queue URL  : {queue_url}")
    print(f"  Queue ARN  : {actual_arn}")
    return True


def main():
    if not TEAM_NAME:
        print("Error: TEAM_NAME environment variable is required.")
        sys.exit(1)

    queue_name = os.environ.get('SQS_QUEUE_NAME', f"{PROJECT_NAME}-docs-queue-{TEAM_NAME}")
    bucket_name = os.environ.get('S3_BUCKET', f"{PROJECT_NAME}-docs-{TEAM_NAME}")
    account_id = get_account_id()
    success = create_sqs_queue(queue_name, bucket_name, AWS_REGION, account_id)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
