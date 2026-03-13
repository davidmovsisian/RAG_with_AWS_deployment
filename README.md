# RAG with AWS Deployment

A Retrieval-Augmented Generation (RAG) application deployed on AWS, consisting of two independently scalable services:

- **API Service** — handles HTTP requests, queries OpenSearch, generates answers with Gemini
- **Worker Service** — polls SQS for document events, processes and indexes documents

## Deployment Architecture

```
┌─────────────────┐         ┌──────────────────┐
│   Flask API     │         │   SQS Worker     │
│  (rag-api)      │         │  (rag-worker)    │
└────────┬────────┘         └────────┬─────────┘
         │                           │
    ┌────▼────┐  ┌─────────┐    ┌────▼─────┐
    │   S3    │  │   SQS   │    │OpenSearch│
    └─────────┘  └─────────┘    └──────────┘
```

### API Service (`src/api/app.py`)
- Handles HTTP requests: upload, ask, list files, delete, health checks
- Queries OpenSearch for relevant document chunks (RAG)
- Generates answers using the Gemini API
- Uploads/deletes files in S3

### Worker Service (`src/worker_main.py`)
- Polls SQS for S3 `ObjectCreated` / `ObjectRemoved` events
- Reads documents from S3, chunks them, generates embeddings
- Indexes chunks into OpenSearch
- Runs as an independent process — can be scaled separately from the API

## Running Locally with Docker Compose

```bash
cp src/.env.example src/.env  # fill in your values
docker-compose -f src/docker-compose.yml up --build
```

To scale workers:

```bash
docker-compose -f src/docker-compose.yml up --build --scale worker=3
```

## Environment Variables

### API Service

| Variable | Description |
|---|---|
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `AWS_REGION` | AWS region (default: `us-east-1`) |
| `S3_BUCKET` | S3 bucket name for document storage |
| `GEMINI_API_KEY` | Google Gemini API key |
| `OPENSEARCH_HOST` | OpenSearch hostname |
| `OPENSEARCH_PORT` | OpenSearch port (default: `443`) |
| `GEMINI_POOL_SIZE` | Gemini client pool size (default: `5`) |

### Worker Service

All API variables, plus:

| Variable | Description |
|---|---|
| `SQS_QUEUE_URL` | URL of the SQS queue |
| `WORKER_POLL_INTERVAL` | Seconds to wait between polls (default: `5`) |
| `WORKER_MAX_MESSAGES` | Max messages per receive call (default: `10`) |
| `WORKER_VISIBILITY_TIMEOUT` | SQS visibility timeout in seconds (default: `300`) |

## Deploying to AWS ECS / Fargate

### API Task Definition
- Image: `<ecr-repo>/rag-api:latest`
- CPU: 512, Memory: 1024
- Port mapping: `5000`
- Auto-scaling: based on CPU utilisation and request count

### Worker Task Definition
- Image: `<ecr-repo>/rag-worker:latest`
- CPU: 1024, Memory: 2048
- No port mapping required
- Auto-scaling: based on `ApproximateNumberOfMessages` SQS metric

### Scaling Recommendations

- **API**: scale horizontally on CPU or ALB request count
- **Worker**: scale on `SQS:ApproximateNumberOfMessages` — add workers when queue depth grows, remove when empty
- Workers are stateless and safe to terminate mid-poll (SQS visibility timeout ensures re-delivery)
- Consider using Spot instances for workers to reduce cost

## Infrastructure Setup

Use the scripts in `infrastructure/` to provision the required AWS resources:

```bash
cd infrastructure
python setup.py
```

See [`infrastructure/aws-setup-guide.md`](infrastructure/aws-setup-guide.md) for detailed instructions.
