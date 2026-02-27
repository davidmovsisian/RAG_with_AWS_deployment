#!/bin/bash
# =============================================================================
# Script: 3-setup-s3-event.sh
# Purpose: Configure S3 bucket to send ObjectCreated events to SQS queue.
# Usage:   source ../.env && bash 3-setup-s3-event.sh
# Prerequisites:
#   - Scripts 1 and 2 must have been run first (bucket and queue must exist)
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

BUCKET_NAME="${PROJECT_NAME}-docs-${TEAM_NAME}"
QUEUE_NAME="${PROJECT_NAME}-docs-queue-${TEAM_NAME}"

info "=== S3 Event Notification Setup ==="
info "Bucket : ${BUCKET_NAME}"
info "Queue  : ${QUEUE_NAME}"

# -----------------------------------------------------------------------------
# Resolve SQS queue ARN
# -----------------------------------------------------------------------------
info "Resolving SQS queue ARN ..."
QUEUE_URL=$(aws sqs get-queue-url \
    --queue-name "${QUEUE_NAME}" \
    --query QueueUrl --output text)

QUEUE_ARN=$(aws sqs get-queue-attributes \
    --queue-url "${QUEUE_URL}" \
    --attribute-names QueueArn \
    --query 'Attributes.QueueArn' --output text)

info "Queue ARN: ${QUEUE_ARN}"

# -----------------------------------------------------------------------------
# Build notification configuration JSON
# -----------------------------------------------------------------------------
NOTIFICATION_CONFIG=$(cat <<EOF
{
  "QueueConfigurations": [
    {
      "Id": "rag-class-s3-event",
      "QueueArn": "${QUEUE_ARN}",
      "Events": ["s3:ObjectCreated:*"]
    }
  ]
}
EOF
)

# -----------------------------------------------------------------------------
# Apply notification configuration to S3 bucket
# -----------------------------------------------------------------------------
info "Applying event notification configuration to bucket '${BUCKET_NAME}' ..."
aws s3api put-bucket-notification-configuration \
    --bucket "${BUCKET_NAME}" \
    --notification-configuration "${NOTIFICATION_CONFIG}"

info "Event notification applied."

# -----------------------------------------------------------------------------
# Verify the configuration
# -----------------------------------------------------------------------------
info "Verifying notification configuration ..."
RESULT=$(aws s3api get-bucket-notification-configuration \
    --bucket "${BUCKET_NAME}")

CONFIGURED_ARN=$(echo "${RESULT}" | python3 -c "
import sys, json
cfg = json.load(sys.stdin)
arns = [q.get('QueueArn','') for q in cfg.get('QueueConfigurations', [])]
print('\n'.join(arns))
" 2>/dev/null || echo "")

if echo "${CONFIGURED_ARN}" | grep -q "${QUEUE_ARN}"; then
    info "Verification passed – queue ARN found in bucket notification config."
else
    warn "Could not auto-verify. Please check manually:"
    warn "  aws s3api get-bucket-notification-configuration --bucket ${BUCKET_NAME}"
fi

# -----------------------------------------------------------------------------
# Output results
# -----------------------------------------------------------------------------
echo ""
info "=== S3 → SQS Event Wiring Complete ==="
echo -e "  Bucket    : ${GREEN}${BUCKET_NAME}${NC}"
echo -e "  Queue ARN : ${GREEN}${QUEUE_ARN}${NC}"
echo -e "  Events    : ${GREEN}s3:ObjectCreated:*${NC}"
echo ""
info "Test by uploading a file:"
info "  echo 'test' | aws s3 cp - s3://${BUCKET_NAME}/test.txt"
info "Then check SQS:"
info "  aws sqs receive-message --queue-url '${QUEUE_URL}' --wait-time-seconds 5"
