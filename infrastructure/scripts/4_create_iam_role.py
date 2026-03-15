"""
Script 4: Create IAM role and instance profile for the EC2 instance.
Usage: python 4_create_iam_role.py
Prerequisites: Scripts 1 and 2 must have been run (bucket and queue must exist).
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

POLICIES_DIR = os.path.join(os.path.dirname(__file__), '..', 'policies')


def load_policy_template(filename: str, replacements: dict) -> str:
    """Load a JSON policy template and replace placeholders."""
    path = os.path.join(POLICIES_DIR, filename)
    with open(path, 'r') as f:
        content = f.read()
    for key, value in replacements.items():
        content = content.replace(f"{{{{{key}}}}}", value)
    return content


def get_account_id() -> str:
    return boto3.client('sts').get_caller_identity()['Account']


def create_iam_role(role_name: str, profile_name: str, bucket_name: str,
                    queue_name: str, opensearch_collection: str,
                    region: str, account_id: str) -> bool:
    """Create IAM role with inline policy and instance profile."""
    iam = boto3.client('iam')

    trust_policy_path = os.path.join(POLICIES_DIR, 'ec2-trust-policy.json')
    with open(trust_policy_path, 'r') as f:
        trust_policy = f.read()

    # at first create IAM role with trsust policy that allows EC2 service to assume the role. 
    print(f"Creating IAM role: {role_name}")
    try:
        iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=trust_policy,
            Description=f"EC2 role for RAG system - {TEAM_NAME}",
            Tags=[
                {'Key': 'Project', 'Value': PROJECT_NAME},
                {'Key': 'Team', 'Value': TEAM_NAME},
                {'Key': 'Stage', 'Value': '1'},
                {'Key': 'ManagedBy', 'Value': 'script'},
            ]
        )
        print(f"IAM role {role_name} created.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"IAM role {role_name} already exists, skipping creation.")
        else:
            print(f"Error creating IAM role: {e}")
            return False

    # Create and attach permissions policy for S3, SQS, and OpenSearch access to the role
    replacements = {
        'BUCKET_NAME': bucket_name,
        'AWS_REGION': region,
        'ACCOUNT_ID': account_id,
        'QUEUE_NAME': queue_name,
    }
    try:
        permissions_policy = load_policy_template('iam-permissions-policy.json', replacements)
    except FileNotFoundError:
        print("Error: iam-permissions-policy.json not found in policies directory.")
        return False

    policy_name = f"{PROJECT_NAME}-ec2-policy-{TEAM_NAME}"
    try:
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=permissions_policy
        )
        print(f"Permissions policy {policy_name} attached to role.")
    except ClientError as e:
        print(f"Error attaching policy: {e}")
        return False

    # Create instance profile and add role to it. 
    # will be used to attach the role to the EC2 instance
    print(f"Creating instance profile: {profile_name}")
    try:
        iam.create_instance_profile(InstanceProfileName=profile_name)
        print(f"Instance profile {profile_name} created.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"Instance profile {profile_name} already exists.")
        else:
            print(f"Error creating instance profile: {e}")
            return False

    try:
        profile = iam.get_instance_profile(InstanceProfileName=profile_name)
        attached_roles = [r['RoleName'] for r in profile['InstanceProfile']['Roles']]
        if role_name not in attached_roles:
            iam.add_role_to_instance_profile(
                InstanceProfileName=profile_name,
                RoleName=role_name
            )
            print(f"Role {role_name} added to instance profile.")
        else:
            print(f"Role {role_name} already attached to instance profile.")
    except ClientError as e:
        print(f"Error attaching role to instance profile: {e}")
        return False

    role_arn = iam.get_role(RoleName=role_name)['Role']['Arn']
    print(f"\nIAM Role Ready")
    print(f"  Role Name             : {role_name}")
    print(f"  Role ARN              : {role_arn}")
    print(f"  Instance Profile Name : {profile_name}")
    return True


def main():
    if not TEAM_NAME:
        print("Error: TEAM_NAME environment variable is required.")
        sys.exit(1)

    account_id = get_account_id()
    role_name = os.environ.get('IAM_ROLE_NAME', f"{PROJECT_NAME}-ec2-role-{TEAM_NAME}")
    profile_name = os.environ.get('IAM_INSTANCE_PROFILE', f"{PROJECT_NAME}-ec2-profile-{TEAM_NAME}")
    bucket_name = os.environ.get('S3_BUCKET', f"{PROJECT_NAME}-docs-{TEAM_NAME}")
    queue_name = os.environ.get('SQS_QUEUE_NAME', f"{PROJECT_NAME}-docs-queue-{TEAM_NAME}")
    opensearch_collection = os.environ.get('OPENSEARCH_COLLECTION', f"{PROJECT_NAME}-{TEAM_NAME}")

    success = create_iam_role(
        role_name, profile_name, bucket_name, queue_name,
        opensearch_collection, AWS_REGION, account_id
    )
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
