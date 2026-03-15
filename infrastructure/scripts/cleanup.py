"""
cleanup.py: Interactively delete all AWS infrastructure resources in reverse order.
Usage: python cleanup.py
Prerequisites: .env file with AWS_REGION, TEAM_NAME, PROJECT_NAME
"""

import os
import sys
import time

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
TEAM_NAME = os.environ.get('TEAM_NAME', '')
PROJECT_NAME = os.environ.get('PROJECT_NAME', 'rag-class')


def confirm_deletion() -> bool:
    """Prompt user for confirmation before deleting resources."""
    print("\nWARNING: This will permanently delete all AWS infrastructure resources.")
    print("Resources to be deleted:")
    print(f"  - EC2 instance: {PROJECT_NAME}-ec2-{TEAM_NAME}")
    print(f"  - Security group: {PROJECT_NAME}-sg-{TEAM_NAME}")
    print(f"  - Instance profile: {PROJECT_NAME}-ec2-profile-{TEAM_NAME}")
    print(f"  - IAM role: {PROJECT_NAME}-ec2-role-{TEAM_NAME}")
    print(f"  - OpenSearch Serverless collection: {PROJECT_NAME}-{TEAM_NAME}")
    print(f"  - SQS queue: {PROJECT_NAME}-docs-queue-{TEAM_NAME}")
    print(f"  - S3 bucket: {PROJECT_NAME}-docs-{TEAM_NAME}")
    answer = input("\nType 'yes' to confirm: ").strip().lower()
    return answer == 'yes'


def terminate_ec2(ec2, instance_name: str) -> None:
    """Terminate EC2 instance and wait for it to stop."""
    print(f"\n[1] Terminating EC2 instance: {instance_name}")
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'tag:Name', 'Values': [instance_name]},
            {'Name': 'instance-state-name', 'Values': ['running', 'stopped', 'pending']},
        ]
    )
    instance_ids = [
        i['InstanceId']
        for r in response.get('Reservations', [])
        for i in r['Instances']
    ]
    if not instance_ids:
        print(f"  Instance {instance_name} not found, skipping.")
        return
    ec2.terminate_instances(InstanceIds=instance_ids)
    print(f"  Termination requested for: {instance_ids}. Waiting...")
    waiter = ec2.get_waiter('instance_terminated')
    waiter.wait(InstanceIds=instance_ids)
    print("  Instance terminated.")


def delete_security_group(ec2, sg_name: str) -> None:
    """Delete security group."""
    print(f"\n[2] Deleting security group: {sg_name}")
    try:
        response = ec2.describe_security_groups(
            Filters=[{'Name': 'group-name', 'Values': [sg_name]}]
        )
        groups = response.get('SecurityGroups', [])
        if not groups:
            print(f"  Security group {sg_name} not found, skipping.")
            return
        sg_id = groups[0]['GroupId']
        ec2.delete_security_group(GroupId=sg_id)
        print(f"  Security group {sg_id} deleted.")
    except ClientError as e:
        print(f"  Error deleting security group: {e}")


def delete_instance_profile(iam, profile_name: str, role_name: str) -> None:
    """Detach role from instance profile and delete it."""
    print(f"\n[3] Deleting instance profile: {profile_name}")
    try:
        profile = iam.get_instance_profile(InstanceProfileName=profile_name)
        for role in profile['InstanceProfile']['Roles']:
            iam.remove_role_from_instance_profile(
                InstanceProfileName=profile_name,
                RoleName=role['RoleName']
            )
            print(f"  Detached role {role['RoleName']} from instance profile.")
        iam.delete_instance_profile(InstanceProfileName=profile_name)
        print(f"  Instance profile {profile_name} deleted.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchEntity':
            print(f"  Instance profile {profile_name} not found, skipping.")
        else:
            print(f"  Error deleting instance profile: {e}")


def delete_iam_role(iam, role_name: str) -> None:
    """Delete inline policies and IAM role."""
    print(f"\n[4] Deleting IAM role: {role_name}")
    try:
        paginator = iam.get_paginator('list_role_policies')
        for page in paginator.paginate(RoleName=role_name):
            for policy_name in page['PolicyNames']:
                iam.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
                print(f"  Deleted inline policy: {policy_name}")

        attached = iam.list_attached_role_policies(RoleName=role_name)
        for policy in attached.get('AttachedPolicies', []):
            iam.detach_role_policy(RoleName=role_name, PolicyArn=policy['PolicyArn'])
            print(f"  Detached managed policy: {policy['PolicyName']}")

        iam.delete_role(RoleName=role_name)
        print(f"  IAM role {role_name} deleted.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchEntity':
            print(f"  IAM role {role_name} not found, skipping.")
        else:
            print(f"  Error deleting IAM role: {e}")


def delete_opensearch_serverless_collection(collection_name: str, region: str) -> None:
    """Delete OpenSearch Serverless collection and associated policies."""
    print(f"\n[4] Deleting OpenSearch Serverless collection: {collection_name}")
    client = boto3.client('opensearchserverless', region_name=region)
    
    try:
        # Delete collection
        client.delete_collection(name=collection_name)
        print(f"  Collection {collection_name} deletion initiated. Waiting...")
        
        # Wait for deletion (max 5 minutes)
        elapsed = 0
        while elapsed < 300:
            time.sleep(10)
            elapsed += 10
            try:
                response = client.batch_get_collection(names=[collection_name])
                if not response['collectionDetails']:
                    print(f"  Collection deleted after {elapsed} seconds.")
                    break
                status = response['collectionDetails'][0]['status']
                print(f"  Status: {status} ({elapsed}s elapsed)")
            except ClientError:
                print(f"  Collection deleted after {elapsed} seconds.")
                break
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"  Collection {collection_name} not found, skipping.")
        else:
            print(f"  Error deleting collection: {e}")
    
    # Delete associated policies
    for policy_type, policy_name_suffix in [
        ('data', '-access'),
        ('network', '-network'),
        ('encryption', '-encryption')
    ]:
        policy_name = f"{collection_name}{policy_name_suffix}"
        try:
            if policy_type == 'data':
                client.delete_access_policy(name=policy_name, type=policy_type)
            elif policy_type == 'network':
                client.delete_security_policy(name=policy_name, type=policy_type)
            elif policy_type == 'encryption':
                client.delete_encryption_policy(name=policy_name, type=policy_type)
            print(f"  Deleted {policy_type} policy: {policy_name}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                print(f"  Policy {policy_name} not found, skipping.")
            else:
                print(f"  Error deleting {policy_type} policy: {e}")


def remove_s3_event_notification(s3, bucket_name: str) -> None:
    """Remove all S3 event notifications from bucket."""
    print(f"\n[6] Removing S3 event notifications from: {bucket_name}")
    try:
        s3.put_bucket_notification_configuration(
            Bucket=bucket_name,
            NotificationConfiguration={}
        )
        print("  Event notifications removed.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchBucket':
            print(f"  Bucket {bucket_name} not found, skipping.")
        else:
            print(f"  Error removing notifications: {e}")


def delete_sqs_queue(sqs, queue_name: str) -> None:
    """Purge and delete SQS queue."""
    print(f"\n[7] Deleting SQS queue: {queue_name}")
    try:
        queue_url = sqs.get_queue_url(QueueName=queue_name)['QueueUrl']
        try:
            sqs.purge_queue(QueueUrl=queue_url)
            print("  Queue purged.")
        except ClientError:
            pass
        sqs.delete_queue(QueueUrl=queue_url)
        print(f"  Queue {queue_name} deleted.")
    except ClientError as e:
        if e.response['Error']['Code'] in ('AWS.SimpleQueueService.NonExistentQueue', 'QueueDoesNotExist'):
            print(f"  Queue {queue_name} not found, skipping.")
        else:
            print(f"  Error deleting queue: {e}")


def empty_and_delete_s3_bucket(s3_resource, s3_client, bucket_name: str) -> None:
    """Delete all objects and the S3 bucket."""
    print(f"\n[8] Deleting S3 bucket: {bucket_name}")
    try:
        bucket = s3_resource.Bucket(bucket_name)
        print("  Deleting all objects and versions...")
        bucket.object_versions.delete()
        bucket.objects.delete()
        s3_client.delete_bucket(Bucket=bucket_name)
        print(f"  Bucket {bucket_name} deleted.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchBucket':
            print(f"  Bucket {bucket_name} not found, skipping.")
        else:
            print(f"  Error deleting bucket: {e}")


def main():
    if not TEAM_NAME:
        print("Error: TEAM_NAME environment variable is required.")
        sys.exit(1)

    if not confirm_deletion():
        print("Cleanup cancelled.")
        sys.exit(0)

    instance_name = f"{PROJECT_NAME}-ec2-{TEAM_NAME}"
    sg_name = f"{PROJECT_NAME}-sg-{TEAM_NAME}"
    profile_name = os.environ.get('IAM_INSTANCE_PROFILE', f"{PROJECT_NAME}-ec2-profile-{TEAM_NAME}")
    role_name = os.environ.get('IAM_ROLE_NAME', f"{PROJECT_NAME}-ec2-role-{TEAM_NAME}")
    collection_name = os.environ.get('OPENSEARCH_COLLECTION', f"{PROJECT_NAME}-{TEAM_NAME}")
    queue_name = os.environ.get('SQS_QUEUE_NAME', f"{PROJECT_NAME}-docs-queue-{TEAM_NAME}")
    bucket_name = os.environ.get('S3_BUCKET', f"{PROJECT_NAME}-docs-{TEAM_NAME}")

    ec2 = boto3.client('ec2', region_name=AWS_REGION)
    iam = boto3.client('iam')
    os_client = boto3.client('opensearch', region_name=AWS_REGION)
    sqs = boto3.client('sqs', region_name=AWS_REGION)
    s3_client = boto3.client('s3', region_name=AWS_REGION)
    s3_resource = boto3.resource('s3', region_name=AWS_REGION)

    terminate_ec2(ec2, instance_name)
    delete_security_group(ec2, sg_name)
    delete_instance_profile(iam, profile_name, role_name)
    delete_iam_role(iam, role_name)
    delete_opensearch_serverless_collection(collection_name, AWS_REGION)
    remove_s3_event_notification(s3_client, bucket_name)
    delete_sqs_queue(sqs, queue_name)
    empty_and_delete_s3_bucket(s3_resource, s3_client, bucket_name)

    print("\nCleanup complete. All resources have been removed.")


if __name__ == '__main__':
    main()
