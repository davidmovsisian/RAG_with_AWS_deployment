# AWS Infrastructure Setup Guide

## Table of Contents
1. [Section 1: Prerequisites](#section-1-prerequisites)
2. [Section 2: Environment Setup](#section-2-environment-setup)
3. [Section 3: Automated Setup](#section-3-automated-setup)
4. [Section 4: Manual Setup](#section-4-manual-setup)
5. [Section 5: Architecture Overview](#section-5-architecture-overview)
6. [Section 6: Troubleshooting](#section-6-troubleshooting)
7. [Section 7: Cleanup](#section-7-cleanup)
8. [Security Best Practices](#security-best-practices)
9. [Cost Optimization Tips](#cost-optimization-tips)

---

## Section 1: Prerequisites

### AWS Account Requirements

- An active AWS account with billing enabled
- IAM user or role with sufficient permissions (see below)
- MFA enabled is recommended for security

### Required IAM Permissions for Setup User

The user or role running these scripts needs the following AWS managed policies, or equivalent custom permissions:

```
AmazonS3FullAccess
AmazonSQSFullAccess
AmazonOpenSearchServiceFullAccess
AmazonEC2FullAccess
IAMFullAccess
```

> **Least privilege note:** For production, scope permissions to specific resources and actions.

### AWS CLI Installation

```bash
# Linux (x86_64)
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# macOS (Homebrew)
brew install awscli

# Verify installation
aws --version
```

### AWS CLI Configuration

```bash
aws configure
# AWS Access Key ID [None]: <your-access-key-id>
# AWS Secret Access Key [None]: <your-secret-access-key>
# Default region name [None]: us-east-1
# Default output format [None]: json
```

Or, if using a named profile:

```bash
aws configure --profile my-profile
export AWS_PROFILE=my-profile
```

### Region Selection

Recommended regions for this project:

| Region | Code | Notes |
|---|---|---|
| US East (N. Virginia) | `us-east-1` | Recommended region |
| US West (Oregon) | `us-west-2` | Alternative with full service support |

> **Note:** Google Gemini API is accessed via an API key and is not region-specific.

### Install jq (for Bash scripts only)

`jq` is used in legacy Bash scripts for JSON parsing:

```bash
# Ubuntu/Debian
sudo apt-get install -y jq

# macOS
brew install jq

# Amazon Linux / RHEL
sudo yum install -y jq
```

### Install Python Dependencies

```bash
pip install -r infrastructure/requirements.txt
```

---

## Section 2: Environment Setup

Copy and edit the environment template:

```bash
cp infrastructure/.env.example infrastructure/.env
# Edit .env with your values
```

### Required Variables

| Variable | Example | Description |
|---|---|---|
| `AWS_REGION` | `us-east-1` | AWS region for all resources |
| `TEAM_NAME` | `team1` | Unique suffix for resource names |
| `PROJECT_NAME` | `rag-class` | Project prefix for resource names |
| `EC2_KEY_NAME` | `my-key-pair` | Existing EC2 key pair name for SSH |

### Resource Names (Auto-Generated)

Once `TEAM_NAME` and `PROJECT_NAME` are set:

```bash
export AWS_REGION="us-east-1"
export TEAM_NAME="your-team-name"
export PROJECT_NAME="rag-class"

export S3_BUCKET="${PROJECT_NAME}-docs-${TEAM_NAME}"
export SQS_QUEUE_NAME="${PROJECT_NAME}-docs-queue-${TEAM_NAME}"
export IAM_ROLE_NAME="${PROJECT_NAME}-ec2-role-${TEAM_NAME}"
export OPENSEARCH_DOMAIN="${PROJECT_NAME}-${TEAM_NAME}"
```

---

## Section 3: Automated Setup

The `worker.py` orchestration class runs all infrastructure scripts with a single command.

### Run Full Setup

```bash
cd infrastructure
python setup.py setup
```

Expected output per step:
```
============================================================
Step 1: Create S3 bucket
============================================================
Creating S3 bucket: rag-class-docs-team1 in us-east-1
Bucket rag-class-docs-team1 created.
...
Step 1 completed successfully.
```

### Check Status

```bash
python setup.py status
```

Output:
```
Infrastructure Setup Status
========================================
  Step 1: Create S3 bucket [COMPLETED] 2024-01-01T12:00:00
  Step 2: Create SQS queue [COMPLETED] 2024-01-01T12:01:00
  Step 3: Setup S3 event notification [COMPLETED] 2024-01-01T12:02:00
  Step 4: Create IAM role [COMPLETED] 2024-01-01T12:03:00
  Step 5: Setup OpenSearch domain [COMPLETED] 2024-01-01T12:18:00
  Step 6: Launch EC2 instance [PENDING]
```

### Resume After Failure

```bash
# Resume from step 5 (e.g., if OpenSearch timed out)
python setup.py resume --step 5
```

### State File

Progress is saved to `.infrastructure_state.json`. This enables the worker to skip completed steps and resume from failures. The file is automatically created in the `infrastructure/` directory.

---

## Section 4: Manual Setup

### Step-by-Step Script Execution

```bash
cd infrastructure/scripts

# Step 1: Create S3 bucket
python 1_create_s3_bucket.py

# Step 2: Create SQS queue
python 2_create_sqs_queue.py

# Step 3: Setup S3 event notification
python 3_setup_s3_event.py

# Step 4: Create IAM role
python 4_create_iam_role.py

# Step 5: Deploy OpenSearch domain (~15 min)
python 5_setup_opensearch.py

# Step 6: Launch EC2 instance
python 6_launch_ec2.py
```

### 4.1 S3 Bucket

#### Purpose

The S3 bucket stores uploaded documents. When a document is uploaded, S3 emits an `ObjectCreated` event to SQS.

#### Manual Console Instructions

1. Navigate to **S3 → Buckets → Create bucket**
2. **Bucket name:** `rag-class-docs-<your-team-name>`
3. **Block public access:** Keep all blocked
4. **Versioning:** Enable
5. **Encryption:** Enable SSE-S3 (AES-256)
6. Click **Create bucket**

#### Verification

```bash
aws s3 ls | grep rag-class-docs-${TEAM_NAME}
aws s3api get-bucket-versioning --bucket rag-class-docs-${TEAM_NAME}
aws s3api get-bucket-encryption --bucket rag-class-docs-${TEAM_NAME}
```

---

### 4.2 SQS Queue

#### Purpose

Receives S3 `ObjectCreated` events and holds them until the EC2 worker processes them.

#### Manual Console Instructions

1. Navigate to **SQS → Create queue**
2. **Name:** `rag-class-docs-queue-<your-team-name>`
3. **Visibility timeout:** 300 seconds
4. **Message retention period:** 345600 seconds (4 days)
5. **Receive message wait time:** 20 seconds
6. Click **Create queue**

#### Verification

```bash
QUEUE_URL=$(aws sqs get-queue-url --queue-name ${SQS_QUEUE_NAME} --query QueueUrl --output text)
aws sqs get-queue-attributes --queue-url "${QUEUE_URL}" --attribute-names All
```

---

### 4.3 S3 Event Notification

#### Purpose

Wires the S3 bucket to send `ObjectCreated:*` events to the SQS queue.

#### Manual Console Instructions

1. Navigate to **S3 → Your bucket → Properties → Event notifications**
2. Click **Create event notification**
3. **Name:** `rag-class-s3-event`
4. **Event types:** `s3:ObjectCreated:*`
5. **Destination:** SQS Queue → `rag-class-docs-queue-<your-team-name>`
6. Click **Save changes**

#### Test the Wiring

```bash
echo "test" | aws s3 cp - s3://rag-class-docs-${TEAM_NAME}/test.txt
QUEUE_URL=$(aws sqs get-queue-url --queue-name ${SQS_QUEUE_NAME} --query QueueUrl --output text)
aws sqs receive-message --queue-url "${QUEUE_URL}" --wait-time-seconds 5
```

---

### 4.4 IAM Role

#### Purpose

Grants EC2 permissions to access S3, SQS, OpenSearch, and Textract.

#### Permissions Summary

| Service | Actions | Resource |
|---|---|---|
| S3 | GetObject, PutObject, ListBucket | Specific bucket |
| SQS | ReceiveMessage, DeleteMessage, GetQueueAttributes | Specific queue |
| OpenSearch | ESHttpPost, ESHttpPut, ESHttpGet | Specific domain |
| Textract | DetectDocumentText, AnalyzeDocument | All (`*`) |

#### Verification

```bash
aws iam get-role --role-name ${IAM_ROLE_NAME}
aws iam list-role-policies --role-name ${IAM_ROLE_NAME}
aws iam get-instance-profile --instance-profile-name ${IAM_INSTANCE_PROFILE}
```

---

### 4.5 OpenSearch

#### Purpose

Stores document chunk embeddings as vectors for k-NN semantic search.

#### Manual Console Instructions

1. Navigate to **OpenSearch Service → Create domain**
2. **Name:** `rag-class-<your-team-name>`
3. **Instance type:** `t3.small.search`
4. **EBS storage:** 10 GB, gp3
5. **Encryption:** Enable at rest and node-to-node
6. **Access policy:** Allow EC2 IAM role ARN
7. Click **Create**

> ⏳ Domain creation takes 10–15 minutes.

#### Verification

```bash
aws opensearch describe-domain --domain-name ${OPENSEARCH_DOMAIN} \
  --query 'DomainStatus.{Status:Processing,Endpoint:Endpoint}'
```

---

### 4.6 EC2 Instance

#### Purpose

Runs the Flask API (port 5000) and SQS worker process.

#### Manual Console Instructions

1. Navigate to **EC2 → Launch Instance**
2. **Name:** `rag-class-ec2-<your-team-name>`
3. **AMI:** Ubuntu Server 22.04 LTS
4. **Instance type:** `t3.small`
5. **Key pair:** Select your existing key pair
6. **Security group:** SSH (22), HTTP (80), Custom TCP (5000)
7. **IAM instance profile:** `rag-class-ec2-profile-<your-team-name>`
8. **User data:** Paste contents of `configs/ec2-user-data.sh`
9. Click **Launch instance**

#### Verification

```bash
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=rag-class-ec2-${TEAM_NAME}" \
  --query 'Reservations[*].Instances[*].{ID:InstanceId,State:State.Name,IP:PublicIpAddress}'

# SSH into instance
ssh -i ~/.ssh/${EC2_KEY_NAME}.pem ubuntu@<public-ip>
sudo tail -f /var/log/user-data.log
```

---

## Section 5: Architecture Overview

```
User Upload → S3 Bucket → S3 Event → SQS Queue → EC2 Worker → OpenSearch
                                                       ↑
                                               IAM Role (Textract)

User Question → EC2 Flask API → Embed (Gemini) → Search OpenSearch → Gemini LLM → Answer
```

### Component Descriptions

| Component | Service | Role |
|---|---|---|
| Document Store | Amazon S3 | Stores raw document files |
| Event Queue | Amazon SQS | Decouples upload events from processing |
| Compute | Amazon EC2 | Runs Flask API and document worker |
| Identity | AWS IAM | Grants EC2 permissions without credentials |
| Vector Store | Amazon OpenSearch | Stores and searches document embeddings |
| Embeddings | Google Gemini API (embedding-001) | Converts text chunks to vectors |
| LLM | Google Gemini API (gemini-1.5-flash) | Generates answers from retrieved context |
| OCR | Amazon Textract | Extracts text from PDFs and images |

### Data Flow

1. User uploads document to S3
2. S3 sends `ObjectCreated` event to SQS
3. EC2 worker polls SQS, downloads document from S3
4. Worker uses Textract to extract text from document
5. Worker splits text into chunks, generates embeddings via Gemini API
6. Worker indexes chunks + embeddings in OpenSearch
7. User asks question via Flask API
8. API generates question embedding via Gemini API
9. API performs k-NN search in OpenSearch, retrieves top-k chunks
10. API sends chunks + question to Gemini LLM for answer generation
11. API returns answer to user

---

## Section 6: Troubleshooting

### IAM Permission Errors

**Symptom:** `AccessDeniedException` or `UnauthorizedOperation`

**Solution:**
1. Check your AWS identity: `aws sts get-caller-identity`
2. Ensure your user has `AdministratorAccess` or specific service permissions
3. Check the error message for the specific action being denied

### Resource Naming Conflicts

**Symptom:** `BucketAlreadyExists` or `EntityAlreadyExists`

**Solution:** Change `TEAM_NAME` in `.env` to something unique, then re-run.

### OpenSearch Timeout

**Symptom:** Script waits 30 minutes with no completion

**Solution:**
```bash
# Check domain status manually
aws opensearch describe-domain --domain-name ${OPENSEARCH_DOMAIN} \
  --query 'DomainStatus.Processing'

# Once it shows "false", resume:
python setup.py resume --step 5
```

### EC2 Connection Issues

**Symptom:** SSH connection refused or times out

**Solutions:**
1. Verify security group allows SSH from your IP
2. Wait 3-5 minutes for the instance to fully boot
3. Check user-data completed: `sudo cat /var/log/user-data.log`
4. Verify the correct key file: `ssh -i ~/.ssh/${EC2_KEY_NAME}.pem ubuntu@<ip>`

### Python / boto3 Errors

**Symptom:** `ModuleNotFoundError: No module named 'boto3'`

**Solution:**
```bash
pip install -r requirements.txt
```

---

## Section 7: Cleanup

```bash
# Interactive cleanup (confirms before deleting)
python setup.py cleanup

# Or directly
python scripts/cleanup.py
```

Resources are deleted in reverse order:
1. EC2 instance (waits for termination)
2. Security group
3. Instance profile (role detached first)
4. IAM role (policies removed first)
5. OpenSearch domain (waits for deletion)
6. S3 event notifications removed
7. SQS queue purged and deleted
8. S3 bucket emptied and deleted

> ⚠️ **Warning:** This permanently deletes all data including S3 documents and OpenSearch vectors.

---

## Security Best Practices

1. **Never embed AWS credentials** in code. Use IAM instance profiles.
2. **Restrict SSH access** to your IP address only (not `0.0.0.0/0`).
3. **Enable S3 versioning** to recover from accidental deletions.
4. **Enable CloudTrail** for audit logging of all API calls.
5. **Use VPC** for OpenSearch in production to restrict network access.
6. **Rotate IAM access keys** regularly if using long-term credentials.
7. **Enable GuardDuty** for threat detection.
8. **Use Systems Manager Session Manager** instead of SSH where possible.

---

## Cost Optimization Tips

1. **Stop EC2 instances** when not in use: `aws ec2 stop-instances --instance-ids <id>`
2. **Use t3.nano/micro** for the EC2 instance if only running tests.
3. **Delete OpenSearch domain** when done to avoid hourly charges.
4. **Set S3 lifecycle rules** to move old documents to Glacier storage.
5. **Monitor Gemini API costs** in Google AI Studio – API calls can add up.
6. **Use Reserved Instances** for EC2 if running long-term (up to 72% savings).
7. **Enable S3 Intelligent-Tiering** for automatic cost optimization.
