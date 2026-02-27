#!/bin/bash
# =============================================================================
# Script: 6-launch-ec2.sh
# Purpose: Launch an EC2 instance with the IAM profile, security group, and
#          user-data initialization script for the RAG application.
# Usage:   source ../.env && bash 6-launch-ec2.sh
# Prerequisites:
#   - Scripts 1-5 must have been run
#   - AWS CLI configured with EC2 permissions
#   - Environment variables: AWS_REGION, TEAM_NAME, PROJECT_NAME, EC2_KEY_NAME
#   - Optional: EC2_INSTANCE_TYPE, EC2_AMI_ID
# =============================================================================

set -e

# -----------------------------------------------------------------------------
# Color output helpers
# -----------------------------------------------------------------------------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# -----------------------------------------------------------------------------
# Validate required environment variables
# -----------------------------------------------------------------------------
: "${AWS_REGION:?Environment variable AWS_REGION is required}"
: "${TEAM_NAME:?Environment variable TEAM_NAME is required}"
: "${EC2_KEY_NAME:?Environment variable EC2_KEY_NAME is required (name of existing EC2 key pair)}"
: "${PROJECT_NAME:=rag-class}"
: "${EC2_INSTANCE_TYPE:=t3.small}"

INSTANCE_NAME="${PROJECT_NAME}-ec2-${TEAM_NAME}"
ROLE_NAME="${PROJECT_NAME}-ec2-role-${TEAM_NAME}"
SG_NAME="${PROJECT_NAME}-sg-${TEAM_NAME}"

info "=== EC2 Instance Launch ==="
info "Instance name  : ${INSTANCE_NAME}"
info "Instance type  : ${EC2_INSTANCE_TYPE}"
info "Key pair       : ${EC2_KEY_NAME}"
info "Region         : ${AWS_REGION}"

# -----------------------------------------------------------------------------
# Resolve AMI ID (use provided or look up latest Ubuntu 22.04 LTS)
# -----------------------------------------------------------------------------
if [[ -z "${EC2_AMI_ID}" ]]; then
    info "Looking up latest Ubuntu 22.04 LTS AMI for ${AWS_REGION} ..."
    EC2_AMI_ID=$(aws ec2 describe-images \
        --owners 099720109477 \
        --filters \
            "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-*" \
            "Name=state,Values=available" \
        --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
        --output text)
    info "Found AMI: ${EC2_AMI_ID}"
else
    info "Using provided AMI: ${EC2_AMI_ID}"
fi

# -----------------------------------------------------------------------------
# Get caller's public IP for SSH security group rule
# -----------------------------------------------------------------------------
MY_IP=$(curl -s --max-time 5 https://checkip.amazonaws.com 2>/dev/null || echo "0.0.0.0")
if [[ "${MY_IP}" == "0.0.0.0" ]]; then
    warn "Could not determine your public IP. SSH will be open to 0.0.0.0/0 – restrict this manually."
    MY_CIDR="0.0.0.0/0"
else
    MY_CIDR="${MY_IP}/32"
fi
info "SSH restricted to: ${MY_CIDR}"

# -----------------------------------------------------------------------------
# Create security group (idempotent)
# -----------------------------------------------------------------------------
EXISTING_SG=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=${SG_NAME}" \
    --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")

if [[ "${EXISTING_SG}" == "None" || -z "${EXISTING_SG}" ]]; then
    info "Creating security group: ${SG_NAME} ..."
    VPC_ID=$(aws ec2 describe-vpcs \
        --filters "Name=isDefault,Values=true" \
        --query 'Vpcs[0].VpcId' --output text)

    SG_ID=$(aws ec2 create-security-group \
        --group-name "${SG_NAME}" \
        --description "Security group for ${INSTANCE_NAME}" \
        --vpc-id "${VPC_ID}" \
        --query 'GroupId' --output text)

    # Inbound: SSH from caller's IP
    aws ec2 authorize-security-group-ingress \
        --group-id "${SG_ID}" \
        --protocol tcp --port 22 --cidr "${MY_CIDR}"

    # Inbound: Flask API port 5000 from anywhere
    aws ec2 authorize-security-group-ingress \
        --group-id "${SG_ID}" \
        --protocol tcp --port 5000 --cidr "0.0.0.0/0"

    # Inbound: HTTP 80 from anywhere
    aws ec2 authorize-security-group-ingress \
        --group-id "${SG_ID}" \
        --protocol tcp --port 80 --cidr "0.0.0.0/0"

    aws ec2 create-tags \
        --resources "${SG_ID}" \
        --tags \
            Key=Name,Value="${SG_NAME}" \
            Key=Project,Value="${PROJECT_NAME}" \
            Key=Team,Value="${TEAM_NAME}"

    info "Security group created: ${SG_ID}"
else
    SG_ID="${EXISTING_SG}"
    warn "Security group '${SG_NAME}' already exists: ${SG_ID}"
fi

# -----------------------------------------------------------------------------
# Check if instance already exists (running or stopped)
# -----------------------------------------------------------------------------
EXISTING_INSTANCE=$(aws ec2 describe-instances \
    --filters \
        "Name=tag:Name,Values=${INSTANCE_NAME}" \
        "Name=instance-state-name,Values=running,stopped,pending" \
    --query 'Reservations[0].Instances[0].InstanceId' --output text 2>/dev/null || echo "None")

if [[ "${EXISTING_INSTANCE}" != "None" && -n "${EXISTING_INSTANCE}" ]]; then
    warn "EC2 instance '${INSTANCE_NAME}' already exists: ${EXISTING_INSTANCE}"
    INSTANCE_ID="${EXISTING_INSTANCE}"
else
    # Encode user-data script
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    USER_DATA_FILE="${SCRIPT_DIR}/../configs/ec2-user-data.sh"

    if [[ ! -f "${USER_DATA_FILE}" ]]; then
        error "User data script not found: ${USER_DATA_FILE}"
        exit 1
    fi

    info "Launching EC2 instance ..."
    INSTANCE_ID=$(aws ec2 run-instances \
        --image-id "${EC2_AMI_ID}" \
        --instance-type "${EC2_INSTANCE_TYPE}" \
        --key-name "${EC2_KEY_NAME}" \
        --security-group-ids "${SG_ID}" \
        --iam-instance-profile Name="${ROLE_NAME}" \
        --user-data "file://${USER_DATA_FILE}" \
        --block-device-mappings \
            "DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3,DeleteOnTermination=true}" \
        --tag-specifications \
            "ResourceType=instance,Tags=[
                {Key=Name,Value=${INSTANCE_NAME}},
                {Key=Project,Value=${PROJECT_NAME}},
                {Key=Team,Value=${TEAM_NAME}},
                {Key=Stage,Value=1},
                {Key=ManagedBy,Value=script}
            ]" \
        --query 'Instances[0].InstanceId' --output text)

    info "Instance launched: ${INSTANCE_ID}"
fi

# -----------------------------------------------------------------------------
# Wait for instance to be running
# -----------------------------------------------------------------------------
info "Waiting for instance to reach 'running' state ..."
aws ec2 wait instance-running --instance-ids "${INSTANCE_ID}"
info "Instance is running."

# -----------------------------------------------------------------------------
# Retrieve public IP
# -----------------------------------------------------------------------------
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids "${INSTANCE_ID}" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

# -----------------------------------------------------------------------------
# Output results
# -----------------------------------------------------------------------------
echo ""
info "=== EC2 Instance Ready ==="
echo -e "  Instance ID   : ${GREEN}${INSTANCE_ID}${NC}"
echo -e "  Public IP     : ${GREEN}${PUBLIC_IP}${NC}"
echo -e "  Instance Type : ${GREEN}${EC2_INSTANCE_TYPE}${NC}"
echo -e "  AMI           : ${GREEN}${EC2_AMI_ID}${NC}"
echo -e "  IAM Profile   : ${GREEN}${ROLE_NAME}${NC}"
echo ""
echo -e "  SSH command   : ${GREEN}ssh -i ~/.ssh/${EC2_KEY_NAME}.pem ubuntu@${PUBLIC_IP}${NC}"
echo ""
warn "User-data initialization is running in the background."
warn "Monitor with: ssh ubuntu@${PUBLIC_IP} 'sudo tail -f /var/log/user-data.log'"
