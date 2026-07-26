#!/usr/bin/env bash
# S3 bucket setup for Kepa raw diffs and PR bodies
#
# Prerequisites:
#   - AWS CLI configured (aws configure)
#   - IAM user/role with s3:CreateBucket, s3:PutBucketPolicy permissions
#
# Usage:
#   bash capture/s3-bucket.sh [BUCKET_NAME] [REGION]
#
# The bucket name must be globally unique across all of AWS.
# Default: kepa-raw-<account-id> in us-east-1

set -euo pipefail

BUCKET_NAME="${1:-}"
REGION="${2:-us-east-1}"

if [ -z "$BUCKET_NAME" ]; then
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "YOUR_ACCOUNT_ID")
    BUCKET_NAME="kepa-raw-${ACCOUNT_ID}"
fi

echo "Creating S3 bucket: $BUCKET_NAME in $REGION"

if [ "$REGION" = "us-east-1" ]; then
    # us-east-1 doesn't accept LocationConstraint
    aws s3api create-bucket \
        --bucket "$BUCKET_NAME" \
        --region "$REGION"
else
    aws s3api create-bucket \
        --bucket "$BUCKET_NAME" \
        --region "$REGION" \
        --create-bucket-configuration LocationConstraint="$REGION"
fi

# Block public access (security best practice)
aws s3api put-public-access-block \
    --bucket "$BUCKET_NAME" \
    --public-access-block-configuration \
        BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

# Enable server-side encryption (AES-256)
aws s3api put-bucket-encryption \
    --bucket "$BUCKET_NAME" \
    --server-side-encryption-configuration '{
        "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
    }'

# Enable versioning
aws s3api put-bucket-versioning \
    --bucket "$BUCKET_NAME" \
    --versioning-configuration Status=Enabled

echo ""
echo "Bucket created successfully."
echo "Bucket ARN: arn:aws:s3:::$BUCKET_NAME"
echo ""
echo "Add this to your .env:"
echo "  S3_BUCKET=$BUCKET_NAME"
