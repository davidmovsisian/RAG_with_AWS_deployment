"""
setup_kb.py: Set up an AWS Bedrock Knowledge Base for RAG (educational example).

This script creates all the AWS infrastructure needed for a Bedrock Knowledge Base:
  1. IAM role with permissions for Bedrock, S3, and OpenSearch Serverless
  2. OpenSearch Serverless collection for vector storage
  3. The Knowledge Base resource itself
  4. An S3 data source linked to the Knowledge Base

Usage:
    python setup_kb.py

Prerequisites:
    - AWS credentials configured (via ~/.aws/credentials or environment variables)
    - An S3 bucket containing your documents (update S3_BUCKET_NAME below)
    - pip install boto3>=1.34.0
"""

import json
import os
import sys
import time

import boto3
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Configuration — edit these values before running
# ---------------------------------------------------------------------------
KB_NAME = "educational-rag-kb"
KB_DESCRIPTION = "Educational example of Bedrock Knowledge Base for RAG"
S3_BUCKET_NAME = "your-kb-documents-bucket"  # ← replace with your bucket name
S3_PREFIX = "documents/"
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
# ---------------------------------------------------------------------------


def get_account_id() -> str:
    """Return the current AWS account ID."""
    return boto3.client("sts").get_caller_identity()["Account"]


def create_kb_role(account_id: str, bucket_name: str) -> str:
    """Create an IAM role that Bedrock can assume to access S3 and OpenSearch.

    The role uses a trust policy that allows bedrock.amazonaws.com to assume it,
    and an inline policy granting the permissions the Knowledge Base service needs.

    Args:
        account_id: AWS account ID used to build resource ARNs.
        bucket_name: Name of the S3 bucket holding the source documents.

    Returns:
        The ARN of the newly created (or existing) IAM role.
    """
    iam = boto3.client("iam")
    role_name = f"{KB_NAME}-role"

    # Trust policy: allow the Bedrock service to assume this role
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    print(f"🔑 Creating IAM role: {role_name}")
    try:
        response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="IAM role for Bedrock Knowledge Base (educational example)",
        )
        role_arn = response["Role"]["Arn"]
        print(f"  ✅ Role created: {role_arn}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            role_arn = iam.get_role(RoleName=role_name)["Role"]["Arn"]
            print(f"  ℹ️  Role already exists: {role_arn}")
        else:
            print(f"  ❌ Error creating role: {e}")
            raise

    # Permissions policy: grant Bedrock the access it needs
    permissions_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                # Allow reading documents from S3
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:ListBucket"],
                "Resource": [
                    f"arn:aws:s3:::{bucket_name}",
                    f"arn:aws:s3:::{bucket_name}/*",
                ],
            },
            {
                # Allow calling Bedrock embedding and foundation models
                "Effect": "Allow",
                "Action": ["bedrock:InvokeModel"],
                "Resource": "*",
            },
            {
                # Allow read/write access to the OpenSearch Serverless collection
                "Effect": "Allow",
                "Action": [
                    "aoss:APIAccessAll",
                ],
                "Resource": f"arn:aws:aoss:{AWS_REGION}:{account_id}:collection/*",
            },
        ],
    }

    try:
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{KB_NAME}-permissions",
            PolicyDocument=json.dumps(permissions_policy),
        )
        print("  ✅ Permissions policy attached")
    except ClientError as e:
        print(f"  ❌ Error attaching permissions policy: {e}")
        raise

    return role_arn


def create_opensearch_collection(role_arn: str) -> str:
    """Create an OpenSearch Serverless collection for vector storage.

    OpenSearch Serverless is used by Bedrock Knowledge Bases to store and
    search the embedding vectors generated from your documents.

    Args:
        role_arn: ARN of the IAM role that will access this collection.

    Returns:
        The HTTP endpoint of the OpenSearch Serverless collection.
    """
    aoss = boto3.client("opensearchserverless", region_name=AWS_REGION)
    collection_name = f"{KB_NAME}-vectors"

    # Security policy: allow the KB role to access the collection
    network_policy = [
        {
            "Rules": [
                {
                    "Resource": [f"collection/{collection_name}"],
                    "ResourceType": "collection",
                },
                {
                    "Resource": [f"collection/{collection_name}"],
                    "ResourceType": "dashboard",
                },
            ],
            "AllowFromPublic": True,
        }
    ]

    encryption_policy = {
        "Rules": [
            {
                "Resource": [f"collection/{collection_name}"],
                "ResourceType": "collection",
            }
        ],
        "AWSOwnedKey": True,
    }

    data_access_policy = [
        {
            "Rules": [
                {
                    "Resource": [f"collection/{collection_name}"],
                    "Permission": [
                        "aoss:CreateCollectionItems",
                        "aoss:DeleteCollectionItems",
                        "aoss:UpdateCollectionItems",
                        "aoss:DescribeCollectionItems",
                    ],
                    "ResourceType": "collection",
                },
                {
                    "Resource": [f"index/{collection_name}/*"],
                    "Permission": [
                        "aoss:CreateIndex",
                        "aoss:DeleteIndex",
                        "aoss:UpdateIndex",
                        "aoss:DescribeIndex",
                        "aoss:ReadDocument",
                        "aoss:WriteDocument",
                    ],
                    "ResourceType": "index",
                },
            ],
            "Principal": [role_arn],
        }
    ]

    print(f"\n🗄️  Creating OpenSearch Serverless collection: {collection_name}")

    # Create security policies first (required before creating the collection)
    for policy_name, policy_type, policy_body in [
        (f"{collection_name}-network", "network", json.dumps(network_policy)),
        (f"{collection_name}-encryption", "encryption", json.dumps(encryption_policy)),
    ]:
        try:
            aoss.create_security_policy(
                name=policy_name, type=policy_type, policy=policy_body
            )
            print(f"  ✅ {policy_type.capitalize()} policy created")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConflictException":
                print(f"  ℹ️  {policy_type.capitalize()} policy already exists")
            else:
                print(f"  ❌ Error creating {policy_type} policy: {e}")
                raise

    try:
        aoss.create_access_policy(
            name=f"{collection_name}-access",
            type="data",
            policy=json.dumps(data_access_policy),
        )
        print("  ✅ Data access policy created")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConflictException":
            print("  ℹ️  Data access policy already exists")
        else:
            print(f"  ❌ Error creating data access policy: {e}")
            raise

    # Create the VECTORSEARCH collection — this is what stores the embeddings
    try:
        response = aoss.create_collection(
            name=collection_name,
            type="VECTORSEARCH",  # Optimized for vector similarity search
            description="Vector store for Bedrock Knowledge Base (educational example)",
        )
        collection_id = response["createCollectionDetail"]["id"]
        print(f"  🔄 Collection created (id={collection_id}), waiting for ACTIVE state...")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConflictException":
            # Collection already exists; look up its endpoint
            existing = aoss.list_collections(
                collectionFilters={"name": collection_name}
            )
            collection_id = existing["collectionSummaries"][0]["id"]
            print(f"  ℹ️  Collection already exists (id={collection_id})")
        else:
            print(f"  ❌ Error creating collection: {e}")
            raise

    # Poll until the collection is ACTIVE (can take several minutes)
    while True:
        detail = aoss.batch_get_collection(ids=[collection_id])
        status = detail["collectionDetails"][0]["status"]
        if status == "ACTIVE":
            endpoint = detail["collectionDetails"][0]["collectionEndpoint"]
            print(f"  ✅ Collection is ACTIVE: {endpoint}")
            return endpoint
        if status == "FAILED":
            print("  ❌ Collection creation failed")
            sys.exit(1)
        print(f"  🔄 Status: {status} — waiting 15 seconds...")
        time.sleep(15)


def create_knowledge_base(role_arn: str, collection_endpoint: str) -> str:
    """Create the Bedrock Knowledge Base resource.

    The Knowledge Base ties together:
    - The embedding model (Amazon Titan) used to vectorise documents
    - The OpenSearch Serverless collection used to store and retrieve vectors

    Args:
        role_arn: ARN of the IAM role with permissions for Bedrock and OpenSearch.
        collection_endpoint: HTTP endpoint of the OpenSearch Serverless collection.

    Returns:
        The Knowledge Base ID assigned by AWS.
    """
    bedrock_agent = boto3.client("bedrock-agent", region_name=AWS_REGION)
    index_name = "bedrock-knowledge-base-index"

    print(f"\n🧠 Creating Bedrock Knowledge Base: {KB_NAME}")
    try:
        response = bedrock_agent.create_knowledge_base(
            name=KB_NAME,
            description=KB_DESCRIPTION,
            roleArn=role_arn,
            knowledgeBaseConfiguration={
                "type": "VECTOR",
                "vectorKnowledgeBaseConfiguration": {
                    # Titan embeddings model converts text chunks to vectors
                    "embeddingModelArn": (
                        f"arn:aws:bedrock:{AWS_REGION}::foundation-model/"
                        "amazon.titan-embed-text-v1"
                    ),
                },
            },
            storageConfiguration={
                "type": "OPENSEARCH_SERVERLESS",
                "opensearchServerlessConfiguration": {
                    "collectionArn": collection_endpoint,
                    "vectorIndexName": index_name,
                    "fieldMapping": {
                        # Field names in the OpenSearch index
                        "vectorField": "embedding",
                        "textField": "text",
                        "metadataField": "metadata",
                    },
                },
            },
        )
        kb_id = response["knowledgeBase"]["knowledgeBaseId"]
        print(f"  ✅ Knowledge Base created: {kb_id}")
        return kb_id
    except ClientError as e:
        print(f"  ❌ Error creating Knowledge Base: {e}")
        raise


def create_data_source(kb_id: str, role_arn: str) -> str:
    """Create an S3 data source and link it to the Knowledge Base.

    The data source tells Bedrock where to find documents.  When you later
    run a sync (ingestion job) Bedrock will:
      1. Read documents from S3
      2. Split them into chunks (FIXED_SIZE, 300 tokens, 20 % overlap)
      3. Generate embeddings via Titan
      4. Store the vectors in OpenSearch Serverless

    Args:
        kb_id: ID of the Knowledge Base to attach the data source to.
        role_arn: ARN of the IAM role used to read from S3.

    Returns:
        The data source ID assigned by AWS.
    """
    bedrock_agent = boto3.client("bedrock-agent", region_name=AWS_REGION)

    print(f"\n📦 Creating S3 data source (bucket={S3_BUCKET_NAME})")
    try:
        response = bedrock_agent.create_data_source(
            knowledgeBaseId=kb_id,
            name=f"{KB_NAME}-s3-source",
            description="S3 document source for educational RAG example",
            dataSourceConfiguration={
                "type": "S3",
                "s3Configuration": {
                    "bucketArn": f"arn:aws:s3:::{S3_BUCKET_NAME}",
                    "inclusionPrefixes": [S3_PREFIX],
                },
            },
            vectorIngestionConfiguration={
                "chunkingConfiguration": {
                    # FIXED_SIZE chunking: each chunk is ~300 tokens with
                    # 20 % overlap so context is preserved across chunk boundaries.
                    # Compare this to the custom chunking in src/utils/chunking.py
                    # where you control every parameter of the algorithm.
                    "chunkingStrategy": "FIXED_SIZE",
                    "fixedSizeChunkingConfiguration": {
                        "maxTokens": 300,
                        "overlapPercentage": 20,
                    },
                }
            },
        )
        ds_id = response["dataSource"]["dataSourceId"]
        print(f"  ✅ Data source created: {ds_id}")
        return ds_id
    except ClientError as e:
        print(f"  ❌ Error creating data source: {e}")
        raise


def main() -> None:
    """Orchestrate the full Knowledge Base setup flow."""
    print("=" * 60)
    print("🚀 Bedrock Knowledge Base Setup (Educational Example)")
    print("=" * 60)

    if S3_BUCKET_NAME == "your-kb-documents-bucket":
        print(
            "\n❌  Please update S3_BUCKET_NAME at the top of this script "
            "before running."
        )
        sys.exit(1)

    account_id = get_account_id()
    print(f"\nℹ️  AWS Account : {account_id}")
    print(f"ℹ️  AWS Region  : {AWS_REGION}")
    print(f"ℹ️  S3 Bucket   : {S3_BUCKET_NAME}")

    # Step 1 — IAM role
    role_arn = create_kb_role(account_id, S3_BUCKET_NAME)

    # Step 2 — OpenSearch Serverless collection
    collection_endpoint = create_opensearch_collection(role_arn)

    # Step 3 — Knowledge Base
    kb_id = create_knowledge_base(role_arn, collection_endpoint)

    # Step 4 — S3 data source
    ds_id = create_data_source(kb_id, role_arn)

    print("\n" + "=" * 60)
    print("✅  Setup complete!  Save these IDs for the next steps:")
    print(f"   Knowledge Base ID : {kb_id}")
    print(f"   Data Source ID    : {ds_id}")
    print("\nNext steps:")
    print(f"  1. Upload documents to s3://{S3_BUCKET_NAME}/{S3_PREFIX}")
    print(f"  2. python sync_documents.py {kb_id} {ds_id}")
    print(f"  3. python query_kb.py {kb_id} 'Your question here'")
    print("=" * 60)


if __name__ == "__main__":
    main()
