#!/bin/bash
# =============================================================================
# Script: 1-create-s3-bucket.sh
# Purpose: Create and configure the S3 bucket for RAG document storage.
# Usage:   source ../.env && bash 1-create-s3-bucket.sh
# Prerequisites:
#   - AWS CLI configured with sufficient permissions
#   - Environment variables: AWS_REGION, TEAM_NAME, PROJECT_NAME
# =============================================================================

set -e

# -----------------------------------------------------------------------------
# Color output helpers
# -----------------------------------------------------------------------------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# -----------------------------------------------------------------------------
# Validate required environment variables
# -----------------------------------------------------------------------------
: "${AWS_REGION:?Environment variable AWS_REGION is required}"
: "${TEAM_NAME:?Environment variable TEAM_NAME is required}"
: "${PROJECT_NAME:=rag-class}"

BUCKET_NAME="${PROJECT_NAME}-docs-${TEAM_NAME}"

info "=== S3 Bucket Setup ==="
info "Bucket name : ${BUCKET_NAME}"
info "Region      : ${AWS_REGION}"

# -----------------------------------------------------------------------------
# Create S3 bucket (idempotent)
# -----------------------------------------------------------------------------
if aws s3api head-bucket --bucket "${BUCKET_NAME}" 2>/dev/null; then
    warn "Bucket '${BUCKET_NAME}' already exists – skipping creation."
else
    info "Creating S3 bucket: ${BUCKET_NAME} ..."
    if [[ "${AWS_REGION}" == "us-east-1" ]]; then
        # us-east-1 does not accept a LocationConstraint
        aws s3api create-bucket \
            --bucket "${BUCKET_NAME}" \
            --region "${AWS_REGION}"
    else
        aws s3api create-bucket \
            --bucket "${BUCKET_NAME}" \
            --region "${AWS_REGION}" \
            --create-bucket-configuration LocationConstraint="${AWS_REGION}"
    fi
    info "Bucket created successfully."
fi

# -----------------------------------------------------------------------------
# Block all public access
# -----------------------------------------------------------------------------
info "Blocking public access on bucket ..."
aws s3api put-public-access-block \
    --bucket "${BUCKET_NAME}" \
    --public-access-block-configuration \
        "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
info "Public access blocked."

# -----------------------------------------------------------------------------
# Enable versioning
# -----------------------------------------------------------------------------
info "Enabling versioning ..."
aws s3api put-bucket-versioning \
    --bucket "${BUCKET_NAME}" \
    --versioning-configuration Status=Enabled
info "Versioning enabled."

# -----------------------------------------------------------------------------
# Enable server-side encryption (SSE-S3 / AES-256)
# -----------------------------------------------------------------------------
info "Enabling server-side encryption (AES-256) ..."
aws s3api put-bucket-encryption \
    --bucket "${BUCKET_NAME}" \
    --server-side-encryption-configuration '{
        "Rules": [{
            "ApplyServerSideEncryptionByDefault": {
                "SSEAlgorithm": "AES256"
            },
            "BucketKeyEnabled": true
        }]
    }'
info "Encryption enabled."

# -----------------------------------------------------------------------------
# Tag the bucket
# -----------------------------------------------------------------------------
info "Tagging bucket ..."
aws s3api put-bucket-tagging \
    --bucket "${BUCKET_NAME}" \
    --tagging "TagSet=[
        {Key=Project,Value=${PROJECT_NAME}},
        {Key=Team,Value=${TEAM_NAME}},
        {Key=Stage,Value=1},
        {Key=ManagedBy,Value=script}
    ]"
info "Tags applied."

# -----------------------------------------------------------------------------
# Output results
# -----------------------------------------------------------------------------
BUCKET_ARN="arn:aws:s3:::${BUCKET_NAME}"

echo ""
info "=== S3 Bucket Ready ==="
echo -e "  Bucket Name : ${GREEN}${BUCKET_NAME}${NC}"
echo -e "  Bucket ARN  : ${GREEN}${BUCKET_ARN}${NC}"
echo -e "  Region      : ${GREEN}${AWS_REGION}${NC}"
echo ""
info "Verify with: aws s3 ls s3://${BUCKET_NAME}"
