# RAG-based Document Q&A System on AWS

A production-ready Retrieval-Augmented Generation (RAG) system deployed on AWS that enables users to upload documents and ask questions about them using AI-powered semantic search and natural language generation.

## 📋 Table of Contents

- [Architecture Overview](#architecture-overview)
- [System Components](#system-components)
- [Technology Stack](#technology-stack)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
- [Running the Application](#running-the-application)
- [Usage Guide](#usage-guide)
- [Infrastructure Management](#infrastructure-management)
- [Environment Variables](#environment-variables)
- [Troubleshooting](#troubleshooting)

---

## Architecture Overview

This RAG system follows a microservices architecture with two main workers: **API Worker** and **SQS Worker**, orchestrated through AWS services.

### High-Level Architecture

```
┌─────────────┐
│   Browser   │
│  (Frontend) │
└──────┬──────┘
       │ HTTP
       ▼
┌─────────────────────────────────────────────────┐
│            EC2 Instance (API Worker)            │
│  ┌──────────────────────────────────────────┐   │
│  │  Flask API                                │  │
│  │  - Upload endpoint                        │  │
│  │  - Ask endpoint                           │  │
│  │  - File management                        │  │
│  │  - Document status checking               │  │
│  └────┬─────────────────────┬────────────┬───┘  │
│       │                     │            │      │
└───────┼─────────────────────┼────────────┼──────┘
        │                     │            │
        ▼                     ▼            ▼
   ┌────────┐          ┌─────────────┐  ┌──────────────┐
   │   S3   │          │  OpenSearch │  │ Bedrock API  │
   │ Bucket │◄─────┐   │  Collection │  │ (Embedding & │
   └────┬───┘      │   └─────────────┘  │     LLM)     │
        │          │                    └──────────────┘
        │ Event    │
        ▼          │
   ┌────────┐     │
   │  SQS   │     │
   │ Queue  │     │
   └────┬───┘     │
        │         │
        ▼         │
┌─────────────────┴───────────────────────────────┐
│         EC2 Instance (SQS Worker)               │
│  ┌──────────────────────────────────────────┐  │
│  │  Document Processor                      │  │
│  │  - Polls SQS messages                    │  │
│  │  - Downloads from S3                     │  │
│  │  - Chunks documents                      │  │
│  │  - Generates embeddings                  │  │
│  │  - Indexes to OpenSearch                 ��  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### Data Flow

#### Upload Flow:
1. User uploads document (`.txt` or `.pdf`) via web interface
2. API Worker receives file and uploads to **S3 bucket**
3. S3 triggers notification → **SQS queue**
4. SQS Worker polls queue and receives message
5. Worker downloads file from S3
6. Document is chunked (500 chars with 50 char overlap)
7. Each chunk is embedded using **AWS Bedrock-> Embedding model**
8. Chunks + embeddings are indexed to **OpenSearch serverless**
9. Frontend polls until document is fully indexed

#### Query Flow:
1. User submits question via web interface
2. API Worker generates question embedding using **AWS Bedrock **
3. OpenSearch performs KNN vector similarity search
4. Top-k most relevant chunks are retrieved
5. Context + question sent to **Bedrock -> LLM**
6. AI-generated answer returned to user with source citations

---

## 🔧 System Components

### 1. API Worker (`src/api/`)
Flask-based REST API that handles:
- Document upload to S3
- Question answering with RAG
- File listing and management
- Document status checking
- Health monitoring

**Key Files:**
- `app.py` - Flask application with API endpoints
- `api_worker.py` - Business logic for Q&A
- `static/` - Frontend HTML/CSS/JS

### 2. SQS Worker (`src/sqs_worker_main.py`)
Background processor that:
- Polls SQS queue for document events
- Extracts text from PDF/TXT files
- Chunks documents into manageable pieces
- Generates embeddings via AWS Bedrock
- Indexes to OpenSearch with metadata

**Key Files:**
- `sqs_worker.py` - Message polling and processing

### 3. Utility Modules (`src/utils/`)
- `s3_client.py` - S3 operations (upload, download, list, delete)
- `opensearch_client.py` - OpenSearch indexing and search
- `bedrock_client.py` - Bedrock API for embeddings and LLM
- `chunking.py` - Text chunking with overlap


### 4. Infrastructure Scripts (`infrastructure/`)
Automated AWS resource provisioning:
1. `1_create_s3_bucket.py` - S3 bucket with versioning
2. `2_create_sqs_queue.py` - SQS queue with S3 permissions
3. `3_setup_s3_event.py` - S3 event notifications to SQS
4. `4_create_iam_role.py` - EC2 IAM role with permissions
5. `5_setup_opensearch.py` - OpenSearch serverless collection 
6. `6_launch_ec2.py` - EC2 instance with setup scripts

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| **Frontend** | HTML, CSS, Vanilla JavaScript |
| **Backend API** | Python Flask/Gunicorn |
| **Background Worker** | Python (SQS polling) |
| **Vector Database** | AWS OpenSearch Serverless (VECTORSEARCH) |
| **Storage** | AWS S3 |
| **Message Queue** | AWS SQS |
| **Compute** | AWS EC2 (t3.small) |
| **Embeddings** | amazon.titan-embed-text-v1 |
| **LLM** | us.anthropic.claude-3-5-haiku-20241022-v1:0 |
| **PDF Processing** | PyPDF2 |

---

## 📦 Prerequisites
### AWS Permissions Required
- S3 (full access)
- SQS (full access)
- OpenSearch (full access)
- EC2 (full access)
- IAM (role creation)
- **AWS Bedrock** (InvokeModel permissions for foundation models)
- AWS Bedrock access enabled in your AWS account
- Bedrock model access granted for Titan Embeddings and Claude models

---

## 🚀 Installation & Setup

### Step 1: Clone Repository

```bash
git clone https://github.com/davidmovsisian/RAG_with_AWS_deployment.git
cd RAG_with_AWS_deployment
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment

Create a `.env` file in the root directory:

```bash
# AWS Configuration
AWS_REGION=us-east-1
TEAM_NAME=your-team-name
PROJECT_NAME=rag-class

# S3 Configuration
S3_BUCKET=rag-class-docs-your-team-name

# SQS Configuration
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/ACCOUNT_ID/rag-class-docs-queue-your-team-name

# OpenSearch Configuration
OPENSEARCH_ENDPOINT=https://your-opensearch-domain.us-east-1.es.amazonaws.com
OPENSEARCH_INDEX_NAME=rag-documents

# Bedrock Configuration
EMBEDDING_MODEL=amazon.titan-embed-text-v1
LLM_MODEL=us.anthropic.claude-3-5-haiku-20241022-v1:0
MAX_TOKENS=4096
TEMPERATURE=0.2
EMBEDDING_DIMENSION=1536

# Flask Configuration
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# Worker Configuration
WORKER_POLL_INTERVAL=5
WORKER_MAX_MESSAGES=10
WORKER_VISIBILITY_TIMEOUT=300
```

### Step 4: Provision AWS Infrastructure

```bash
cd infrastructure
python setup.py setup --env ../.env
```

This will create:
- S3 bucket
- SQS queue
- S3 event notifications
- IAM role for EC2
- OpenSearch collection 
- EC2 instance


```bash
python setup.py status
```

---

## 🎯 Running the Application

### Option 1: Local Development

#### Terminal 1 - Start API Worker

```bash
cd src
python -m api.app
```

Access at: `http://localhost:5000`

#### Terminal 2 - Start SQS Worker

```bash
cd src
python sqs_worker_main.py
```

### Option 2: AWS Deployment

The application automatically starts on EC2 instances using systemd services:

```bash
# SSH to EC2 instance
ssh -i your-key.pem ec2-user@your-ec2-ip

# Check service status
sudo systemctl status api-worker
sudo systemctl status sqs-worker

# View logs
sudo journalctl -u api-worker -f
sudo journalctl -u sqs-worker -f
```

---

## 📖 Usage Guide

### 1. Upload Documents

1. Navigate to the web interface
2. Click **Choose Files** and select `.txt` or `.pdf` files
3. Click **Upload**
4. Wait for status: "Processing... (X/Y files ready)"
5. When complete: "All X file(s) are ready!"

### 2. Ask Questions

1. Type your question in the input box
2. Optionally adjust `top_k` (number of context chunks: 1-5)
3. Click **Send** or press Enter
4. View AI-generated answer with source citations

### 3. Manage Files

- View uploaded files in tabs above upload section
- Click **×** button to delete a file
- Deletion removes from S3 and OpenSearch

---

## 🔄 Infrastructure Management

### Check Infrastructure Status

```bash
cd infrastructure
python setup.py status --env ../.env
```

### Resume from Specific Step

If setup fails at a step:

```bash
python setup.py resume --step 5 --env ../.env
```

### Cleanup All Resources

```bash
python setup.py cleanup --env ../.env
```

**Warning:** This will delete all AWS resources created by the system.

---

## 🌍 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_REGION` | AWS region for resources | `us-east-1` |
| `TEAM_NAME` | Unique identifier for resources | Required |
| `S3_BUCKET` | S3 bucket name | `{PROJECT_NAME}-docs-{TEAM_NAME}` |
| `SQS_QUEUE_URL` | Full SQS queue URL | Auto-generated |
| `OPENSEARCH_ENDPOINT` | OpenSearch collection endpoint | Auto-generated |
| `EMBEDDING_MODEL` | AWS Bedrock embedding model ID | `amazon.titan-embed-text-v1` |
| `LLM_MODEL` | AWS Bedrock LLM model ID | `us.anthropic.claude-3-5-haiku-20241022-v1:0` |
| `EMBEDDING_DIMENSION` | Embedding vector dimension | `1536` |
| `MAX_TOKENS` | Maximum tokens for LLM response | `1000` |
| `TEMPERATURE` | LLM temperature (0-1) | `0.7` |
| `WORKER_POLL_INTERVAL` | SQS polling interval (seconds) | `5` |

---

## 🐛 Troubleshooting

### OpenSearch Connection Issues

```bash
# Check OpenSearch endpoint
aws opensearchserverless batch-get-collection --names rag-class-your-team-name

# Verify data access policy
aws opensearchserverless get-access-policy --name rag-class-your-team-name-access --type data

# Verify IAM role has permissions
aws iam get-role --role-name rag-class-ec2-role-your-team-name
```

### SQS Worker Not Processing

```bash
# Check SQS queue for messages
aws sqs get-queue-attributes --queue-url YOUR_QUEUE_URL --attribute-names All

# Verify S3 event notification
aws s3api get-bucket-notification-configuration --bucket YOUR_BUCKET_NAME
```

### Document Not Appearing in Search

- Check if document is indexed: `POST /check-files-ready` with filename
- View OpenSearch index: Login to OpenSearch Dashboard
- Check SQS worker logs for processing errors

### Bedrock Model Access Issues

```bash
# Check if Bedrock models are available in your region
aws bedrock list-foundation-models --region us-east-1

# Verify IAM role has Bedrock permissions
aws iam get-role-policy --role-name rag-class-ec2-role-your-team-name --policy-name rag-class-ec2-policy-your-team-name
```

**Note:** If you get "Access Denied" errors, you may need to request model access through the AWS Bedrock console.

### API Worker Crashes

```bash
# Check logs on EC2
sudo journalctl -u api-worker -n 100 --no-pager

# Restart service
sudo systemctl restart api-worker
```

---

## 📝 Project Structure

```
RAG_with_AWS_deployment/
├── src/
│   ├── api/
│   │   ├── app.py                 # Flask API application
│   │   ├── static/                # Frontend files
│   │   │   ├── index.html
│   │   │   ├── css/style.css
│   │   │   └── js/script.js
│   ├── worker/
│   │   ├── api_worker.py          # Q&A business logic
│   │   ├── sqs_worker.py          # SQS message processor
│   │   └── document_processor.py  # Document indexing logic
│   ├── utils/
│   │   ├── s3_client.py
│   │   ├── opensearch_client.py
│   │   ├── bedrock_client.py
│   │   ├── chunking.py
│   │   └── pdf_extractor.py
│   └── sqs_worker_main.py         # SQS worker entry point
├── infrastructure/
│   ├── setup.py                   # Infrastructure orchestrator
│   └── scripts/
│       ├── 1_create_s3_bucket.py
│       ���── 2_create_sqs_queue.py
│       ├── 3_setup_s3_event.py
│       ├── 4_create_iam_role.py
│       ├── 5_setup_opensearch.py
│       └── 6_launch_ec2.py
├── requirements.txt
├── .env
└── README.md
