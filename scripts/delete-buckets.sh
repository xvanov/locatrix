#!/bin/bash
# Quick script to delete orphaned S3 buckets
# Usage: ./scripts/delete-buckets.sh [dev|prod]

set -e

ENV=${1:-dev}
REGION=${AWS_REGION:-us-east-1}

BLUEPRINTS_BUCKET="location-detection-${ENV}-blueprints"
CACHE_BUCKET="location-detection-${ENV}-cache"

echo "🗑️  Deleting buckets for environment: $ENV"
echo ""

for BUCKET in "$BLUEPRINTS_BUCKET" "$CACHE_BUCKET"; do
  if aws s3api head-bucket --bucket "$BUCKET" --region "$REGION" 2>/dev/null; then
    echo "Found bucket: $BUCKET"
    
    # Delete all objects
    echo "  Deleting all objects..."
    aws s3 rm s3://$BUCKET --recursive --region "$REGION" || true
    
    # Delete all object versions
    echo "  Deleting object versions..."
    VERSIONS=$(aws s3api list-object-versions --bucket "$BUCKET" --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' --output json --region "$REGION" 2>/dev/null || echo "{}")
    if [ "$VERSIONS" != "null" ] && [ "$VERSIONS" != "{}" ] && [ -n "$VERSIONS" ] && [ "$(echo $VERSIONS | jq -r '.Objects | length')" -gt 0 ]; then
      aws s3api delete-objects --bucket "$BUCKET" --delete "$VERSIONS" --region "$REGION" 2>/dev/null || true
    fi
    
    # Delete delete markers
    echo "  Deleting delete markers..."
    MARKERS=$(aws s3api list-object-versions --bucket "$BUCKET" --query '{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}' --output json --region "$REGION" 2>/dev/null || echo "{}")
    if [ "$MARKERS" != "null" ] && [ "$MARKERS" != "{}" ] && [ -n "$MARKERS" ] && [ "$(echo $MARKERS | jq -r '.Objects | length')" -gt 0 ]; then
      aws s3api delete-objects --bucket "$BUCKET" --delete "$MARKERS" --region "$REGION" 2>/dev/null || true
    fi
    
    # Disable versioning
    echo "  Disabling versioning..."
    aws s3api put-bucket-versioning \
      --bucket "$BUCKET" \
      --versioning-configuration Status=Suspended \
      --region "$REGION" 2>/dev/null || true
    
    # Delete bucket
    echo "  Deleting bucket..."
    aws s3api delete-bucket --bucket "$BUCKET" --region "$REGION" && echo "  ✅ Deleted: $BUCKET" || echo "  ⚠️  Could not delete: $BUCKET"
  else
    echo "Bucket does not exist: $BUCKET"
  fi
done

echo ""
echo "✅ Bucket cleanup complete"
echo "Waiting 15 seconds for AWS to propagate..."
sleep 15

# Verify deletion
echo ""
echo "Verifying deletion..."
for BUCKET in "$BLUEPRINTS_BUCKET" "$CACHE_BUCKET"; do
  if aws s3api head-bucket --bucket "$BUCKET" --region "$REGION" 2>/dev/null; then
    echo "  ⚠️  $BUCKET still exists"
  else
    echo "  ✅ $BUCKET confirmed deleted"
  fi
done

