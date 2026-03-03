# RAG System with AWS Deployment - Project Plan

## Overview
This plan outlines the step-by-step development process for building a Flask-based RAG application using AWS services (OpenSearch, S3, SQS, EC2) and Google Gemini API with Gemini as the AI model.

---

## STAGE 1: AWS Infrastructure Setup
**Goal:** Set up all required AWS services and IAM permissions

### Tasks:
1. **S3 Bucket Configuration**
   - Create S3 bucket: `rag-class-docs-<team>`
   - Configure bucket for document uploads
   - Set up appropriate bucket policies

2. **SQS Queue Setup**
   - Create SQS queue: `rag-class-docs-queue-<team>`
   - Configure queue settings (visibility timeout, retention)

3. **OpenSearch Deployment**
   - Deploy OpenSearch Serverless domain
   - Configure k-NN index settings
   - Set up access policies

4. **IAM Role Configuration**
   - Create EC2 role with permissions for:
     - S3 (read/write)
     - SQS (receive/delete messages)
     - OpenSearch (index/search)
     - Textract (optional)

5. **EC2 Instance Setup**
   - Launch Ubuntu 22.04 instance
   - Attach IAM role
   - Configure security groups
   - Install Python 3.11+

6. **S3 → SQS Event Wiring**
   - Configure S3 event notification for ObjectCreated
   - Link to SQS queue

**Deliverables:**
- All AWS resources provisioned
- IAM roles configured
- EC2 instance ready

---

## STAGE 2: Project Repository Structure & Dependencies
**Goal:** Set up the codebase foundation

### Tasks:
1. **Create Repository Structure**
   ```
   ├── app.py                  # Flask API
   ├── worker.py               # SQS worker
   ├── opensearch_utils.py     # OpenSearch operations
   ├── gemini_client.py        # Gemini API interactions
   ├── chunking.py             # Text chunking logic
   ├── s3_utils.py             # S3 operations
   ├── requirements.txt        # Python dependencies
   ├── .env.example            # Environment template
   ├── scripts/
   │   ├── create_index.py     # OpenSearch index creation
   │   └── smoke_test.py       # Testing script
   ├── systemd/
   │   ├── rag-api.service     # API service config
   │   └── rag-worker.service  # Worker service config
   └── README.md
   ```

2. **Dependencies Setup (requirements.txt)**
   - flask
   - boto3
   - requests
   - opensearch-py
   - python-dotenv
   - gunicorn

3. **Environment Configuration (.env.example)**
   - AWS_REGION
   - S3_BUCKET
   - SQS_QUEUE_URL
   - OS_HOST
   - OS_INDEX
   - GEMINI_API_KEY
   - GEMINI_EMBEDDING_MODEL
   - GEMINI_LLM_MODEL

**Deliverables:**
- Repository structure created
- requirements.txt configured
- .env.example template

---

## STAGE 3: Utility Modules Development
**Goal:** Build reusable utility functions

### Tasks:
1. **gemini_client.py**
   - Function to generate embeddings using Gemini embedding-001 (768 dimensions)
   - Function to call Gemini LLM for chat/completions
   - Error handling and retries
   - Proper response parsing

2. **opensearch_utils.py**
   - Initialize OpenSearch client with authentication
   - Create k-NN index with proper mappings
   - Index document chunks with metadata
   - Search for similar vectors (cosine similarity)
   - Error handling and connection management

3. **chunking.py**
   - Text splitting logic (configurable chunk size/overlap)
   - Support for different chunking strategies
   - Metadata preservation (source, page number, etc.)
   - Handle edge cases (short documents, special characters)

4. **s3_utils.py**
   - Download objects from S3 by key
   - Handle different file types (txt, pdf, docx, etc.)
   - Stream large files efficiently
   - Error handling for missing objects

**Deliverables:**
- All utility modules implemented and tested
- Unit tests for critical functions

---

## STAGE 4: Worker Development
**Goal:** Build the background worker for document processing

### Tasks:
1. **SQS Polling Logic**
   - Implement long polling (WaitTimeSeconds=20)
   - Parse S3 event notification from SQS message body
   - Extract bucket name and object key
   - Delete message after successful processing
   - Handle malformed messages

2. **Document Processing Pipeline**
   - Download document from S3 using s3_utils
   - Extract text content:
     - Plain text: direct read
     - PDF/Images: optional Textract integration
   - Chunk text using chunking.py
   - Generate embeddings for each chunk using gemini_client
   - Index chunks into OpenSearch with metadata

3. **Error Handling & Logging**
   - Comprehensive error handling for each step
   - Structured logging (timestamp, level, message)
   - Retry logic for transient failures
   - Dead letter queue handling (optional)

**Deliverables:**
- worker.py fully functional
- Processes documents from S3 automatically
- Logs activities clearly

---

## STAGE 5: Flask API Development
**Goal:** Build the user-facing API

### Tasks:
1. **/health Endpoint** (GET)
   - Return 200 OK with service status
   - Check connectivity to OpenSearch
   - Check Gemini API availability
   - Return JSON: `{"status": "healthy", "services": {...}}`

2. **/ask Endpoint** (POST)
   - Accept JSON body: `{"question": "user question"}`
   - Generate embedding for the question
   - Retrieve top-k (e.g., 5) relevant chunks from OpenSearch
   - Build context prompt with retrieved chunks
   - Call Gemini LLM with prompt
   - Return JSON: `{"answer": "...", "sources": [...]}`
   - Handle errors gracefully (return appropriate status codes)

3. **Optional: /upload Endpoint** (POST)
   - Accept file upload
   - Upload to S3 bucket
   - Return upload confirmation
   - Trigger indexing via S3 event

**Deliverables:**
- Flask API with documented endpoints
- Request/response validation
- Error handling

---

## STAGE 6: Scripts & Testing
**Goal:** Create helper scripts and tests

### Tasks:
1. **scripts/create_index.py**
   - Script to initialize OpenSearch index
   - Configure k-NN settings (engine: nmslib, space_type: cosinesimil)
   - Set dimension based on Gemini embeddings (768)
   - Handle index recreation (delete if exists)
   - Verify index creation

2. **scripts/smoke_test.py**
   - Test 1: Upload test document to S3
   - Test 2: Verify document indexed in OpenSearch
   - Test 3: Query /ask endpoint with test question
   - Test 4: Verify grounded answer
   - End-to-end validation

**Deliverables:**
- Working scripts for setup and testing
- Documentation on how to run scripts

---

## STAGE 7: Deployment & Systemd Configuration
**Goal:** Deploy to EC2 with production-ready setup

### Tasks:
1. **Systemd Service Files**
   - Create `systemd/rag-api.service`:
     - ExecStart with Gunicorn
     - Environment variables
     - Auto-restart on failure
     - Logging to journal
   - Create `systemd/rag-worker.service`:
     - ExecStart with Python worker.py
     - Environment variables
     - Auto-restart on failure
     - Logging to journal

2. **Deployment Steps**
   - Clone repository to EC2
   - Install Python 3.11+ and dependencies
   - Set environment variables (create .env file)
   - Copy systemd files to /etc/systemd/system/
   - Enable services: `systemctl enable rag-api rag-worker`
   - Start services: `systemctl start rag-api rag-worker`
   - Verify services running: `systemctl status`

3. **Testing**
   - Test /health endpoint: `curl http://localhost:5000/health`
   - Upload test document to S3
   - Wait for indexing
   - Test /ask endpoint: `curl -X POST http://localhost:5000/ask -d '{"question": "test"}'`

**Deliverables:**
- Services running on EC2
- Systemd configuration
- Deployment documentation

---

## STAGE 8: UI/UX Layer (Optional Enhancement)
**Goal:** Create a simple frontend interface

### Tasks:
1. **Frontend Development**
   - Create simple HTML page (index.html)
   - CSS styling for clean UI
   - JavaScript for API calls
   - File upload interface
   - Question input box
   - Display area for answers with sources

2. **Integration**
   - Serve static files from Flask
   - AJAX calls to /upload and /ask
   - Loading indicators
   - Error message display
   - Response formatting

**Deliverables:**
- Simple, functional web UI
- Integrated with Flask API

---

## STAGE 9: Optional AI Services Integration
**Goal:** Add advanced AI capabilities

### Tasks:
1. **Amazon Comprehend** (Optional)
   - Extract entities from documents
   - Perform sentiment analysis
   - Enhance metadata

2. **Amazon Translate** (Optional)
   - Detect language of question
   - Translate to English for processing
   - Translate answer back to user's language

3. **Amazon Polly** (Optional)
   - Convert text answers to speech
   - Provide audio playback option in UI

**Deliverables:**
- Enhanced capabilities (choose 1+)
- Documentation of integration

---

## STAGE 10: Stretch Goals & Optimization
**Goal:** Enhance system performance and features

### Tasks:
1. **Reranking**
   - Implement cross-encoder reranking after vector search
   - Use Gemini or custom model
   - Improve answer relevance

2. **Feedback Loop**
   - Add thumbs up/down to UI
   - Store feedback in DynamoDB
   - Analyze feedback for improvements

3. **Deduplication**
   - Hash chunks to prevent duplicates
   - Check before indexing

4. **Caching**
   - Cache embeddings for frequent queries
   - Use ElastiCache or in-memory cache
   - Set TTL appropriately

5. **Batch Embedding**
   - Process multiple chunks in single Gemini API call
   - Reduce API calls and latency

**Deliverables:**
- Performance improvements
- Feature enhancements
- Documentation

---

## High-Level Architecture Diagram

```
User Upload → S3 Bucket → S3 Event → SQS Queue → EC2 Worker
                                                      ↓
                                            Download from S3
                                                      ↓
                                            Extract text (Textract optional)
                                                      ↓
                                            Chunk text
                                                      ↓
                                            Embed chunks (Gemini)
                                                      ↓
                                            Index into OpenSearch

User Question → Flask /ask → Embed question (Gemini) → Search OpenSearch
                                                      ↓
                                            Retrieve top-k chunks
                                                      ↓
                                            Build prompt with context
                                                      ↓
                                            Call Gemini LLM
                                                      ↓
                                            Return grounded answer
```

---

## Troubleshooting Guide

### Common Issues:
1. **IAM Permission Errors**
   - Verify EC2 role has all required permissions
   - Check trust relationships

2. **Dimension Mismatch**
   - Ensure OpenSearch index dimension matches Gemini output (768)

3. **SQS Message Parsing**
   - S3 event format: nested JSON structure
   - Parse correctly: `message['Records'][0]['s3']`

4. **Textract Throttling**
   - Implement exponential backoff
   - Consider batch processing

5. **OpenSearch Connectivity**
   - Check security groups
   - Verify VPC configuration
   - Ensure proper authentication

---

## Evaluation Rubric

- ✅ **Bootstraps correctly**: All dependencies install, services start
- ✅ **Indexing works**: Documents uploaded to S3 are indexed in OpenSearch
- ✅ **OpenSearch works**: k-NN search returns relevant chunks
- ✅ **Gemini answers grounded**: Responses based on retrieved context
- ✅ **Optional service**: At least one additional AWS AI service integrated

---

## Development Approach

**We will develop this project STEP BY STEP:**
1. Each stage will be completed in order
2. Each stage will have its own PR for review
3. Testing will be performed after each stage
4. No stage will begin until the previous is complete and approved
5. Documentation will be updated continuously

---

## References
- Google Gemini API Documentation
- OpenSearch Documentation
- Flask Documentation
- Boto3 Documentation
- Original project requirements: `Second project.md`

---

**Note:** This is a planning document. Implementation will follow in subsequent PRs, stage by stage.
