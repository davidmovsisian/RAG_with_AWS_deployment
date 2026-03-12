# AWS Infrastructure Setup Guide

## Table of Contents
1. [Section 1: Prerequisites](#section-1-prerequisites)
2. [Section 3: Automated Setup](#section-3-automated-setup)
4. [Section 4: Manual Setup](#section-4-manual-setup)
5. [Section 5: Architecture Overview](#section-5-architecture-overview)
6. [Section 6: Troubleshooting](#section-6-troubleshooting)
7. [Section 7: Cleanup](#section-7-cleanup)
8. [Security Best Practices](#security-best-practices)
9. [Cost Optimization Tips](#cost-optimization-tips)

---

## Section 1: Prerequisites

### Required IAM Permissions for Setup User
The user or role running these scripts needs the following AWS managed policies, or equivalent custom permissions:
```
AmazonS3FullAccess
AmazonSQSFullAccess
AmazonOpenSearchServiceFullAccess
AmazonEC2FullAccess
IAMFullAccess
```

## Section 2: Automated Setup
The `worker.py` orchestration class runs all infrastructure scripts with a single command.
### Run Full Setup
```bash
cd infrastructure
python setup.py setup
```

### Check Status. 
```bash
python setup.py status
```

### Resume After Failure
```bash
# Resume from step 5 (e.g., if OpenSearch timed out)
python setup.py resume --step 5
```

### State File
Progress is saved to `.infrastructure_state.json`. This enables the worker to skip completed steps and resume from failures. The file is automatically created in the `infrastructure/` directory.
---

## Section 3: Manual Setup
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

## Section 5: Architecture Overview
### Component Descriptions
|    Component   |  Service   | Role |

| Document Store | Amazon S3  | Stores raw document files |
| Event Queue    | Amazon SQS | Decouples upload events from processing |
| Compute        | Amazon EC2 | Runs Flask API and document worker |
| Identity       | AWS IAM    | Grants EC2 permissions without credentials |
| Vector Store   | Amazon OpenSearch | Stores and searches document embeddings |
| Embeddings     | Google Gemini API (embedding-001) | Converts text chunks to vectors |
| LLM            | Google Gemini API (gemini-1.5-flash) | Generates answers from retrieved context |
| OCR            | Amazon Textract | Extracts text from PDFs and images |

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

## Section 7: Cleanup

```bash
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
