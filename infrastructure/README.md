# AWS Infrastructure Setup for RAG System

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Execution Order](#execution-order)
5. [Directory Structure](#directory-structure)
6. [Verification Steps](#verification-steps)
7. [Cost Estimates](#cost-estimates)
8. [Troubleshooting](#troubleshooting)
9. [Cleanup](#cleanup)

---

## Overview

This directory contains all scripts and configuration files needed to provision the AWS infrastructure for the RAG (Retrieval-Augmented Generation) system. The infrastructure consists of:

- **Amazon S3** – Document storage bucket
- **Amazon SQS** – Message queue for document processing events
- **AWS IAM** – Role and policies for EC2 service access
- **Amazon OpenSearch** – Vector database for semantic search
- **Amazon EC2** – Compute instance running the Flask API and SQS worker

### Architecture

```
User Upload → S3 Bucket → S3 Event → SQS Queue → EC2 Worker → OpenSearch
                                                       ↑
                                               IAM Role (Bedrock, Textract)

User Question → EC2 Flask API → Embed (Titan/Bedrock) → Search OpenSearch → Claude (Bedrock) → Answer
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| AWS CLI v2 | [Installation guide](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) |
| AWS credentials configured | `aws configure` or IAM role |
| Bash 4.x+ | Available on Linux/macOS |
| `jq` utility | `sudo apt install jq` or `brew install jq` |
| Sufficient IAM permissions | See [aws-setup-guide.md](aws-setup-guide.md) |

### Verify Prerequisites

```bash
# Check AWS CLI version
aws --version

# Check configured identity
aws sts get-caller-identity

# Check jq
jq --version
```

---

## Quick Start

```bash
# 1. Copy and configure environment variables
cp .env.example .env
# Edit .env with your values (TEAM_NAME is required)
source .env

# 2. Run scripts in order
cd scripts
bash 1-create-s3-bucket.sh
bash 2-create-sqs-queue.sh
bash 3-setup-s3-event.sh
bash 4-create-iam-role.sh
bash 5-setup-opensearch.sh
bash 6-launch-ec2.sh
```

> **Note:** OpenSearch domain creation (script 5) takes 10–15 minutes. EC2 bootstrap (script 6) takes 3–5 minutes.

---

## Execution Order

| Step | Script | Description | Duration |
|---|---|---|---|
| 1 | `scripts/1-create-s3-bucket.sh` | Create S3 bucket with encryption and versioning | ~30 sec |
| 2 | `scripts/2-create-sqs-queue.sh` | Create SQS queue with dead-letter queue | ~30 sec |
| 3 | `scripts/3-setup-s3-event.sh` | Wire S3 ObjectCreated events to SQS | ~30 sec |
| 4 | `scripts/4-create-iam-role.sh` | Create IAM role and policies for EC2 | ~1 min |
| 5 | `scripts/5-setup-opensearch.sh` | Deploy OpenSearch domain | ~15 min |
| 6 | `scripts/6-launch-ec2.sh` | Launch EC2 instance with user data | ~5 min |

---

## Directory Structure

```
infrastructure/
├── README.md                          # This file
├── aws-setup-guide.md                 # Detailed AWS setup instructions
├── .env.example                       # Environment variables template
├── scripts/
│   ├── 1-create-s3-bucket.sh         # S3 bucket creation
│   ├── 2-create-sqs-queue.sh         # SQS queue creation
│   ├── 3-setup-s3-event.sh           # S3 to SQS event wiring
│   ├── 4-create-iam-role.sh          # IAM role and policies
│   ├── 5-setup-opensearch.sh         # OpenSearch domain setup
│   ├── 6-launch-ec2.sh               # EC2 instance launch
│   └── cleanup.sh                     # Cleanup all resources
├── policies/
│   ├── ec2-trust-policy.json         # EC2 trust relationship
│   ├── s3-policy.json                # S3 permissions
│   ├── sqs-policy.json               # SQS permissions
│   ├── bedrock-policy.json           # Bedrock permissions
│   ├── opensearch-policy.json        # OpenSearch permissions
│   └── textract-policy.json          # Textract permissions
└── configs/
    ├── opensearch-config.json        # OpenSearch domain configuration
    └── ec2-user-data.sh              # EC2 initialization script
```

---

## Verification Steps

After running all scripts, verify your infrastructure:

```bash
# 1. Verify S3 bucket
aws s3 ls s3://rag-class-docs-${TEAM_NAME}

# 2. Verify SQS queue
aws sqs get-queue-attributes \
  --queue-url $(aws sqs get-queue-url --queue-name rag-class-docs-queue-${TEAM_NAME} --query QueueUrl --output text) \
  --attribute-names All

# 3. Verify IAM role
aws iam get-role --role-name rag-class-ec2-role-${TEAM_NAME}

# 4. Verify OpenSearch domain
aws opensearch describe-domain --domain-name rag-class-${TEAM_NAME} \
  --query 'DomainStatus.{Status:Processing,Endpoint:Endpoint}'

# 5. Verify EC2 instance
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=rag-class-ec2-${TEAM_NAME}" \
  --query 'Reservations[*].Instances[*].{ID:InstanceId,State:State.Name,IP:PublicIpAddress}'
```

### Stage 1 Completion Checklist

- [ ] S3 bucket `rag-class-docs-${TEAM_NAME}` exists and is accessible
- [ ] SQS queue `rag-class-docs-queue-${TEAM_NAME}` exists
- [ ] S3 sends ObjectCreated events to SQS
- [ ] IAM role `rag-class-ec2-role-${TEAM_NAME}` exists with correct policies
- [ ] OpenSearch domain `rag-class-${TEAM_NAME}` is Active
- [ ] EC2 instance is running with IAM profile attached
- [ ] EC2 instance is reachable via SSH

---

## Cost Estimates

| Service | Configuration | Estimated Cost |
|---|---|---|
| S3 | Standard storage, < 1 GB | ~$0.02/month |
| SQS | Standard queue, < 1M messages | Free tier |
| IAM | Role and policies | Free |
| OpenSearch | t3.small.search, 10 GB | ~$25/month |
| EC2 | t3.small, on-demand | ~$15/month |
| Bedrock (Titan) | Per API call | ~$0.10/1M tokens |
| Bedrock (Claude) | Per API call | ~$3–$15/1M tokens |

> **Total estimated cost:** ~$40–50/month for a development environment.
> Stop/terminate resources when not in use to minimize costs.

---

## Troubleshooting

### AWS CLI not configured
```bash
aws configure
# Enter: AWS Access Key ID, Secret Access Key, Region, Output format
```

### Bucket already exists in another account
S3 bucket names are globally unique. Change `TEAM_NAME` in `.env`.

### OpenSearch domain creation times out
OpenSearch domains take 10–15 minutes. Check status:
```bash
aws opensearch describe-domain --domain-name rag-class-${TEAM_NAME} \
  --query 'DomainStatus.Processing'
```

### EC2 instance fails to start
Check that the key pair exists:
```bash
aws ec2 describe-key-pairs --key-names ${EC2_KEY_NAME}
```

### Permission denied errors
Ensure your AWS user has `AdministratorAccess` or the specific permissions listed in [aws-setup-guide.md](aws-setup-guide.md).

---

## Cleanup

To remove all provisioned resources:

```bash
bash scripts/cleanup.sh
```

> ⚠️ **Warning:** This will permanently delete all data including documents in S3 and vectors in OpenSearch.
