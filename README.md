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

This RAG system follows a **multi-process architecture** with two standalone services running on a single EC2 instance:

1. **API Worker** (Foreground Service)
   - Flask-based REST API
   - Handles user requests (upload, query, file management)
   - Interacts with: S3, OpenSearch, Bedrock (for query embeddings and LLM)

2. **SQS Worker** (Background Service)
   - Autonomous document processor
   - Polls SQS queue for document events
   - Performs the complete indexing pipeline
   - Interacts with: SQS, S3, Bedrock (for embeddings), OpenSearch (for indexing)

Both services run concurrently on the same EC2 instance and share access to AWS resources.

### High-Level Architecture

```
┌─────────────┐
│   Browser   │
│  (Frontend) │
└──────┬──────┘
       │ HTTP
       ▼
┌─────────────────────────────────────────────────────────────┐
│                    EC2 Instance                             │
│                                                             │
│  ┌────────────────────────────────────────────────────┐   │
│  │         API Worker (Flask Application)             │   │
│  │  ┌──────────────────────────────────────────────┐  │   │
│  │  │  Flask API                                    │  │   │
│  │  │  - Upload endpoint                            │  │   │
│  │  │  - Ask endpoint                               │  │   │
│  │  │  - File management                            │  │   │
│  │  │  - Document status checking                   │  │   │
│  │  └────┬─────────────────────┬──────────────┬─────┘  │   │
│  └───────┼─────────────────────┼──────────────┼────────┘   │
│          │                     │              │            │
│          │                     │              │            │
│  ┌───────┼─────────────────────┼──────────────┼────────┐   │
│  │       │    SQS Worker       │              │        │   │
│  │       │  (Background Process)              │        │   │
│  │  ┌────▼────────────────────────────────────▼─────┐  │   │
│  │  │  Document Processor                          │  │   │
│  │  │  - Polls SQS messages                        │  │   │
│  │  │  - Downloads from S3                         │  │   │
│  │  │  - Extracts text (PDF/TXT)                   │  │   │
│  │  │  - Chunks documents                          │  │   │
│  │  │  - Generates embeddings (Bedrock)            │  │   │
│  │  │  - Indexes to OpenSearch                     │  │   │
│  │  └──────┬────────────────────────┬──────────────┘  │   │
│  └─────────┼────────────────────────┼─────────────────┘   │
└────────────┼────────────────────────┼─────────────────────┘
             │                        │
             ▼                        ▼
   ┌──────────────────┐    ┌──────────────────┐
   │   AWS Bedrock    │    │   OpenSearch     │
   │  - Titan Embed   │    │   Serverless     │
   │  - Claude 3.5    │    │  (Vector Store)  │
   └──────────────────┘    └──────────────────┘
             ▲                        ▲
             │                        │
             └────────────────────────┘
                      Shared Access

        ┌────────┐          ┌────────┐
        │   S3   │◄─────────│  SQS   │
        │ Bucket │  Event   │ Queue  │
        └────┬───┘          └───▲────┘
             │                  │
             └──────────────────┘
              Both Workers Access
```

### Data Flow

#### Upload Flow:
1. User uploads document (`.txt` or `.pdf`) via web interface
2. API Worker receives file and uploads to **S3 bucket**
3. S3 triggers notification → **SQS queue**
4. **SQS Worker polls queue** and receives message
5. Worker **downloads file from S3**
6. Document is **chunked** (500 chars with 50 char overlap)
7. **SQS Worker generates embeddings** for each chunk using **AWS Bedrock Titan**
8. **SQS Worker indexes** chunks + embeddings to **OpenSearch**
9. Frontend polls until document is fully indexed

#### Query Flow:
1. User submits question via web interface
2. **API Worker generates question embedding** using **AWS Bedrock Titan**
3. **API Worker queries OpenSearch** to perform KNN vector similarity search
4. Top-k most relevant chunks are retrieved
5. Context + question sent to **AWS Bedrock Claude 3.5 Haiku**
6. AI-generated answer returned to user with source citations

---

## 🔧 System Components

### 1. API Worker (`src/api/`)
**Flask-based REST API** (runs as foreground service on EC2)

Handles:
- Document upload to S3
- Question answering with RAG using **AWS Bedrock**
- File listing and management
- Document status checking via OpenSearch
- Health monitoring

**Key Files:**
- `app.py` - Flask application with API endpoints
- `api_worker.py` - Business logic for Q&A
- `static/` - Frontend HTML/CSS/JS

**AWS Services Used:**
- S3 (upload, list, delete)
- OpenSearch (search queries)
- Bedrock (query embeddings, LLM responses)

### 2. SQS Worker (`src/sqs_worker_main.py`)
**Background document processor** (runs as background service on EC2)

Operates autonomously to:
- Poll SQS queue for S3 event notifications
- Download documents from S3
- Extract text from PDF/TXT files (with AWS Textract for multi-page PDFs)
- Chunk documents into manageable pieces
- Generate embeddings via **AWS Bedrock Titan**
- Index chunks + embeddings + metadata to OpenSearch

**Key Files:**
- `sqs_worker.py` - Message polling and processing

**AWS Services Used:**
- SQS (receive messages, delete messages)
- S3 (download files)
- Bedrock (generate embeddings)
- OpenSearch (index documents)
- Textract (optional, for complex PDFs)

### 3. Utility Modules (`src/utils/`)
- `s3_client.py` - S3 operations (upload, download, list, delete)
- `opensearch_client.py` - OpenSearch indexing and search
- `bedrock_client.py` - AWS Bedrock client for embeddings and LLM inference
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
| **Embeddings** | AWS Bedrock - Titan Embeddings (amazon.titan-embed-text-v1, 1536d) |
| **LLM** | AWS Bedrock - Claude 3.5 Haiku (us.anthropic.claude-3-5-haiku-20241022-v1:0) |
| **PDF Processing** | PyPDF2 |

---

## 📦 Prerequisites
### AWS Permissions Required
- S3 (full access)
- SQS (full access)
- OpenSearch (full access)
- EC2 (full access)
- IAM (role creation)
- Bedrock (model invocation)

### AWS Bedrock Access
- AWS Bedrock enabled in your account
- Model access granted for:
  - `amazon.titan-embed-text-v1` (Embeddings)
  - `us.anthropic.claude-3-5-haiku-20241022-v1:0` (LLM)

To enable model access:
```bash
# Via AWS Console: Bedrock → Model access → Manage model access
# Or check current access:
aws bedrock list-foundation-models --region us-east-1 --query 'modelSummaries[?contains(modelId, `titan-embed`) || contains(modelId, `claude`)].{ModelId:modelId,Status:modelLifecycle.status}'
```

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

# AWS Bedrock Configuration
EMBEDDING_MODEL=amazon.titan-embed-text-v1
LLM_MODEL=us.anthropic.claude-3-5-haiku-20241022-v1:0
EMBEDDING_DIMENSION=1536
MAX_TOKENS=1000
TEMPERATURE=0.7

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

**Both services must run concurrently in separate terminals**

#### Terminal 1 - Start API Worker (Foreground Service)

```bash
cd src
python -m api.app
```

Access at: `http://localhost:5000`

#### Terminal 2 - Start SQS Worker (Background Service)

```bash
cd src
python sqs_worker_main.py
```

**Note:** Both services must be running for the system to function. API Worker handles user requests, while SQS Worker processes documents in the background.

### Option 2: AWS Deployment

On EC2, both services run as **systemd services** that start automatically:

```bash
# SSH to EC2 instance
ssh -i your-key.pem ec2-user@your-ec2-ip

# Check both services are running
sudo systemctl status api-worker
sudo systemctl status sqs-worker

# View real-time logs
sudo journalctl -u api-worker -f    # API Worker logs
sudo journalctl -u sqs-worker -f    # SQS Worker logs

# Restart services if needed
sudo systemctl restart api-worker
sudo systemctl restart sqs-worker
```

Both services run concurrently on the same EC2 instance.

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
| `TEMPERATURE` | LLM response temperature | `0.7` |
| `WORKER_POLL_INTERVAL` | SQS polling interval (seconds) | `5` |

---

## 🐛 Troubleshooting

### Bedrock Access Issues

**Symptom:** Errors like "Access Denied" or "Model not found" when processing documents or queries

**Solution:**

```bash
# 1. Check Bedrock model access in your AWS account
aws bedrock list-foundation-models --region us-east-1 \
  --query 'modelSummaries[?contains(modelId, `titan-embed`) || contains(modelId, `claude`)].[modelId,modelLifecycle.status]' \
  --output table

# 2. Verify IAM role has Bedrock permissions
aws iam get-role-policy \
  --role-name rag-class-ec2-role-your-team-name \
  --policy-name rag-class-ec2-policy-your-team-name

# 3. Test Bedrock access from EC2
aws bedrock invoke-model \
  --model-id amazon.titan-embed-text-v1 \
  --body '{"inputText":"test"}' \
  --cli-binary-format raw-in-base64-out \
  output.json
```

**Note:** You must request model access through AWS Bedrock console before using models. This is a one-time setup per AWS account.

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
│       ├── 2_create_sqs_queue.py
│       ├── 3_setup_s3_event.py
│       ├── 4_create_iam_role.py
│       ├── 5_setup_opensearch.py
│       └── 6_launch_ec2.py
├── requirements.txt
├── .env
└── README.md
```
