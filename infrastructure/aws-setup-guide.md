# AWS Infrastructure Setup Guide

## Table of Contents
1. [Section 1: Prerequisites](#section-1-prerequisites)
2. [Section 2: Environment Variables](#section-2-environment-variables)
3. [Section 3: Step-by-Step Instructions](#section-3-step-by-step-instructions)
   - [S3 Bucket](#31-s3-bucket)
   - [SQS Queue](#32-sqs-queue)
   - [S3 Event Notification](#33-s3-event-notification)
   - [IAM Role](#34-iam-role)
   - [OpenSearch](#35-opensearch)
   - [EC2 Instance](#36-ec2-instance)
4. [Security Best Practices](#security-best-practices)
5. [Cost Optimization Tips](#cost-optimization-tips)

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
AWSBedrockFullAccess
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
| US East (N. Virginia) | `us-east-1` | Best Bedrock model availability |
| US West (Oregon) | `us-west-2` | Alternative with full service support |

> **Important:** Amazon Bedrock (Claude 3, Titan) has limited regional availability. Check the [Bedrock documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/bedrock-regions.html) before selecting a region.

### Install jq

`jq` is used in scripts for JSON parsing:

```bash
# Ubuntu/Debian
sudo apt-get install -y jq

# macOS
brew install jq

# Amazon Linux / RHEL
sudo yum install -y jq
```

---

## Section 2: Environment Variables

Copy and edit the environment template:

```bash
cp infrastructure/.env.example infrastructure/.env
# Edit .env with your values
source infrastructure/.env
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

## Section 3: Step-by-Step Instructions

### 3.1 S3 Bucket

#### Purpose and Role

The S3 bucket stores uploaded documents (PDFs, text files, Word documents). When a new document is uploaded, S3 emits an `ObjectCreated` event to SQS, triggering the document processing pipeline.

#### Manual Console Instructions

1. Navigate to **S3 → Buckets → Create bucket**
2. **Bucket name:** `rag-class-docs-<your-team-name>`
3. **Region:** Select your region (e.g., `us-east-1`)
4. **Block public access:** Keep all blocked (default)
5. **Versioning:** Enable
6. **Encryption:** Enable SSE-S3 (AES-256)
7. Click **Create bucket**

#### Automated Script

```bash
source infrastructure/.env
bash infrastructure/scripts/1-create-s3-bucket.sh
```

#### Verification

```bash
# Check bucket exists
aws s3 ls | grep rag-class-docs-${TEAM_NAME}

# Check versioning
aws s3api get-bucket-versioning --bucket rag-class-docs-${TEAM_NAME}

# Check encryption
aws s3api get-bucket-encryption --bucket rag-class-docs-${TEAM_NAME}
```

#### Expected Output

```
{
    "Status": "Enabled"
}
```

---

### 3.2 SQS Queue

#### Purpose and Role

The SQS queue receives `ObjectCreated` notifications from S3 and holds them until the EC2 worker processes them. A dead-letter queue (DLQ) catches messages that fail to process multiple times.

#### Manual Console Instructions

1. Navigate to **SQS → Create queue**
2. **Type:** Standard
3. **Name:** `rag-class-docs-queue-<your-team-name>`
4. **Visibility timeout:** 300 seconds
5. **Message retention period:** 345600 seconds (4 days)
6. **Receive message wait time:** 20 seconds (long polling)
7. Under **Dead-letter queue:** Create and attach a DLQ with max receives = 3
8. Click **Create queue**

After creation, note the Queue ARN for use in the S3 event configuration.

#### Automated Script

```bash
bash infrastructure/scripts/2-create-sqs-queue.sh
```

#### Verification

```bash
QUEUE_URL=$(aws sqs get-queue-url \
  --queue-name ${SQS_QUEUE_NAME} \
  --query QueueUrl --output text)

aws sqs get-queue-attributes \
  --queue-url "${QUEUE_URL}" \
  --attribute-names All
```

#### Expected Output

```json
{
    "Attributes": {
        "VisibilityTimeout": "300",
        "MessageRetentionPeriod": "345600",
        "ReceiveMessageWaitTimeSeconds": "20"
    }
}
```

---

### 3.3 S3 Event Notification

#### Purpose and Role

This wires the S3 bucket to automatically send `ObjectCreated:*` events to the SQS queue. Every document uploaded to S3 will trigger a message in the queue.

#### Manual Console Instructions

1. Navigate to **S3 → Your bucket → Properties → Event notifications**
2. Click **Create event notification**
3. **Name:** `rag-class-s3-event`
4. **Event types:** Check `s3:ObjectCreated:*`
5. **Destination:** SQS Queue → Select `rag-class-docs-queue-<your-team-name>`
6. Click **Save changes**

> **Note:** The SQS queue policy must allow `sqs:SendMessage` from the S3 bucket ARN. The script handles this automatically.

#### Automated Script

```bash
bash infrastructure/scripts/3-setup-s3-event.sh
```

#### Verification

```bash
# Check notification configuration on bucket
aws s3api get-bucket-notification-configuration \
  --bucket rag-class-docs-${TEAM_NAME}
```

#### Test the Wiring

```bash
# Upload a test file
echo "test document" | aws s3 cp - s3://rag-class-docs-${TEAM_NAME}/test.txt

# Check SQS for the message
QUEUE_URL=$(aws sqs get-queue-url --queue-name ${SQS_QUEUE_NAME} --query QueueUrl --output text)
aws sqs receive-message --queue-url "${QUEUE_URL}" --wait-time-seconds 5
```

---

### 3.4 IAM Role

#### Purpose and Role

The IAM role grants the EC2 instance permission to interact with all required AWS services without embedding credentials in the code.

#### Permissions Summary

| Service | Actions | Resource |
|---|---|---|
| S3 | GetObject, PutObject, DeleteObject | Specific bucket |
| SQS | ReceiveMessage, DeleteMessage, GetQueueAttributes | Specific queue |
| Bedrock | InvokeModel | Claude and Titan model ARNs |
| OpenSearch | ESHttpPost, ESHttpPut, ESHttpGet, ESHttpDelete | Specific domain |
| Textract | DetectDocumentText, AnalyzeDocument | All (`*`) |

#### Manual Console Instructions

1. Navigate to **IAM → Roles → Create role**
2. **Trusted entity:** AWS service → EC2
3. Skip attaching managed policies (use custom policy below)
4. **Role name:** `rag-class-ec2-role-<your-team-name>`
5. After creation, attach a custom inline policy with permissions from `policies/` directory
6. Navigate to **IAM → Roles → Your role → Instance Profile**
7. Create an instance profile with the same name

#### Automated Script

```bash
bash infrastructure/scripts/4-create-iam-role.sh
```

#### Verification

```bash
# Check role exists
aws iam get-role --role-name ${IAM_ROLE_NAME}

# List attached policies
aws iam list-role-policies --role-name ${IAM_ROLE_NAME}

# Check instance profile
aws iam get-instance-profile --instance-profile-name ${IAM_ROLE_NAME}
```

---

### 3.5 OpenSearch

#### Purpose and Role

OpenSearch stores document chunk embeddings as vectors. When the worker processes a document, it generates embeddings and indexes them here. The Flask API queries OpenSearch using k-NN search to retrieve relevant chunks for a given question.

#### Options

**Option A: OpenSearch Serverless (Recommended for development)**
- No server management
- Pay per use
- Automatically scales
- Cost: ~$0.24/OCU-hour

**Option B: Managed OpenSearch Domain**
- More control and predictable costs
- `t3.small.search` for development (~$25/month)
- Requires managing updates and patches

#### Manual Console Instructions (Managed Domain)

1. Navigate to **OpenSearch Service → Create domain**
2. **Name:** `rag-class-<your-team-name>`
3. **Deployment type:** Development and testing
4. **Engine version:** OpenSearch 2.x (latest)
5. **Instance type:** `t3.small.search`
6. **Number of nodes:** 1
7. **EBS storage:** 10 GB, gp3
8. **Encryption:** Enable at rest and node-to-node
9. **Access policy:** Allow access from EC2 IAM role ARN
10. Click **Create**

> ⏳ Domain creation takes 10–15 minutes.

#### Automated Script

```bash
bash infrastructure/scripts/5-setup-opensearch.sh
```

#### Verification

```bash
aws opensearch describe-domain \
  --domain-name ${OPENSEARCH_DOMAIN} \
  --query 'DomainStatus.{Status:Processing,Endpoint:Endpoint,Version:EngineVersion}'
```

#### Expected Output

```json
{
    "Status": false,
    "Endpoint": "search-rag-class-team1-xxxxxx.us-east-1.es.amazonaws.com",
    "Version": "OpenSearch_2.11"
}
```

---

### 3.6 EC2 Instance

#### Purpose and Role

The EC2 instance runs two processes:
- **Flask API** (`app.py`) – serves HTTP requests on port 5000
- **SQS Worker** (`worker.py`) – polls SQS and processes documents

#### Manual Console Instructions

1. Navigate to **EC2 → Launch Instance**
2. **Name:** `rag-class-ec2-<your-team-name>`
3. **AMI:** Ubuntu Server 22.04 LTS
4. **Instance type:** `t3.small`
5. **Key pair:** Select your existing key pair
6. **Security group (new):**
   - Inbound: SSH (22) from your IP
   - Inbound: Custom TCP (5000) from Anywhere
   - Outbound: All traffic
7. **IAM instance profile:** Select `rag-class-ec2-role-<your-team-name>`
8. **User data:** Paste contents of `configs/ec2-user-data.sh`
9. Click **Launch instance**

#### Automated Script

```bash
bash infrastructure/scripts/6-launch-ec2.sh
```

#### Verification

```bash
# Check instance state
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=rag-class-ec2-${TEAM_NAME}" \
  --query 'Reservations[*].Instances[*].{ID:InstanceId,State:State.Name,IP:PublicIpAddress}'

# SSH into instance (once running)
ssh -i ~/.ssh/${EC2_KEY_NAME}.pem ubuntu@<public-ip>

# Check user-data log
sudo tail -f /var/log/user-data.log
```

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
5. **Monitor Bedrock costs** in AWS Cost Explorer – Claude calls can add up.
6. **Use Reserved Instances** for EC2 if running long-term (up to 72% savings).
7. **Enable S3 Intelligent-Tiering** for automatic cost optimization.
