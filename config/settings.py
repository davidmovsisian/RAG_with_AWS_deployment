"""
Configuration settings for the RAG system.
Loads and validates environment variables.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # AWS Configuration
    aws_region: str = Field(default="us-east-1", env="AWS_REGION")
    aws_access_key_id: Optional[str] = Field(default=None, env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, env="AWS_SECRET_ACCESS_KEY")

    # S3 Configuration
    s3_bucket_name: str = Field(..., env="S3_BUCKET_NAME")
    s3_processed_prefix: str = Field(default="processed/", env="S3_PROCESSED_PREFIX")
    s3_failed_prefix: str = Field(default="failed/", env="S3_FAILED_PREFIX")

    # SQS Configuration
    sqs_queue_url: str = Field(..., env="SQS_QUEUE_URL")

    # OpenSearch Configuration
    opensearch_endpoint: str = Field(..., env="OPENSEARCH_ENDPOINT")
    opensearch_index_name: str = Field(default="rag-documents", env="OPENSEARCH_INDEX_NAME")
    opensearch_username: Optional[str] = Field(default=None, env="OPENSEARCH_USERNAME")
    opensearch_password: Optional[str] = Field(default=None, env="OPENSEARCH_PASSWORD")

    # Gemini Configuration
    gemini_api_key: str = Field(..., env="GEMINI_API_KEY")
    gemini_embedding_model: str = Field(
        default="models/embedding-001",
        env="GEMINI_EMBEDDING_MODEL"
    )
    gemini_llm_model: str = Field(
        default="gemini-1.5-flash",
        env="GEMINI_LLM_MODEL"
    )
    gemini_max_tokens: int = Field(default=4096, env="GEMINI_MAX_TOKENS")
    gemini_temperature: float = Field(default=0.7, env="GEMINI_TEMPERATURE")

    # Chunking Configuration
    chunk_size: int = Field(default=1000, env="CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, env="CHUNK_OVERLAP")
    max_chunk_size: int = Field(default=1500, env="MAX_CHUNK_SIZE")

    # API Configuration
    flask_env: str = Field(default="development", env="FLASK_ENV")
    flask_debug: bool = Field(default=False, env="FLASK_DEBUG")
    api_port: int = Field(default=5000, env="API_PORT")
    api_host: str = Field(default="0.0.0.0", env="API_HOST")

    # Worker Configuration
    worker_poll_interval: int = Field(default=5, env="WORKER_POLL_INTERVAL")
    worker_max_messages: int = Field(default=10, env="WORKER_MAX_MESSAGES")
    worker_visibility_timeout: int = Field(default=300, env="WORKER_VISIBILITY_TIMEOUT")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")

    # RAG Configuration
    retrieval_top_k: int = Field(default=5, env="RETRIEVAL_TOP_K")
    rerank_enabled: bool = Field(default=False, env="RERANK_ENABLED")
    rerank_top_k: int = Field(default=3, env="RERANK_TOP_K")

    @validator("chunk_overlap")
    def validate_chunk_overlap(cls, v, values):
        """Ensure chunk overlap is less than chunk size."""
        if "chunk_size" in values and v >= values["chunk_size"]:
            raise ValueError("chunk_overlap must be less than chunk_size")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
