"""
Gunicorn configuration for RAG Application running in Docker container on AWS EC2.
"""

import os
import multiprocessing

# =============================================================================
# Server Socket
# =============================================================================
# Bind to all interfaces inside container (0.0.0.0)
# Port is mapped by Docker: container:5000 -> host:5000
bind = "0.0.0.0:5000"
backlog = 2048

# =============================================================================
# Worker Processes
# =============================================================================
# For Docker: Use available CPUs within container limits
# Default: (2 x CPUs) + 1
# Can be overridden with GUNICORN_WORKERS env var
workers = int(os.getenv('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))

# Worker class: 'sync' or 'gthread'
# For I/O-bound RAG workloads (API calls), use 'gthread' with threads
worker_class = os.getenv('GUNICORN_WORKER_CLASS', 'gthread')

# Threads per worker (only for 'gthread' worker class)
# Total concurrency = workers * threads
# Example: 2 workers * 2 threads = 4 concurrent requests
threads = int(os.getenv('GUNICORN_THREADS', '2'))

# =============================================================================
# Worker Lifecycle
# =============================================================================
# Max requests before worker restart (prevents memory leaks)
max_requests = int(os.getenv('GUNICORN_MAX_REQUESTS', '1000'))
max_requests_jitter = int(os.getenv('GUNICORN_MAX_REQUESTS_JITTER', '50'))

# Timeout for long-running requests (Gemini API can be slow)
timeout = int(os.getenv('GUNICORN_TIMEOUT', '120'))
graceful_timeout = int(os.getenv('GUNICORN_GRACEFUL_TIMEOUT', '30'))
keepalive = int(os.getenv('GUNICORN_KEEPALIVE', '5'))

# =============================================================================
# Logging
# =============================================================================
# Log to stdout/stderr (captured by Docker)
accesslog = '-'
errorlog = '-'
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')

# Access log format with response time
access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s µs'
)

# =============================================================================
# Process Naming
# =============================================================================
proc_name = 'rag-app-gunicorn'

# =============================================================================
# Server Mechanics
# =============================================================================
# Preload app for faster worker startup
preload_app = False  # Set to False to avoid issues with RagWorker initialization

# Worker temporary directory (use /tmp in container)
worker_tmp_dir = '/dev/shm'  # Use shared memory for better performance

# =============================================================================
# Server Hooks
# =============================================================================
def on_starting(server):
    """Called when master process starts."""
    server.log.info("=" * 60)
    server.log.info("RAG Application Starting in Docker Container")
    server.log.info("=" * 60)
    server.log.info(f"Workers: {workers}")
    server.log.info(f"Worker Class: {worker_class}")
    server.log.info(f"Threads per Worker: {threads}")
    server.log.info(f"Total Concurrency: {workers * threads}")
    server.log.info(f"Binding to: {bind}")
    server.log.info("=" * 60)


def when_ready(server):
    """Called after server is ready."""
    server.log.info("✅ Server is ready. Spawning workers")


def post_worker_init(worker):
    """Called after worker initializes the application."""
    worker.log.info(f"✅ Worker {worker.pid} initialized")


def worker_exit(server, worker):
    """Called when a worker exits."""
    server.log.info(f"Worker {worker.pid} exited")


def on_exit(server):
    """Called when master process exits."""
    server.log.info("=" * 60)
    server.log.info("RAG Application shutting down")
    server.log.info("=" * 60)