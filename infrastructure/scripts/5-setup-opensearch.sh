#!/bin/bash
# =============================================================================
# Script: 5-setup-opensearch.sh
# Purpose: Create and configure an Amazon OpenSearch Service managed domain
#          for vector search. Waits for the domain to become active.
# Usage:   source ../.env && bash 5-setup-opensearch.sh
# Prerequisites:
#   - Script 4 must have been run (IAM role must exist)
#   - AWS CLI configured with OpenSearch permissions
#   - Environment variables: AWS_REGION, TEAM_NAME, PROJECT_NAME
#   - Optional: OPENSEARCH_INSTANCE_TYPE, OPENSEARCH_VOLUME_SIZE
# Notes:
#   - Domain creation takes 10–15 minutes.
#   - For OpenSearch Serverless, see the comment block at the end of this file.
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
: "${PROJECT_NAME:=rag-class}"
: "${OPENSEARCH_INSTANCE_TYPE:=t3.small.search}"
: "${OPENSEARCH_VOLUME_SIZE:=10}"

DOMAIN_NAME="${PROJECT_NAME}-${TEAM_NAME}"
ROLE_NAME="${PROJECT_NAME}-ec2-role-${TEAM_NAME}"

info "=== OpenSearch Domain Setup ==="
info "Domain name     : ${DOMAIN_NAME}"
info "Instance type   : ${OPENSEARCH_INSTANCE_TYPE}"
info "Volume size     : ${OPENSEARCH_VOLUME_SIZE} GB"
info "Region          : ${AWS_REGION}"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

# -----------------------------------------------------------------------------
# Access policy – allows the EC2 role to perform all OpenSearch HTTP operations
# -----------------------------------------------------------------------------
ACCESS_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "AWS": "${ROLE_ARN}" },
      "Action": "es:*",
      "Resource": "arn:aws:es:${AWS_REGION}:${ACCOUNT_ID}:domain/${DOMAIN_NAME}/*"
    }
  ]
}
EOF
)

# -----------------------------------------------------------------------------
# Check if domain already exists
# -----------------------------------------------------------------------------
if aws opensearch describe-domain --domain-name "${DOMAIN_NAME}" &>/dev/null; then
    warn "OpenSearch domain '${DOMAIN_NAME}' already exists – skipping creation."
    DOMAIN_ENDPOINT=$(aws opensearch describe-domain \
        --domain-name "${DOMAIN_NAME}" \
        --query 'DomainStatus.Endpoint' --output text)
else
    info "Creating OpenSearch domain: ${DOMAIN_NAME} ..."
    info "This will take approximately 10–15 minutes ..."

    aws opensearch create-domain \
        --domain-name "${DOMAIN_NAME}" \
        --engine-version "OpenSearch_2.11" \
        --cluster-config \
            "InstanceType=${OPENSEARCH_INSTANCE_TYPE},InstanceCount=1,DedicatedMasterEnabled=false,ZoneAwarenessEnabled=false" \
        --ebs-options \
            "EBSEnabled=true,VolumeType=gp3,VolumeSize=${OPENSEARCH_VOLUME_SIZE}" \
        --access-policies "${ACCESS_POLICY}" \
        --encryption-at-rest-options "Enabled=true" \
        --node-to-node-encryption-options "Enabled=true" \
        --domain-endpoint-options \
            "EnforceHTTPS=true,TLSSecurityPolicy=Policy-Min-TLS-1-2-2019-07" \
        --advanced-security-options \
            "Enabled=false" \
        --tags \
            "Key=Project,Value=${PROJECT_NAME}" \
            "Key=Team,Value=${TEAM_NAME}" \
            "Key=Stage,Value=1" \
            "Key=ManagedBy,Value=script"

    info "Domain creation initiated. Waiting for domain to become active ..."

    # Wait loop – check every 60 seconds for up to 20 minutes
    MAX_WAIT=20
    WAITED=0
    while [[ "${WAITED}" -lt "${MAX_WAIT}" ]]; do
        PROCESSING=$(aws opensearch describe-domain \
            --domain-name "${DOMAIN_NAME}" \
            --query 'DomainStatus.Processing' --output text)
        if [[ "${PROCESSING}" == "False" ]]; then
            break
        fi
        info "Domain is still being created... (${WAITED}/${MAX_WAIT} minutes elapsed)"
        sleep 60
        WAITED=$((WAITED + 1))
    done

    if [[ "${WAITED}" -ge "${MAX_WAIT}" ]]; then
        warn "Domain creation is still in progress after ${MAX_WAIT} minutes."
        warn "Check status with: aws opensearch describe-domain --domain-name ${DOMAIN_NAME}"
    else
        info "Domain is active."
    fi

    DOMAIN_ENDPOINT=$(aws opensearch describe-domain \
        --domain-name "${DOMAIN_NAME}" \
        --query 'DomainStatus.Endpoint' --output text)
fi

# -----------------------------------------------------------------------------
# Output results
# -----------------------------------------------------------------------------
echo ""
info "=== OpenSearch Domain Ready ==="
echo -e "  Domain Name : ${GREEN}${DOMAIN_NAME}${NC}"
echo -e "  Endpoint    : ${GREEN}${DOMAIN_ENDPOINT}${NC}"
echo -e "  Region      : ${GREEN}${AWS_REGION}${NC}"
echo ""
info "Set in your .env: OS_HOST=https://${DOMAIN_ENDPOINT}"
info "Verify with: aws opensearch describe-domain --domain-name ${DOMAIN_NAME}"

# =============================================================================
# ALTERNATIVE: OpenSearch Serverless
# Uncomment and adapt the block below if you prefer Serverless collections.
# =============================================================================
# COLLECTION_NAME="${PROJECT_NAME}-${TEAM_NAME}"
#
# aws opensearchserverless create-collection \
#     --name "${COLLECTION_NAME}" \
#     --type VECTORSEARCH \
#     --description "RAG vector search collection for ${TEAM_NAME}"
#
# aws opensearchserverless create-access-policy \
#     --name "${COLLECTION_NAME}-access" \
#     --type data \
#     --policy "[{\"Rules\":[{\"ResourceType\":\"collection\",\"Resource\":[\"collection/${COLLECTION_NAME}\"],\"Permission\":[\"aoss:*\"]},{\"ResourceType\":\"index\",\"Resource\":[\"index/${COLLECTION_NAME}/*\"],\"Permission\":[\"aoss:*\"]}],\"Principal\":[\"${ROLE_ARN}\"]}]"
#
# aws opensearchserverless create-security-policy \
#     --name "${COLLECTION_NAME}-network" \
#     --type network \
#     --policy "[{\"Rules\":[{\"ResourceType\":\"collection\",\"Resource\":[\"collection/${COLLECTION_NAME}\"]}],\"AllowFromPublic\":true}]"
