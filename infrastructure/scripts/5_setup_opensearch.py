"""
Script 5: Create and configure an Amazon OpenSearch Service domain.
Usage: python 5_setup_opensearch.py
Prerequisites: Script 4 must have been run (IAM role must exist).
"""

import json
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
OPENSEARCH_INSTANCE_TYPE = os.environ.get('OPENSEARCH_INSTANCE_TYPE', 't3.small.search')
OPENSEARCH_VOLUME_SIZE = int(os.environ.get('OPENSEARCH_VOLUME_SIZE', '10'))

WAIT_INTERVAL_SECONDS = 30
WAIT_TIMEOUT_SECONDS = 1800  # 30 minutes


def get_account_id() -> str:
    return boto3.client('sts').get_caller_identity()['Account']


def create_opensearch_domain(domain_name: str, role_name: str,
                              region: str, account_id: str) -> bool:
    """Create OpenSearch domain and wait for it to become active."""
    client = boto3.client('opensearch', region_name=region)

    # create access policy to allow the EC2 instance with IAM role to access the OpenSearch domain.
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}" #IAM role
    access_policy = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"AWS": role_arn}, #only allow access from EC2 instance with IAM role
            "Action": "es:*", #full access to OpenSearch for the EC2 instance
            "Resource": f"arn:aws:es:{region}:{account_id}:domain/{domain_name}/*", #target OpenSearch ARN
        }]
    })

    try:
        status = client.describe_domain(DomainName=domain_name)['DomainStatus']
        print(f"OpenSearch domain {domain_name} already exists, skipping creation.")
        endpoint = status.get('Endpoint', 'pending')
        domain_arn = status['ARN']
    except ClientError as e:
        if e.response['Error']['Code'] != 'ResourceNotFoundException':
            print(f"Error checking domain: {e}")
            return False

        print(f"Creating OpenSearch domain: {domain_name} (this takes ~10-15 minutes)")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.create_domain(
                    DomainName=domain_name,
                    EngineVersion='OpenSearch_2.11',
                    ClusterConfig={
                        'InstanceType': OPENSEARCH_INSTANCE_TYPE,
                        'InstanceCount': 1,
                        'DedicatedMasterEnabled': False,
                        'ZoneAwarenessEnabled': False,
                    },
                    EBSOptions={
                        'EBSEnabled': True,
                        'VolumeType': 'gp3',
                        'VolumeSize': OPENSEARCH_VOLUME_SIZE,
                    },
                    AccessPolicies=access_policy,
                    EncryptionAtRestOptions={'Enabled': True},
                    NodeToNodeEncryptionOptions={'Enabled': True},
                    DomainEndpointOptions={
                        'EnforceHTTPS': True,
                        'TLSSecurityPolicy': 'Policy-Min-TLS-1-2-2019-07',
                    },
                    AdvancedSecurityOptions={'Enabled': False},
                    TagList=[
                        {'Key': 'Project', 'Value': PROJECT_NAME},
                        {'Key': 'Team', 'Value': TEAM_NAME},
                        {'Key': 'Stage', 'Value': '1'},
                        {'Key': 'ManagedBy', 'Value': 'script'},
                    ]
                )
                domain_arn = response['DomainStatus']['ARN']
                print(f"Domain creation initiated. ARN: {domain_arn}")
            except ClientError as create_err:
                if "InvalidTypeException" in str(create_err) and attempt < max_retries - 1:
                    print(f"IAM Role might not be ready. Retrying in 30s... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(30)
                    continue
                else:
                    print(f"Error creating domain: {create_err}")
                    return False

        print("Waiting for domain to become active (checking every 30 seconds)...")
        elapsed = 0
        while elapsed < WAIT_TIMEOUT_SECONDS:
            time.sleep(WAIT_INTERVAL_SECONDS)
            elapsed += WAIT_INTERVAL_SECONDS
            try:
                status = client.describe_domain(DomainName=domain_name)['DomainStatus']
                processing = status.get('Processing', True)
                if not processing:
                    print(f"Domain is active after {elapsed // 60} minutes.")
                    break
                print(f"  Still creating... ({elapsed // 60}m {elapsed % 60}s elapsed)")
            except ClientError as poll_err:
                print(f"  Warning: error polling domain status: {poll_err}")
        else:
            print(f"Timeout: domain still processing after {WAIT_TIMEOUT_SECONDS // 60} minutes.")
            print("Check status with: aws opensearch describe-domain --domain-name " + domain_name)
            return False

        status = client.describe_domain(DomainName=domain_name)['DomainStatus']
        endpoint = status.get('Endpoint', 'pending')

    print(f"\nOpenSearch Domain Ready")
    print(f"  Domain Name : {domain_name}")
    print(f"  Endpoint    : {endpoint}")
    print(f"  ARN         : {domain_arn}")
    print(f"  Region      : {region}")
    return True


def main():
    if not TEAM_NAME:
        print("Error: TEAM_NAME environment variable is required.")
        sys.exit(1)

    account_id = get_account_id()
    domain_name = os.environ.get('OPENSEARCH_DOMAIN', f"{PROJECT_NAME}-{TEAM_NAME}")
    role_name = os.environ.get('IAM_ROLE_NAME', f"{PROJECT_NAME}-ec2-role-{TEAM_NAME}")
    success = create_opensearch_domain(domain_name, role_name, AWS_REGION, account_id)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
