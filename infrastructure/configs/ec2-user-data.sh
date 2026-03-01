#!/bin/bash
# =============================================================================
# EC2 User Data Script: ec2-user-data.sh
# Purpose: Initialize the EC2 instance for the RAG application on first boot.
#          Installs Docker Engine and Docker Compose for container deployment.
# This script runs as root via cloud-init on instance launch.
# All output is logged to /var/log/user-data.log
# =============================================================================

exec > >(tee -a /var/log/user-data.log) 2>&1
set -e

echo "=========================================="
echo "EC2 User Data Script Started"
echo "Time: $(date)"
echo "=========================================="

# -----------------------------------------------------------------------------
# 1. Set timezone to UTC
# -----------------------------------------------------------------------------
echo "[1/7] Setting timezone to UTC ..."
timedatectl set-timezone UTC
echo "Timezone set."

# -----------------------------------------------------------------------------
# 2. Update system packages
# -----------------------------------------------------------------------------
echo "[2/7] Updating system packages ..."
apt-get update -y
apt-get upgrade -y --no-install-recommends
echo "System packages updated."

# -----------------------------------------------------------------------------
# 3. Install system dependencies
# -----------------------------------------------------------------------------
echo "[3/7] Installing system dependencies ..."
apt-get install -y --no-install-recommends \
    curl \
    wget \
    git \
    unzip \
    jq \
    ca-certificates \
    gnupg \
    lsb-release
echo "System dependencies installed."

# -----------------------------------------------------------------------------
# 4. Install Docker Engine (official method for Ubuntu 22.04)
# -----------------------------------------------------------------------------
echo "[4/7] Installing Docker Engine ..."
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
    | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update -y
apt-get install -y --no-install-recommends \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin
echo "Docker $(docker --version) installed."

# -----------------------------------------------------------------------------
# 5. Configure Docker service and user
# -----------------------------------------------------------------------------
echo "[5/7] Configuring Docker service and user ..."
systemctl enable docker
systemctl start docker
usermod -aG docker ubuntu
echo "Docker service enabled and started. ubuntu user added to docker group."
echo "Group membership: $(groups ubuntu)"

# -----------------------------------------------------------------------------
# 6. Create application directory structure
# -----------------------------------------------------------------------------
echo "[6/7] Creating application directory structure ..."
APP_DIR="/home/ubuntu/rag-app"
mkdir -p "${APP_DIR}"
mkdir -p "${APP_DIR}/data"
mkdir -p "${APP_DIR}/logs"
chown -R ubuntu:ubuntu "${APP_DIR}"
echo "Application directories created at ${APP_DIR}."

# -----------------------------------------------------------------------------
# 7. Verify installations
# -----------------------------------------------------------------------------
echo "[7/7] Verifying installations ..."
docker --version
docker compose version
systemctl status docker --no-pager
echo "Verification complete."

echo "=========================================="
echo "EC2 User Data Script Completed"
echo "Time: $(date)"
echo "=========================================="
