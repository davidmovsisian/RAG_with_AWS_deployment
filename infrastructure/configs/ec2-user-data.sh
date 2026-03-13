#!/bin/bash
exec > >(tee -a /var/log/user-data.log) 2>&1
set -e

echo "--- Script Started: $(date) ---"

# 1-3. System Prep & Dependencies
timedatectl set-timezone UTC
export DEBIAN_FRONTEND=noninteractive
apt-get update && apt-get upgrade -yq
apt-get install -yq curl git ca-certificates gnupg lsb-release

# 4. Install Docker (Consolidated)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list

apt-get update && apt-get install -yq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 5-6. Config & Directory Setup
systemctl enable --now docker
usermod -aG docker ubuntu

# mkdir -p /home/ubuntu/rag_app/{data,logs}
# chown -R ubuntu:ubuntu /home/ubuntu/rag_app

# 7. Final Verification
docker info && docker compose version
echo "--- Script Completed: $(date) ---"