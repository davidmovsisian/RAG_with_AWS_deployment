#!/bin/bash
# =============================================================================
# EC2 User Data Script: ec2-user-data.sh
# Purpose: Initialize the EC2 instance for the RAG application on first boot.
#          Installs system packages, Python 3.11, and sets up the app directory.
# This script runs as root via cloud-init on instance launch.
# All output is logged to /var/log/user-data.log
# =============================================================================

exec > >(tee /var/log/user-data.log | logger -t user-data) 2>&1
set -e

echo "========================================"
echo " RAG System EC2 Initialization Started"
echo " $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "========================================"

# -----------------------------------------------------------------------------
# 1. Set timezone to UTC
# -----------------------------------------------------------------------------
echo "[1/9] Setting timezone to UTC ..."
timedatectl set-timezone UTC
echo "Timezone set."

# -----------------------------------------------------------------------------
# 2. Update system packages
# -----------------------------------------------------------------------------
echo "[2/9] Updating system packages ..."
apt-get update -y
apt-get upgrade -y --no-install-recommends
echo "System packages updated."

# -----------------------------------------------------------------------------
# 3. Install system dependencies
# -----------------------------------------------------------------------------
echo "[3/9] Installing system dependencies ..."
apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    wget \
    git \
    unzip \
    jq \
    ca-certificates \
    gnupg \
    lsb-release \
    software-properties-common \
    libssl-dev \
    libffi-dev \
    libpq-dev \
    ufw
echo "System dependencies installed."

# -----------------------------------------------------------------------------
# 4. Install Python 3.11
# -----------------------------------------------------------------------------
echo "[4/9] Installing Python 3.11 ..."
add-apt-repository ppa:deadsnakes/ppa -y
apt-get update -y
apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip

# Set Python 3.11 as default python3
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
update-alternatives --install /usr/bin/python python3 /usr/bin/python3.11 1

# Upgrade pip
python3.11 -m pip install --upgrade pip
echo "Python $(python3.11 --version) installed."

# -----------------------------------------------------------------------------
# 5. Install virtualenv
# -----------------------------------------------------------------------------
echo "[5/9] Installing virtualenv ..."
python3.11 -m pip install --upgrade virtualenv
echo "virtualenv installed."

# -----------------------------------------------------------------------------
# 6. Install AWS CLI v2
# -----------------------------------------------------------------------------
echo "[6/9] Installing AWS CLI v2 ..."
if ! command -v aws &>/dev/null; then
    curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
    unzip -q /tmp/awscliv2.zip -d /tmp
    /tmp/aws/install
    rm -rf /tmp/awscliv2.zip /tmp/aws
fi
echo "AWS CLI $(aws --version) installed."

# -----------------------------------------------------------------------------
# 7. Create application directory structure
# -----------------------------------------------------------------------------
echo "[7/9] Creating application directory structure ..."
APP_DIR="/opt/rag-app"
mkdir -p "${APP_DIR}"/{logs,uploads,scripts}
chown -R ubuntu:ubuntu "${APP_DIR}"

# Create Python virtual environment
su - ubuntu -c "python3.11 -m virtualenv ${APP_DIR}/venv"
echo "Application directories created at ${APP_DIR}."

# Create placeholder .env file for the app
cat > "${APP_DIR}/.env.example" <<'ENV_EOF'
# RAG Application Environment Variables
# Copy to .env and fill in your values

AWS_REGION=us-east-1
S3_BUCKET=rag-class-docs-<your-team-name>
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/<account>/<queue-name>
OS_HOST=https://<opensearch-endpoint>
OS_INDEX=rag-documents
CLAUDE_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
TITAN_EMBED_MODEL=amazon.titan-embed-text-v1
FLASK_PORT=5000
ENV_EOF
chown ubuntu:ubuntu "${APP_DIR}/.env.example"

# -----------------------------------------------------------------------------
# 8. Configure basic firewall (UFW)
# -----------------------------------------------------------------------------
echo "[8/9] Configuring UFW firewall ..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp   comment "SSH"
ufw allow 80/tcp   comment "HTTP"
ufw allow 5000/tcp comment "Flask API"
ufw --force enable
echo "Firewall configured."

# -----------------------------------------------------------------------------
# 9. Create systemd service placeholders
# -----------------------------------------------------------------------------
echo "[9/9] Creating systemd service placeholders ..."
SYSTEMD_DIR="/etc/systemd/system"

cat > "${SYSTEMD_DIR}/rag-api.service" <<'SERVICE_EOF'
[Unit]
Description=RAG Flask API Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/rag-app
EnvironmentFile=/opt/rag-app/.env
ExecStart=/opt/rag-app/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 2 app:app
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICE_EOF

cat > "${SYSTEMD_DIR}/rag-worker.service" <<'SERVICE_EOF'
[Unit]
Description=RAG SQS Worker Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/rag-app
EnvironmentFile=/opt/rag-app/.env
ExecStart=/opt/rag-app/venv/bin/python worker.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICE_EOF

systemctl daemon-reload
echo "Systemd service files created (not started – deploy your app code first)."

# -----------------------------------------------------------------------------
# Completion
# -----------------------------------------------------------------------------
echo ""
echo "========================================"
echo " Initialization Complete"
echo " $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. SSH into this instance: ssh -i ~/.ssh/<key>.pem ubuntu@$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
echo "  2. Clone your repo: cd /opt/rag-app && git clone <repo-url> ."
echo "  3. Install Python dependencies: source venv/bin/activate && pip install -r requirements.txt"
echo "  4. Create .env from .env.example and fill in values"
echo "  5. Start services: sudo systemctl enable --now rag-api rag-worker"
