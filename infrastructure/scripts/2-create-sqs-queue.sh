#!/bin/bash
# =============================================================================
# Script: 2-create-sqs-queue.sh
# Purpose: Create SQS queue (and optional DLQ) for S3 document event messages.
# Usage:   source ../.env && bash 2-create-sqs-queue.sh
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

QUEUE_NAME="${PROJECT_NAME}-docs-queue-${TEAM_NAME}"
DLQ_NAME="${PROJECT_NAME}-docs-dlq-${TEAM_NAME}"
BUCKET_NAME="${PROJECT_NAME}-docs-${TEAM_NAME}"

info "=== SQS Queue Setup ==="
info "Queue name : ${QUEUE_NAME}"
info "DLQ name   : ${DLQ_NAME}"
info "Region     : ${AWS_REGION}"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# -----------------------------------------------------------------------------
# Create Dead Letter Queue (idempotent)
# -----------------------------------------------------------------------------
info "Creating dead-letter queue: ${DLQ_NAME} ..."
DLQ_URL=$(aws sqs create-queue \
    --queue-name "${DLQ_NAME}" \
    --attributes '{
        "MessageRetentionPeriod": "1209600",
        "Tags": {
            "Project": "'"${PROJECT_NAME}"'",
            "Team": "'"${TEAM_NAME}"'",
            "Stage": "1",
            "ManagedBy": "script"
        }
    }' \
    --query QueueUrl --output text 2>/dev/null || \
    aws sqs get-queue-url --queue-name "${DLQ_NAME}" --query QueueUrl --output text)

DLQ_ARN=$(aws sqs get-queue-attributes \
    --queue-url "${DLQ_URL}" \
    --attribute-names QueueArn \
    --query 'Attributes.QueueArn' --output text)

info "DLQ ARN: ${DLQ_ARN}"

# -----------------------------------------------------------------------------
# Create main SQS queue (idempotent)
# -----------------------------------------------------------------------------
info "Creating main queue: ${QUEUE_NAME} ..."

BUCKET_ARN="arn:aws:s3:::${BUCKET_NAME}"
QUEUE_ARN="arn:aws:sqs:${AWS_REGION}:${ACCOUNT_ID}:${QUEUE_NAME}"

# Build queue policy allowing S3 to send messages
QUEUE_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowS3SendMessage",
      "Effect": "Allow",
      "Principal": { "Service": "s3.amazonaws.com" },
      "Action": "sqs:SendMessage",
      "Resource": "${QUEUE_ARN}",
      "Condition": {
        "ArnEquals": { "aws:SourceArn": "${BUCKET_ARN}" }
      }
    }
  ]
}
EOF
)

REDRIVE_POLICY=$(cat <<EOF
{"deadLetterTargetArn":"${DLQ_ARN}","maxReceiveCount":"3"}
EOF
)

QUEUE_URL=$(aws sqs create-queue \
    --queue-name "${QUEUE_NAME}" \
    --attributes \
        VisibilityTimeout=300 \
        MessageRetentionPeriod=345600 \
        ReceiveMessageWaitTimeSeconds=20 \
        Policy="${QUEUE_POLICY}" \
        RedrivePolicy="${REDRIVE_POLICY}" \
    --query QueueUrl --output text 2>/dev/null || \
    aws sqs get-queue-url --queue-name "${QUEUE_NAME}" --query QueueUrl --output text)

# If queue already existed, update its policy to ensure it allows S3
aws sqs set-queue-attributes \
    --queue-url "${QUEUE_URL}" \
    --attributes \
        VisibilityTimeout=300 \
        MessageRetentionPeriod=345600 \
        ReceiveMessageWaitTimeSeconds=20 \
        Policy="${QUEUE_POLICY}" \
        RedrivePolicy="${REDRIVE_POLICY}"

info "Queue configured successfully."

# Tag the queue
aws sqs tag-queue \
    --queue-url "${QUEUE_URL}" \
    --tags \
        Project="${PROJECT_NAME}" \
        Team="${TEAM_NAME}" \
        Stage=1 \
        ManagedBy=script

# -----------------------------------------------------------------------------
# Output results
# -----------------------------------------------------------------------------
FINAL_ARN=$(aws sqs get-queue-attributes \
    --queue-url "${QUEUE_URL}" \
    --attribute-names QueueArn \
    --query 'Attributes.QueueArn' --output text)

echo ""
info "=== SQS Queues Ready ==="
echo -e "  Queue Name : ${GREEN}${QUEUE_NAME}${NC}"
echo -e "  Queue URL  : ${GREEN}${QUEUE_URL}${NC}"
echo -e "  Queue ARN  : ${GREEN}${FINAL_ARN}${NC}"
echo -e "  DLQ ARN    : ${GREEN}${DLQ_ARN}${NC}"
echo ""
info "Verify with: aws sqs get-queue-attributes --queue-url '${QUEUE_URL}' --attribute-names All"
