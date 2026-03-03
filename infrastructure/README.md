# AWS Infrastructure Setup for RAG System

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start (Automated)](#quick-start-automated)
4. [Quick Start (Manual)](#quick-start-manual)
5. [Commands](#commands)
6. [Execution Order](#execution-order)
7. [Directory Structure](#directory-structure)
8. [Verification Steps](#verification-steps)
9. [Cost Estimates](#cost-estimates)
10. [Troubleshooting](#troubleshooting)
11. [Windows Users](#windows-users)
12. [Cleanup](#cleanup)

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
                                               IAM Role (Textract)

User Question → EC2 Flask API → Embed (Gemini) → Search OpenSearch → Gemini LLM → Answer
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.8+ | [python.org](https://www.python.org/downloads/) |
| boto3 + python-dotenv | `pip install -r requirements.txt` |
| AWS CLI configured | `aws configure` or IAM role |
| IAM user with admin permissions | See [aws-setup-guide.md](aws-setup-guide.md) |

### Verify Prerequisites

```bash
# Check Python version
python --version

# Check AWS identity
aws sts get-caller-identity
```

---

## Quick Start (Automated)

```bash
# 1. Install Python dependencies
pip install -r infrastructure/requirements.txt

# 2. Copy and configure environment variables
cd infrastructure
cp .env.example .env
# Edit .env: set TEAM_NAME, AWS_REGION, EC2_KEY_NAME at minimum

# 3. Run automated setup
python setup.py setup
```

> **Note:** OpenSearch domain creation (step 5) takes 10–15 minutes. Total setup is ~20 minutes.

---

## Quick Start (Manual)

```bash
cd infrastructure
cp .env.example .env
# Edit .env with your values

cd scripts
python 1_create_s3_bucket.py
python 2_create_sqs_queue.py
python 3_setup_s3_event.py
python 4_create_iam_role.py
python 5_setup_opensearch.py
python 6_launch_ec2.py
```

---

## Commands

| Command | Description |
|---|---|
| `python setup.py setup` | Run all infrastructure steps in order |
| `python setup.py status` | Show completion status of each step |
| `python setup.py resume --step N` | Resume setup from step N |
| `python setup.py cleanup` | Interactively delete all resources |

---

## Execution Order

| Step | Script | Description | Duration |
|---|---|---|---|
| 1 | `scripts/1_create_s3_bucket.py` | Create S3 bucket with encryption and versioning | ~30 sec |
| 2 | `scripts/2_create_sqs_queue.py` | Create SQS queue | ~30 sec |
| 3 | `scripts/3_setup_s3_event.py` | Wire S3 ObjectCreated events to SQS | ~30 sec |
| 4 | `scripts/4_create_iam_role.py` | Create IAM role and policies for EC2 | ~1 min |
| 5 | `scripts/5_setup_opensearch.py` | Deploy OpenSearch domain | ~15 min |
| 6 | `scripts/6_launch_ec2.py` | Launch EC2 instance with user data | ~5 min |

---

## Directory Structure

```
infrastructure/
├── README.md                               # This file
├── aws-setup-guide.md                      # Detailed AWS setup instructions
├── .env.example                            # Environment variables template
├── requirements.txt                        # Python dependencies
├── worker.py                               # Orchestration worker class
├── setup.py                                # CLI interface
├── scripts/
│   ├── 1_create_s3_bucket.py              # S3 bucket creation
│   ├── 2_create_sqs_queue.py              # SQS queue creation
│   ├── 3_setup_s3_event.py                # S3 to SQS event wiring
│   ├── 4_create_iam_role.py               # IAM role and policies
│   ├── 5_setup_opensearch.py              # OpenSearch domain setup
│   ├── 6_launch_ec2.py                    # EC2 instance launch
│   ├── cleanup.py                         # Cleanup all resources (Python)
│   ├── 1-create-s3-bucket.sh              # S3 bucket creation (Bash)
│   ├── 2-create-sqs-queue.sh              # SQS queue creation (Bash)
│   ├── 3-setup-s3-event.sh                # S3 to SQS event wiring (Bash)
│   ├── 4-create-iam-role.sh               # IAM role and policies (Bash)
│   ├── 5-setup-opensearch.sh              # OpenSearch domain setup (Bash)
│   ├── 6-launch-ec2.sh                    # EC2 instance launch (Bash)
│   └── cleanup.sh                         # Cleanup all resources (Bash)
├── policies/
│   ├── ec2-trust-policy.json              # EC2 trust relationship
│   ├── iam-permissions-policy.json        # Combined permissions policy template
│   ├── s3-policy.json                     # S3 permissions
│   ├── sqs-policy.json                    # SQS permissions
│   ├── opensearch-policy.json             # OpenSearch permissions
│   └── textract-policy.json               # Textract permissions
└── configs/
    ├── opensearch-config.json             # OpenSearch domain configuration
    └── ec2-user-data.sh                   # EC2 initialization script
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
| Gemini API | Per API call | Free tier available |

> **Total estimated cost:** ~$40–50/month for a development environment.
> Stop/terminate resources when not in use to minimize costs.

---

## Troubleshooting

### AWS CLI not configured
```bash
aws configure
# Enter: AWS Access Key ID, Secret Access Key, Region, Output format
```

### boto3 / python-dotenv not installed
```bash
pip install -r infrastructure/requirements.txt
```

### Bucket already exists in another account
S3 bucket names are globally unique. Change `TEAM_NAME` in `.env`.

### OpenSearch domain creation times out
OpenSearch domains take 10–15 minutes. Resume after the domain is active:
```bash
python setup.py resume --step 5
```

### EC2 instance fails to start
Check that the key pair name in `.env` matches an existing key pair:
```bash
aws ec2 describe-key-pairs --key-names ${EC2_KEY_NAME}
```

### Permission denied errors
Ensure your AWS user has `AdministratorAccess` or the specific permissions listed in [aws-setup-guide.md](aws-setup-guide.md).

### Resume after failure
```bash
# Check what failed
python setup.py status

# Resume from a specific step
python setup.py resume --step 3
```

---

## Windows Users

The Python scripts work on Windows without any changes.

1. Install Python 3.8+ from [python.org](https://www.python.org/downloads/)
2. Verify installation: `python --version`
3. Install dependencies: `pip install -r requirements.txt`
4. Run setup using Command Prompt or Git Bash:
   ```
   python setup.py setup
   ```

---

## Cleanup

To remove all provisioned resources (Python):

```bash
python setup.py cleanup
```

Or using the standalone cleanup script:

```bash
python scripts/cleanup.py
```

Or using Bash (Linux/macOS):

```bash
bash scripts/cleanup.sh
```

> ⚠️ **Warning:** This will permanently delete all data including documents in S3 and vectors in OpenSearch.
