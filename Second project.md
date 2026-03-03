# Second Project: RAG Implementation

This project is your chance to bring **Retrieval-Augmented Generation (RAG)** to life in a practical way. You’ll build a Flask application that connects to AWS services like Bedrock, OpenSearch, and S3, and use Claude as your AI model. 

The best part is that you’re free to choose **any topic you’re passionate about**—from history, sports, or movies, to finance or healthcare—so the project feels like your own. Along the way, you’ll also design a simple **UI/UX** layer for your app, because it’s not just about making the backend work, but also about creating a product that’s easy and enjoyable to use. For your dataset, you can grab free, ready-to-use material from **Kaggle**, which offers thousands of datasets to experiment with.

---

### Tech Stack
* **Flask API**: Python 3.11+
* **Google Gemini API**: 
    * Gemini LLM (chat/completions)
    * Gemini Embeddings (text embeddings, 768 dimensions)
* **OpenSearch**: Managed domain as the vector store (k‑NN)
* **S3**: Document drop‑box (students upload files here)
* **SQS**: Event fan‑out from S3 to EC2 worker
* **Textract (optional)**: To extract text from PDFs/images
* **EC2**: Hosting the app + worker (Gunicorn + systemd)

---



## 0) High‑Level Flow
1.  **Upload**: `[User uploads file]` → S3 bucket → S3 Event → SQS Queue → EC2 Worker
2.  **EC2 Worker Ingestion**:
    * Downloads object from S3.
    * (Optional) Uses Textract to extract text.
    * Chunks → Embeds (Gemini) → Indexes chunks into OpenSearch k‑NN index.
3.  **User Query**:
    * `User question` → Flask `/ask` → Retrieves top‑k chunks from OpenSearch.
    * Builds prompt → Calls Gemini LLM → Returns grounded answer.

---

## 1) Minimal AWS Setup (one-time)
* **S3**: `rag-class-docs-<team>` bucket
* **SQS**: `rag-class-docs-queue-<team>`
* **OpenSearch**: Serverless or managed domain
* **IAM**: EC2 role with S3, SQS, OpenSearch, and Textract permissions
* **EC2**: Ubuntu 22.04 with Python 3.11, Flask app + worker

## 2) Project Repo Structure
```text
├── app.py              # Flask API
├── worker.py           # SQS worker
├── opensearch_utils.py # OpenSearch logic
├── gemini_client.py    # Gemini API logic
├── chunking.py         # Text processing
├── s3_utils.py         # S3 interaction
├── requirements.txt    # Dependencies
├── scripts/            # Deployment scripts
└── systemd/            # Service configuration