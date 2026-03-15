"""
Script 5: Create and configure an Amazon OpenSearch Serverless collection.
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

WAIT_INTERVAL_SECONDS = 10
WAIT_TIMEOUT_SECONDS = 300  # 5 minutes (much faster than managed domain)


def get_account_id() -> str:
    return boto3.client('sts').get_caller_identity()['Account']


def create_opensearch_serverless_collection(
    collection_name: str, 
    role_name: str,
    region: str, 
    account_id: str
) -> bool:
    """Create OpenSearch Serverless collection with encryption, network, and data access policies."""
    client = boto3.client('opensearchserverless', region_name=region)
    
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
    
    # Step 1: Create encryption policy (required for serverless)
    encryption_policy_name = f"{collection_name}-encryption"
    encryption_policy = {
        "Rules": [
            {
                "ResourceType": "collection",
                "Resource": [f"collection/{collection_name}"]
            }
        ],
        "AWSOwnedKey": True
    }
    
    print(f"Creating encryption policy: {encryption_policy_name}")
    try:
        client.create_security_policy(
            name=encryption_policy_name,
            type='encryption',
            policy=json.dumps(encryption_policy)
        )
        print(f"  Encryption policy created.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConflictException':
            print(f"  Encryption policy {encryption_policy_name} already exists.")
        else:
            print(f"  Error creating encryption policy: {e}")
            return False
    
    # Step 2: Create network policy (public access for simplicity)
    network_policy_name = f"{collection_name}-network"
    network_policy = [
        {
            "Rules": [
                {
                    "ResourceType": "collection",
                    "Resource": [f"collection/{collection_name}"]
                },
                {
                    "ResourceType": "dashboard",
                    "Resource": [f"collection/{collection_name}"]
                }
            ],
            "AllowFromPublic": True
        }
    ]
    
    print(f"Creating network policy: {network_policy_name}")
    try:
        client.create_security_policy(
            name=network_policy_name,
            type='network',
            policy=json.dumps(network_policy)
        )
        print(f"  Network policy created.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConflictException':
            print(f"  Network policy {network_policy_name} already exists.")
        else:
            print(f"  Error creating network policy: {e}")
            return False
    
    # Step 3: Create data access policy (IAM-based access)
    access_policy_name = f"{collection_name}-access"
    access_policy = [
        {
            "Rules": [
                {
                    "ResourceType": "collection",
                    "Resource": [f"collection/{collection_name}"],
                    "Permission": [
                        "aoss:CreateCollectionItems",
                        "aoss:UpdateCollectionItems",
                        "aoss:DescribeCollectionItems"
                    ]
                },
                {
                    "ResourceType": "index",
                    "Resource": [f"index/{collection_name}/*"],
                    "Permission": [
                        "aoss:CreateIndex",
                        "aoss:UpdateIndex",
                        "aoss:DescribeIndex",
                        "aoss:ReadDocument",
                        "aoss:WriteDocument",
                        "aoss:DeleteIndex"
                    ]
                }
            ],
            "Principal": [role_arn],
            "Description": f"Data access policy for {collection_name}"
        }
    ]
    
    print(f"Creating data access policy: {access_policy_name}")
    try:
        client.create_access_policy(
            name=access_policy_name,
            type='data',
            policy=json.dumps(access_policy)
        )
        print(f"  Data access policy created.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConflictException':
            print(f"  Data access policy {access_policy_name} already exists.")
        else:
            print(f"  Error creating data access policy: {e}")
            return False
    
    # Step 4: Create the OpenSearch Serverless collection
    print(f"Creating OpenSearch Serverless collection: {collection_name} (this takes ~1-2 minutes)")
    try:
        response = client.create_collection(
            name=collection_name,
            type='VECTORSEARCH',  # Optimized for vector search workloads
            description=f"RAG vector database for {TEAM_NAME}",
            tags=[
                {'key': 'Project', 'value': PROJECT_NAME},
                {'key': 'Team', 'value': TEAM_NAME},
                {'key': 'Stage', 'value': '1'},
                {'key': 'ManagedBy', 'value': 'script'},
            ]
        )
        collection_id = response['createCollectionDetail']['id']
        collection_arn = response['createCollectionDetail']['arn']
        print(f"  Collection creation initiated. ID: {collection_id}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConflictException':
            print(f"  Collection {collection_name} already exists, fetching details...")
            try:
                response = client.batch_get_collection(names=[collection_name])
                if response['collectionDetails']:
                    collection = response['collectionDetails'][0]
                    collection_id = collection['id']
                    collection_arn = collection['arn']
                    endpoint = collection.get('collectionEndpoint', 'pending')
                    status = collection['status']
                    
                    if status == 'ACTIVE':
                        print(f"\n✅ OpenSearch Serverless Collection Ready")
                        print(f"  Collection Name : {collection_name}")
                        print(f"  Collection ID   : {collection_id}")
                        print(f"  Endpoint        : {endpoint}")
                        print(f"  ARN             : {collection_arn}")
                        print(f"  Region          : {region}")
                        return True
            except ClientError as get_err:
                print(f"  Error fetching collection: {get_err}")
                return False
        else:
            print(f"  Error creating collection: {e}")
            return False
    
    # Step 5: Wait for collection to become active
    print("  Waiting for collection to become active (checking every 10 seconds)...")
    elapsed = 0
    endpoint = None
    
    while elapsed < WAIT_TIMEOUT_SECONDS:
        time.sleep(WAIT_INTERVAL_SECONDS)
        elapsed += WAIT_INTERVAL_SECONDS
        
        try:
            response = client.batch_get_collection(names=[collection_name])
            if response['collectionDetails']:
                collection = response['collectionDetails'][0]
                status = collection['status']
                endpoint = collection.get('collectionEndpoint', 'pending')
                
                if status == 'ACTIVE':
                    print(f"  Collection is active after {elapsed} seconds.")
                    break
                else:
                    print(f"  Still creating... Status: {status} ({elapsed}s elapsed)")
        except ClientError as poll_err:
            print(f"  Warning: error polling collection status: {poll_err}")
    else:
        print(f"  Timeout: collection still not active after {WAIT_TIMEOUT_SECONDS} seconds.")
        return False
    
    print(f"\n✅ OpenSearch Serverless Collection Ready")
    print(f"  Collection Name : {collection_name}")
    print(f"  Collection ID   : {collection_id}")
    print(f"  Endpoint        : {endpoint}")
    print(f"  ARN             : {collection_arn}")
    print(f"  Region          : {region}")
    print(f"  Type            : VECTORSEARCH (optimized for vector embeddings)")
    return True


def main():
    if not TEAM_NAME:
        print("Error: TEAM_NAME environment variable is required.")
        sys.exit(1)

    account_id = get_account_id()
    # Use OPENSEARCH_COLLECTION for serverless, fallback to OPENSEARCH_DOMAIN for compatibility
    collection_name = os.environ.get('OPENSEARCH_COLLECTION', f"{PROJECT_NAME}-{TEAM_NAME}")
    role_name = os.environ.get('IAM_ROLE_NAME', f"{PROJECT_NAME}-ec2-role-{TEAM_NAME}")
    success = create_opensearch_serverless_collection(
        collection_name, role_name, AWS_REGION, account_id
    )
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()