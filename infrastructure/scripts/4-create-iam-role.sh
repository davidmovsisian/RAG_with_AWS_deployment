#!/bin/bash
# =============================================================================
# Script: 4-create-iam-role.sh
# Purpose: Create IAM role and policies for the EC2 instance to access
#          S3, SQS, Bedrock, OpenSearch, and Textract.
# Usage:   source ../.env && bash 4-create-iam-role.sh
# Prerequisites:
#   - Scripts 1 and 2 must have been run (bucket and queue must exist)
#   - AWS CLI configured with sufficient IAM permissions
#   - Environment variables: AWS_REGION, TEAM_NAME, PROJECT_NAME
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

ROLE_NAME="${PROJECT_NAME}-ec2-role-${TEAM_NAME}"
POLICY_NAME="${PROJECT_NAME}-ec2-policy-${TEAM_NAME}"
BUCKET_NAME="${PROJECT_NAME}-docs-${TEAM_NAME}"
QUEUE_NAME="${PROJECT_NAME}-docs-queue-${TEAM_NAME}"
OPENSEARCH_DOMAIN="${PROJECT_NAME}-${TEAM_NAME}"

info "=== IAM Role Setup ==="
info "Role name   : ${ROLE_NAME}"
info "Policy name : ${POLICY_NAME}"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Resolve resource ARNs
BUCKET_ARN="arn:aws:s3:::${BUCKET_NAME}"
QUEUE_ARN="arn:aws:sqs:${AWS_REGION}:${ACCOUNT_ID}:${QUEUE_NAME}"
OPENSEARCH_ARN="arn:aws:es:${AWS_REGION}:${ACCOUNT_ID}:domain/${OPENSEARCH_DOMAIN}/*"

# -----------------------------------------------------------------------------
# EC2 trust policy
# -----------------------------------------------------------------------------
TRUST_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "ec2.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
)

# -----------------------------------------------------------------------------
# Create IAM role (idempotent)
# -----------------------------------------------------------------------------
if aws iam get-role --role-name "${ROLE_NAME}" &>/dev/null; then
    warn "IAM role '${ROLE_NAME}' already exists – skipping creation."
else
    info "Creating IAM role: ${ROLE_NAME} ..."
    aws iam create-role \
        --role-name "${ROLE_NAME}" \
        --assume-role-policy-document "${TRUST_POLICY}" \
        --description "EC2 role for RAG system – ${TEAM_NAME}" \
        --tags \
            Key=Project,Value="${PROJECT_NAME}" \
            Key=Team,Value="${TEAM_NAME}" \
            Key=Stage,Value=1 \
            Key=ManagedBy,Value=script
    info "IAM role created."
fi

# -----------------------------------------------------------------------------
# Custom permissions policy
# -----------------------------------------------------------------------------
PERMISSIONS_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3DocumentAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "${BUCKET_ARN}",
        "${BUCKET_ARN}/*"
      ]
    },
    {
      "Sid": "SQSQueueAccess",
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes",
        "sqs:GetQueueUrl"
      ],
      "Resource": "${QUEUE_ARN}"
    },
    {
      "Sid": "BedrockModelInvocation",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:${AWS_REGION}::foundation-model/amazon.titan-embed-text-v1",
        "arn:aws:bedrock:${AWS_REGION}::foundation-model/amazon.titan-embed-text-v2:0",
        "arn:aws:bedrock:${AWS_REGION}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0",
        "arn:aws:bedrock:${AWS_REGION}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
        "arn:aws:bedrock:${AWS_REGION}::foundation-model/anthropic.claude-v2:1",
        "arn:aws:bedrock:${AWS_REGION}::foundation-model/anthropic.claude-instant-v1"
      ]
    },
    {
      "Sid": "OpenSearchAccess",
      "Effect": "Allow",
      "Action": [
        "es:ESHttpPost",
        "es:ESHttpPut",
        "es:ESHttpGet",
        "es:ESHttpDelete",
        "es:ESHttpHead"
      ],
      "Resource": "${OPENSEARCH_ARN}"
    },
    {
      "Sid": "TextractAccess",
      "Effect": "Allow",
      "Action": [
        "textract:DetectDocumentText",
        "textract:AnalyzeDocument",
        "textract:StartDocumentTextDetection",
        "textract:GetDocumentTextDetection"
      ],
      "Resource": "*"
    }
  ]
}
EOF
)

# -----------------------------------------------------------------------------
# Attach / update inline policy on the role
# -----------------------------------------------------------------------------
info "Attaching permissions policy to role ..."
aws iam put-role-policy \
    --role-name "${ROLE_NAME}" \
    --policy-name "${POLICY_NAME}" \
    --policy-document "${PERMISSIONS_POLICY}"
info "Policy attached."

# -----------------------------------------------------------------------------
# Create instance profile and attach role (idempotent)
# -----------------------------------------------------------------------------
if aws iam get-instance-profile --instance-profile-name "${ROLE_NAME}" &>/dev/null; then
    warn "Instance profile '${ROLE_NAME}' already exists – checking role association."
    # Check if the role is already attached
    ATTACHED=$(aws iam get-instance-profile \
        --instance-profile-name "${ROLE_NAME}" \
        --query 'InstanceProfile.Roles[*].RoleName' \
        --output text)
    if [[ "${ATTACHED}" != *"${ROLE_NAME}"* ]]; then
        info "Adding role to existing instance profile ..."
        aws iam add-role-to-instance-profile \
            --instance-profile-name "${ROLE_NAME}" \
            --role-name "${ROLE_NAME}"
    else
        info "Role already attached to instance profile."
    fi
else
    info "Creating instance profile: ${ROLE_NAME} ..."
    aws iam create-instance-profile \
        --instance-profile-name "${ROLE_NAME}"
    info "Adding role to instance profile ..."
    aws iam add-role-to-instance-profile \
        --instance-profile-name "${ROLE_NAME}" \
        --role-name "${ROLE_NAME}"
    info "Instance profile ready."
fi

# -----------------------------------------------------------------------------
# Output results
# -----------------------------------------------------------------------------
ROLE_ARN=$(aws iam get-role --role-name "${ROLE_NAME}" --query 'Role.Arn' --output text)

echo ""
info "=== IAM Role Ready ==="
echo -e "  Role Name             : ${GREEN}${ROLE_NAME}${NC}"
echo -e "  Role ARN              : ${GREEN}${ROLE_ARN}${NC}"
echo -e "  Instance Profile Name : ${GREEN}${ROLE_NAME}${NC}"
echo ""
info "Verify with: aws iam get-role --role-name ${ROLE_NAME}"
