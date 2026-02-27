#!/bin/bash
# =============================================================================
# Script: cleanup.sh
# Purpose: Remove all AWS resources created by the infrastructure scripts.
#          Resources are deleted in reverse dependency order.
# Usage:   source ../.env && bash cleanup.sh
# WARNING: This permanently deletes data including documents in S3 and vectors
#          in OpenSearch. Confirm before running.
# =============================================================================

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
DLQ_NAME="${PROJECT_NAME}-docs-dlq-${TEAM_NAME}"
ROLE_NAME="${PROJECT_NAME}-ec2-role-${TEAM_NAME}"
POLICY_NAME="${PROJECT_NAME}-ec2-policy-${TEAM_NAME}"
DOMAIN_NAME="${PROJECT_NAME}-${TEAM_NAME}"
INSTANCE_NAME="${PROJECT_NAME}-ec2-${TEAM_NAME}"
SG_NAME="${PROJECT_NAME}-sg-${TEAM_NAME}"

# -----------------------------------------------------------------------------
# Confirmation prompt
# -----------------------------------------------------------------------------
echo ""
echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${RED}║                  ⚠  DESTRUCTIVE OPERATION ⚠                 ║${NC}"
echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
warn "This will permanently delete the following resources:"
echo "  - EC2 instance       : ${INSTANCE_NAME}"
echo "  - IAM role           : ${ROLE_NAME}"
echo "  - OpenSearch domain  : ${DOMAIN_NAME}"
echo "  - S3 bucket (+ data) : ${BUCKET_NAME}"
echo "  - SQS queue          : ${QUEUE_NAME}"
echo "  - SQS DLQ            : ${DLQ_NAME}"
echo "  - Security group     : ${SG_NAME}"
echo ""
read -rp "Type 'yes' to confirm deletion: " CONFIRM
if [[ "${CONFIRM}" != "yes" ]]; then
    info "Cleanup cancelled."
    exit 0
fi

echo ""
info "Starting cleanup ... (logging to /tmp/cleanup-${TEAM_NAME}.log)"
exec > >(tee -a "/tmp/cleanup-${TEAM_NAME}.log") 2>&1

# -----------------------------------------------------------------------------
# 1. Terminate EC2 instance
# -----------------------------------------------------------------------------
info "[1/7] Terminating EC2 instance ..."
INSTANCE_ID=$(aws ec2 describe-instances \
    --filters \
        "Name=tag:Name,Values=${INSTANCE_NAME}" \
        "Name=instance-state-name,Values=running,stopped,pending" \
    --query 'Reservations[0].Instances[0].InstanceId' --output text 2>/dev/null || echo "None")

if [[ "${INSTANCE_ID}" != "None" && -n "${INSTANCE_ID}" ]]; then
    aws ec2 terminate-instances --instance-ids "${INSTANCE_ID}"
    info "Waiting for instance to terminate ..."
    aws ec2 wait instance-terminated --instance-ids "${INSTANCE_ID}"
    info "Instance terminated: ${INSTANCE_ID}"
else
    warn "No running EC2 instance found for '${INSTANCE_NAME}' – skipping."
fi

# -----------------------------------------------------------------------------
# 2. Delete security group (after instance termination)
# -----------------------------------------------------------------------------
info "[2/7] Deleting security group ..."
SG_ID=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=${SG_NAME}" \
    --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")

if [[ "${SG_ID}" != "None" && -n "${SG_ID}" ]]; then
    # Small wait to allow instance to release ENI
    sleep 10
    aws ec2 delete-security-group --group-id "${SG_ID}" && \
        info "Security group deleted: ${SG_ID}" || \
        warn "Could not delete security group ${SG_ID} – may still be in use."
else
    warn "Security group '${SG_NAME}' not found – skipping."
fi

# -----------------------------------------------------------------------------
# 3. Delete IAM instance profile and role
# -----------------------------------------------------------------------------
info "[3/7] Deleting IAM role and instance profile ..."

if aws iam get-instance-profile --instance-profile-name "${ROLE_NAME}" &>/dev/null; then
    # Remove role from instance profile first
    aws iam remove-role-from-instance-profile \
        --instance-profile-name "${ROLE_NAME}" \
        --role-name "${ROLE_NAME}" 2>/dev/null || true
    aws iam delete-instance-profile --instance-profile-name "${ROLE_NAME}"
    info "Instance profile deleted."
fi

if aws iam get-role --role-name "${ROLE_NAME}" &>/dev/null; then
    # Delete inline policy
    aws iam delete-role-policy \
        --role-name "${ROLE_NAME}" \
        --policy-name "${POLICY_NAME}" 2>/dev/null || true
    aws iam delete-role --role-name "${ROLE_NAME}"
    info "IAM role deleted."
else
    warn "IAM role '${ROLE_NAME}' not found – skipping."
fi

# -----------------------------------------------------------------------------
# 4. Delete OpenSearch domain
# -----------------------------------------------------------------------------
info "[4/7] Deleting OpenSearch domain '${DOMAIN_NAME}' ..."
if aws opensearch describe-domain --domain-name "${DOMAIN_NAME}" &>/dev/null; then
    aws opensearch delete-domain --domain-name "${DOMAIN_NAME}"
    info "OpenSearch domain deletion initiated (takes several minutes)."
else
    warn "OpenSearch domain '${DOMAIN_NAME}' not found – skipping."
fi

# -----------------------------------------------------------------------------
# 5. Remove S3 event notification
# -----------------------------------------------------------------------------
info "[5/7] Removing S3 event notification ..."
if aws s3api head-bucket --bucket "${BUCKET_NAME}" 2>/dev/null; then
    aws s3api put-bucket-notification-configuration \
        --bucket "${BUCKET_NAME}" \
        --notification-configuration '{}'
    info "S3 event notification removed."
else
    warn "S3 bucket '${BUCKET_NAME}' not found – skipping notification removal."
fi

# -----------------------------------------------------------------------------
# 6. Purge and delete SQS queues
# -----------------------------------------------------------------------------
info "[6/7] Deleting SQS queues ..."
for Q_NAME in "${QUEUE_NAME}" "${DLQ_NAME}"; do
    Q_URL=$(aws sqs get-queue-url --queue-name "${Q_NAME}" \
        --query QueueUrl --output text 2>/dev/null || echo "")
    if [[ -n "${Q_URL}" ]]; then
        info "Purging queue: ${Q_NAME} ..."
        aws sqs purge-queue --queue-url "${Q_URL}" 2>/dev/null || true
        sleep 3
        aws sqs delete-queue --queue-url "${Q_URL}"
        info "Queue deleted: ${Q_NAME}"
    else
        warn "Queue '${Q_NAME}' not found – skipping."
    fi
done

# -----------------------------------------------------------------------------
# 7. Empty and delete S3 bucket
# -----------------------------------------------------------------------------
info "[7/7] Emptying and deleting S3 bucket '${BUCKET_NAME}' ..."
if aws s3api head-bucket --bucket "${BUCKET_NAME}" 2>/dev/null; then
    info "Removing all objects and versions ..."
    # Delete all object versions (including delete markers)
    aws s3api list-object-versions \
        --bucket "${BUCKET_NAME}" \
        --output json \
        --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' \
        2>/dev/null | \
    python3 -c "
import sys, json, subprocess, shlex
data = json.load(sys.stdin)
objects = data.get('Objects') or []
if objects:
    payload = json.dumps({'Objects': objects, 'Quiet': True})
    subprocess.run(['aws','s3api','delete-objects',
                    '--bucket','${BUCKET_NAME}',
                    '--delete', payload], check=True)
    print(f'Deleted {len(objects)} version(s).')
else:
    print('No versions to delete.')
" 2>/dev/null || true

    # Remove remaining objects (unversioned)
    aws s3 rm "s3://${BUCKET_NAME}" --recursive 2>/dev/null || true

    aws s3 rb "s3://${BUCKET_NAME}" --force
    info "S3 bucket deleted: ${BUCKET_NAME}"
else
    warn "S3 bucket '${BUCKET_NAME}' not found – skipping."
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
info "=== Cleanup Complete ==="
info "Log saved to: /tmp/cleanup-${TEAM_NAME}.log"
warn "OpenSearch domain deletion runs asynchronously and may take a few minutes."
