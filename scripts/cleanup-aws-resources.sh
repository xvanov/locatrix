#!/bin/bash
# Script to manually clean up AWS resources for location-detection-dev environment
# Usage: ./scripts/cleanup-aws-resources.sh [dev|prod]

set -e

ENV=${1:-dev}
REGION=${AWS_REGION:-us-east-1}
STACK_NAME="location-detection-${ENV}"

echo "🧹 Cleaning up AWS resources for environment: $ENV"
echo "Region: $REGION"
echo ""

# Check and delete CloudFormation stack
echo "📦 Checking CloudFormation stack..."
STACK_STATUS=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].StackStatus' \
  --output text \
  --region "$REGION" 2>/dev/null || echo "NOT_FOUND")

if [ "$STACK_STATUS" = "ROLLBACK_COMPLETE" ] || [ "$STACK_STATUS" = "CREATE_FAILED" ] || [ "$STACK_STATUS" = "DELETE_FAILED" ]; then
  echo "⚠️  Found failed stack in status: $STACK_STATUS"
  echo "Deleting stack..."
  aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION"
  echo "Waiting for stack deletion..."
  aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --region "$REGION"
  echo "✅ Stack deleted"
elif [ "$STACK_STATUS" != "NOT_FOUND" ]; then
  echo "ℹ️  Stack exists with status: $STACK_STATUS"
  read -p "Delete this stack? (y/N): " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION"
    aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --region "$REGION"
    echo "✅ Stack deleted"
  fi
else
  echo "✅ No stack found"
fi

# Clean up S3 buckets
echo ""
echo "🪣 Cleaning up S3 buckets..."
# Get AWS Account ID for bucket names
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "$REGION" 2>/dev/null || echo "")

if [ -z "$ACCOUNT_ID" ]; then
  echo "⚠️  Warning: Could not get AWS Account ID, using old bucket names"
  BLUEPRINTS_BUCKET="location-detection-${ENV}-blueprints"
  CACHE_BUCKET="location-detection-${ENV}-cache"
else
  # Use new naming pattern with Account ID for uniqueness
  BLUEPRINTS_BUCKET="location-detection-${ENV}-blueprints-${ACCOUNT_ID}"
  CACHE_BUCKET="location-detection-${ENV}-cache-${ACCOUNT_ID}"
fi

for BUCKET in "$BLUEPRINTS_BUCKET" "$CACHE_BUCKET"; do
  if aws s3api head-bucket --bucket "$BUCKET" --region "$REGION" 2>/dev/null; then
    echo "⚠️  Found bucket: $BUCKET"
    
    # Delete all objects
    echo "  Deleting objects..."
    aws s3 rm s3://$BUCKET --recursive --region "$REGION" || true
    
    # Delete all versions
    echo "  Deleting versions..."
    VERSIONS=$(aws s3api list-object-versions --bucket "$BUCKET" --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' --output json --region "$REGION" 2>/dev/null)
    if [ "$VERSIONS" != "null" ] && [ "$VERSIONS" != "{}" ] && [ -n "$VERSIONS" ]; then
      aws s3api delete-objects --bucket "$BUCKET" --delete "$VERSIONS" --region "$REGION" 2>/dev/null || true
    fi
    
    # Delete delete markers
    MARKERS=$(aws s3api list-object-versions --bucket "$BUCKET" --query '{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}' --output json --region "$REGION" 2>/dev/null)
    if [ "$MARKERS" != "null" ] && [ "$MARKERS" != "{}" ] && [ -n "$MARKERS" ]; then
      aws s3api delete-objects --bucket "$BUCKET" --delete "$MARKERS" --region "$REGION" 2>/dev/null || true
    fi
    
    # Suspend versioning
    echo "  Suspending versioning..."
    aws s3api put-bucket-versioning \
      --bucket "$BUCKET" \
      --versioning-configuration Status=Suspended \
      --region "$REGION" 2>/dev/null || true
    
    # Delete bucket
    echo "  Deleting bucket..."
    if aws s3api delete-bucket --bucket "$BUCKET" --region "$REGION" 2>/dev/null; then
      echo "  ✅ Deleted: $BUCKET"
    else
      echo "  ⚠️  Could not delete: $BUCKET (may have remaining objects or policies)"
    fi
  else
    echo "✅ Bucket does not exist: $BUCKET"
  fi
done

# Clean up DynamoDB tables
echo ""
echo "🗄️  Cleaning up DynamoDB tables..."
JOBS_TABLE="${ENV}-jobs"
PREVIEW_TABLE="${ENV}-preview-cache"

for TABLE in "$JOBS_TABLE" "$PREVIEW_TABLE"; do
  TABLE_STATUS=$(aws dynamodb describe-table --table-name "$TABLE" --region "$REGION" --query 'Table.TableStatus' --output text 2>/dev/null || echo "NOT_FOUND")
  if [ "$TABLE_STATUS" != "NOT_FOUND" ]; then
    echo "⚠️  Found table: $TABLE (status: $TABLE_STATUS)"
    if [ "$TABLE_STATUS" = "ACTIVE" ]; then
      echo "  Deleting table..."
      aws dynamodb delete-table --table-name "$TABLE" --region "$REGION"
      echo "  ✅ Deleted: $TABLE"
    elif [ "$TABLE_STATUS" = "DELETING" ]; then
      echo "  ⏳ Table is already being deleted"
    else
      echo "  ⚠️  Table status: $TABLE_STATUS (skipping)"
    fi
  else
    echo "✅ Table does not exist: $TABLE"
  fi
done

echo ""
echo "✅ Cleanup completed!"

