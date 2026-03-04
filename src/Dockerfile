# Dockerfile for RAG Worker
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/rag_app

# Set working directory
WORKDIR /rag_app

# Copy requirements
COPY requirements.txt .

# Install requirements
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code 
COPY . .

# Run the worker using the direct file path
CMD ["python", "worker/run_worker.py"]