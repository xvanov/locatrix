#!/bin/bash
# Setup LocalStack resources for Story 3.1 testing

set -e

echo "🔧 Setting up LocalStack resources for Story 3.1..."

export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

ENVIRONMENT=${ENVIRONMENT:-dev}

# Create DynamoDB tables
echo "📊 Creating DynamoDB tables..."

aws --endpoint-url=$AWS_ENDPOINT_URL dynamodb create-table \
  --table-name ${ENVIRONMENT}-jobs \
  --attribute-definitions AttributeName=job_id,AttributeType=S \
  --key-schema AttributeName=job_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  2>&1 | grep -v "ResourceInUseException" || echo "  ✓ Table ${ENVIRONMENT}-jobs already exists"

aws --endpoint-url=$AWS_ENDPOINT_URL dynamodb create-table \
  --table-name ${ENVIRONMENT}-preview-cache \
  --attribute-definitions AttributeName=blueprint_hash,AttributeType=S \
  --key-schema AttributeName=blueprint_hash,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  2>&1 | grep -v "ResourceInUseException" || echo "  ✓ Table ${ENVIRONMENT}-preview-cache already exists"

# Create S3 buckets
echo "🪣 Creating S3 buckets..."

aws --endpoint-url=$AWS_ENDPOINT_URL s3 mb s3://location-detection-${ENVIRONMENT}-blueprints \
  2>&1 | grep -v "BucketAlreadyOwnedByYou\|BucketAlreadyExists" || echo "  ✓ Bucket location-detection-${ENVIRONMENT}-blueprints already exists"

aws --endpoint-url=$AWS_ENDPOINT_URL s3 mb s3://location-detection-${ENVIRONMENT}-cache \
  2>&1 | grep -v "BucketAlreadyOwnedByYou\|BucketAlreadyExists" || echo "  ✓ Bucket location-detection-${ENVIRONMENT}-cache already exists"

aws --endpoint-url=$AWS_ENDPOINT_URL s3 mb s3://location-detection-${ENVIRONMENT}-textract-results \
  2>&1 | grep -v "BucketAlreadyOwnedByYou\|BucketAlreadyExists" || echo "  ✓ Bucket location-detection-${ENVIRONMENT}-textract-results already exists"

echo ""
echo "✅ LocalStack resources setup complete!"
echo ""
echo "Tables:"
aws --endpoint-url=$AWS_ENDPOINT_URL dynamodb list-tables --query 'TableNames' --output table
echo ""
echo "Buckets:"
aws --endpoint-url=$AWS_ENDPOINT_URL s3 ls | grep location-detection || echo "  (none found)"


