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
│  ┌──────────────────────────────────────────┐  │
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
   │   S3   │          │  OpenSearch │  │ Gemini API   │
   │ Bucket │◄─────┐   │   Domain    │  │ (Embedding & │
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
7. Each chunk is embedded using **Gemini Embedding API**
8. Chunks + embeddings are indexed to **OpenSearch**
9. Frontend polls until document is fully indexed

#### Query Flow:
1. User submits question via web interface
2. API Worker generates question embedding using **Gemini API**
3. OpenSearch performs KNN vector similarity search
4. Top-k most relevant chunks are retrieved
5. Context + question sent to **Gemini LLM**
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
- Generates embeddings via Gemini API
- Indexes to OpenSearch with metadata

**Key Files:**
- `sqs_worker.py` - Message polling and processing
- `document_processor.py` - Chunking and indexing logic

### 3. Utility Modules (`src/utils/`)
- `s3_client.py` - S3 operations (upload, download, list, delete)
- `opensearch_client.py` - OpenSearch indexing and search
- `gemini_client.py` - Gemini API for embeddings and LLM
- `chunking.py` - Text chunking with overlap
- `pdf_extractor.py` - PDF text extraction

### 4. Infrastructure Scripts (`infrastructure/`)
Automated AWS resource provisioning:
1. `1_create_s3_bucket.py` - S3 bucket with versioning
2. `2_create_sqs_queue.py` - SQS queue with S3 permissions
3. `3_setup_s3_event.py` - S3 event notifications to SQS
4. `4_create_iam_role.py` - EC2 IAM role with permissions
5. `5_setup_opensearch.py` - OpenSearch domain (10-15 min)
6. `6_launch_ec2.py` - EC2 instance with setup scripts

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| **Frontend** | HTML, CSS, Vanilla JavaScript |
| **Backend API** | Python Flask |
| **Background Worker** | Python (SQS polling) |
| **Vector Database** | AWS OpenSearch Service (KNN) |
| **Storage** | AWS S3 |
| **Message Queue** | AWS SQS |
| **Compute** | AWS EC2 (t3.small) |
| **Embeddings** | Google Gemini Embedding API (768d) |
| **LLM** | Google Gemini 2.5 Flash |
| **PDF Processing** | PyPDF2 |

---

## 📦 Prerequisites

### Local Development
- Python 3.9+
- AWS Account with appropriate permissions
- Google Gemini API Key ([Get one here](https://ai.google.dev/))

### AWS Permissions Required
- S3 (full access)
- SQS (full access)
- OpenSearch (full access)
- EC2 (full access)
- IAM (role creation)

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

# Gemini API Configuration
GEMINI_API_KEY=your-gemini-api-key
GEMINI_EMBEDDING_MODEL=models/embedding-001
GEMINI_LLM_MODEL=gemini-2.0-flash-exp
EMBEDDING_DIMENSION=768
GEMINI_POOL_SIZE=5

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
- OpenSearch domain (~15 minutes)
- EC2 instance

**Note:** OpenSearch domain creation takes 10-15 minutes. Monitor progress:

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
| `OPENSEARCH_ENDPOINT` | OpenSearch domain endpoint | Auto-generated |
| `GEMINI_API_KEY` | Google Gemini API key | Required |
| `EMBEDDING_DIMENSION` | Embedding vector dimension | `768` |
| `GEMINI_POOL_SIZE` | Connection pool size | `5` |
| `WORKER_POLL_INTERVAL` | SQS polling interval (seconds) | `5` |

---

## 🐛 Troubleshooting

### OpenSearch Connection Issues

```bash
# Check OpenSearch endpoint
aws opensearch describe-domain --domain-name rag-class-your-team-name

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
│   │   ├── gemini_client.py
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
