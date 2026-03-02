# Educational Example: AWS Bedrock Knowledge Bases

> **⚠️ Educational / Comparison Example**
> This directory contains an optional example that demonstrates AWS Bedrock
> Knowledge Bases as a **managed** alternative to the custom RAG system built
> in this repository.  It is here purely for comparison and learning — the main
> project is the custom implementation in `src/`.

---

## Overview

AWS Bedrock Knowledge Bases is a fully managed RAG service.  You point it at
an S3 bucket and it automatically handles:

| What Bedrock KB does for you | Equivalent code in this repo |
|------------------------------|------------------------------|
| Document parsing | `src/worker/` |
| Text chunking | `src/utils/chunking.py` |
| Embedding generation | `src/utils/bedrock_client.py` |
| Vector storage in OpenSearch | `src/utils/opensearch_client.py` |
| Similarity search | `src/utils/opensearch_client.py` |
| Answer generation | `src/api/` |

The convenience comes at a price — both in dollars and in learning opportunity.

---

## Quick Start

### Prerequisites

- AWS account with Bedrock access enabled in your region
- AWS credentials configured (`aws configure` or environment variables)
- An S3 bucket containing your documents
- Python 3.9+ with boto3 installed

```bash
pip install -r requirements.txt
```

### Step-by-step workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                  Managed RAG with Bedrock KB                    │
│                                                                 │
│  1. setup_kb.py                                                 │
│     ├── Create IAM role (Bedrock trust policy)                  │
│     ├── Create OpenSearch Serverless collection                 │
│     ├── Create Knowledge Base (Titan embeddings)                │
│     └── Create S3 data source (FIXED_SIZE chunking)            │
│                                                                 │
│  2. Upload documents to S3                                      │
│     aws s3 cp ./docs/ s3://your-bucket/documents/ --recursive  │
│                                                                 │
│  3. sync_documents.py                                           │
│     └── Start ingestion job (parse → chunk → embed → index)    │
│                                                                 │
│  4. query_kb.py                                                 │
│     └── retrieve_and_generate() → answer + citations           │
│                                                                 │
│  5. cleanup_kb.py (when finished)                               │
│     └── Delete Knowledge Base (+ manual AOSS / IAM cleanup)    │
└─────────────────────────────────────────────────────────────────┘
```

### 1. Set up the Knowledge Base

Edit `setup_kb.py` and update `S3_BUCKET_NAME` to your bucket name, then run:

```bash
python setup_kb.py
```

Save the `Knowledge Base ID` and `Data Source ID` printed at the end.

### 2. Upload documents to S3

```bash
aws s3 cp ./my-documents/ s3://your-kb-documents-bucket/documents/ --recursive
```

### 3. Sync documents into the Knowledge Base

```bash
python sync_documents.py <KB_ID> <DATA_SOURCE_ID>
```

Example:

```bash
python sync_documents.py ABCDEF1234 GHIJKL5678
```

### 4. Query the Knowledge Base

```bash
python query_kb.py <KB_ID> "Your question here"
```

Example:

```bash
python query_kb.py ABCDEF1234 "How do I configure OpenSearch?"
```

**Example output:**

```
🤖 Querying Knowledge Base
Question: How do I configure OpenSearch?

💬 Answer:
To configure OpenSearch you need to ... [generated answer]

📚 Sources (2 citation(s)):

1. Source: s3://your-bucket/documents/opensearch-guide.pdf
   Content preview: OpenSearch configuration involves setting the cluster name...

2. Source: s3://your-bucket/documents/setup-guide.txt
   Content preview: The opensearch.yml file controls most cluster settings...
```

### 5. Clean up

```bash
python cleanup_kb.py <KB_ID>
```

Then manually delete the OpenSearch Serverless collection and IAM role via the
AWS Console to avoid ongoing charges.

---

## Side-by-side Code Comparison

### Querying — Bedrock KB (this example)

```python
# ~10 lines — the entire RAG pipeline is a single API call
response = bedrock_runtime.retrieve_and_generate(
    input={"text": question},
    retrieveAndGenerateConfiguration={
        "type": "KNOWLEDGE_BASE",
        "knowledgeBaseConfiguration": {
            "knowledgeBaseId": kb_id,
            "modelArn": MODEL_ARN,
            "retrievalConfiguration": {
                "vectorSearchConfiguration": {"numberOfResults": 5}
            },
        },
    },
)
answer = response["output"]["text"]
```

### Querying — Custom RAG system (this repo)

```python
# ~50 lines — but you understand and control every step
embedding = bedrock_client.get_embedding(question)          # 1. embed question
chunks = opensearch_client.similarity_search(embedding, k=5) # 2. vector search
context = "\n\n".join([c["text"] for c in chunks])          # 3. build context
prompt = build_prompt(question, context)                     # 4. format prompt
answer = bedrock_client.generate_text(prompt)               # 5. generate answer
sources = [c["metadata"]["source"] for c in chunks]         # 6. collect citations
```

---

## Cost Breakdown

| Resource | Approximate Cost |
|----------|-----------------|
| OpenSearch Serverless (minimum) | ~$700 / month |
| Bedrock Titan embeddings | $0.0001 per 1K tokens |
| Bedrock Claude 3 Sonnet queries | $0.003 / 1K input tokens |
| S3 storage | ~$0.023 per GB / month |

> **⚠️ Cost warning:** OpenSearch Serverless has a minimum charge of ~$700/month
> regardless of usage.  Only use this for production workloads that justify the
> cost.  Delete the collection when you are finished experimenting.

---

## Comparison: Bedrock KB vs Custom RAG System

| Feature | Bedrock KB | Custom RAG System (This Repo) |
|---------|------------|-------------------------------|
| Setup Time | ~15 minutes | Days |
| Lines of Code | ~200 | ~2,000 |
| Control | Limited | Full |
| Minimum Cost | ~$700/month | ~$100/month |
| Learning Value | Black box | Understand every component |
| Chunking Strategy | Fixed (configurable size) | Custom (any algorithm) |
| Embedding Model | Titan (fixed) | Any model |
| Vector Store | OpenSearch Serverless only | OpenSearch or any DB |
| Customizability | Low | High |
| Debugging | Limited | Full visibility |
| Suitable for Production | Yes (high traffic) | Yes (with tuning) |
| Suitable for Learning | No | ✅ Yes |

---

## When to Use Each Approach

### Use Bedrock Knowledge Bases when:
- You need a production system quickly and cost is not a concern
- Your team lacks ML/infrastructure expertise
- You need AWS-managed reliability and scaling
- You have high query volume that justifies the OpenSearch Serverless cost

### Use the Custom RAG System (this repo) when:
- **You are learning** — you want to understand how RAG works
- Cost is a priority (~$100/month vs ~$700/month)
- You need full control over chunking, embedding, and retrieval logic
- You want to experiment with different embedding models or vector stores
- You need to customise the pipeline for your specific use case

---

## Educational Value

Building a custom RAG system teaches you:

1. **Chunking strategies** — why chunk size and overlap matter for retrieval quality
2. **Embedding models** — how different models produce different vector spaces
3. **Vector search** — cosine similarity, HNSW indexing, approximate nearest neighbours
4. **Prompt engineering** — how context is structured to guide the LLM
5. **Pipeline debugging** — how to diagnose retrieval quality issues
6. **Cost optimisation** — choosing the right components for your budget

Bedrock Knowledge Bases hides all of this behind a single API call.  That is
convenient for production, but it is a "black box" that prevents you from
developing a deep understanding of the technology.

**Recommendation:** Build the custom system in this repo first.  Once you
understand all the components, you will be able to make informed decisions
about when a managed service like Bedrock KB is the right trade-off.

---

## Files in This Directory

| File | Purpose |
|------|---------|
| `setup_kb.py` | Create IAM role, OpenSearch collection, KB, and data source |
| `sync_documents.py` | Run an ingestion job to index documents from S3 |
| `query_kb.py` | Query the KB using `retrieve_and_generate()` |
| `cleanup_kb.py` | Delete the Knowledge Base (with confirmation) |
| `requirements.txt` | Python dependencies |
| `README.md` | This file |

---

*This example is part of the [RAG with AWS Deployment](../../README.md) educational project.*
