"""
Script 3: Configure S3 bucket to send ObjectCreated events to SQS queue.
Usage: python 3_setup_s3_event.py
Prerequisites: Scripts 1 and 2 must have been run first.
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


def setup_s3_event_notification(bucket_name: str, queue_name: str, region: str) -> bool:
    """Configure S3 to send ObjectCreated and ObjectRemoved events to SQS."""
    s3 = boto3.client('s3', region_name=region)
    sqs = boto3.client('sqs', region_name=region)

    print(f"Setting up S3 event notification: {bucket_name} -> {queue_name}")

    try:
        queue_url = sqs.get_queue_url(QueueName=queue_name)['QueueUrl']
        queue_arn = sqs.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['QueueArn']
        )['Attributes']['QueueArn']
        print(f"Queue ARN: {queue_arn}")
    except ClientError as e:
        print(f"Error fetching queue ARN: {e}")
        return False

    notification_config = {
        'QueueConfigurations': [{
            'Id': f"{PROJECT_NAME}-s3-event",
            'QueueArn': queue_arn,
            'Events': [
                's3:ObjectCreated:*',
                's3:ObjectRemoved:*'
            ],
        }]
    }

    try:
        s3.put_bucket_notification_configuration(
            Bucket=bucket_name,
            NotificationConfiguration=notification_config
        )
        print("Event notification configuration applied.")
    except ClientError as e:
        print(f"Error applying notification configuration: {e}")
        return False

    try:
        result = s3.get_bucket_notification_configuration(Bucket=bucket_name)
        configured_arns = [
            q.get('QueueArn', '')
            for q in result.get('QueueConfigurations', [])
        ]
        if queue_arn in configured_arns:
            print("Verification passed: queue ARN found in bucket notification config.")
        else:
            print("Warning: Could not verify notification config. Check manually.")
    except ClientError as e:
        print(f"Warning: Could not verify configuration: {e}")

    print(f"\nS3 -> SQS Event Wiring Complete")
    print(f"  Bucket    : {bucket_name}")
    print(f"  Queue ARN : {queue_arn}")
    print(f"  Events    : s3:ObjectCreated:*")
    return True


def main():
    if not TEAM_NAME:
        print("Error: TEAM_NAME environment variable is required.")
        sys.exit(1)

    bucket_name = os.environ.get('S3_BUCKET', f"{PROJECT_NAME}-docs-{TEAM_NAME}")
    queue_name = os.environ.get('SQS_QUEUE_NAME', f"{PROJECT_NAME}-docs-queue-{TEAM_NAME}")
    success = setup_s3_event_notification(bucket_name, queue_name, AWS_REGION)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
