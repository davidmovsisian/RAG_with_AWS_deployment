# Dockerfile for RAG Worker
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/rag_app

# Set working directory
WORKDIR /rag_app

# Install system dependencies (if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install requirements
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code 
COPY . .

# Copy Gunicorn configuration
# COPY gunicorn.conf.py .

EXPOSE 5000

# Use Gunicorn instead of Flask dev server
CMD ["gunicorn", "--config", "gunicorn.conf.py", "api.app:app"]