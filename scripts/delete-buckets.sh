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
echo "Waiting for buckets to be fully deleted (with retry logic)..."
MAX_RETRIES=15
RETRY_INTERVAL=10

for BUCKET in "$BLUEPRINTS_BUCKET" "$CACHE_BUCKET"; do
  RETRY_COUNT=0
  while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    # Check if bucket exists
    if aws s3api head-bucket --bucket "$BUCKET" --region "$REGION" 2>/dev/null; then
      RETRY_COUNT=$((RETRY_COUNT + 1))
      echo "  ⏳ Bucket $BUCKET still exists (attempt $RETRY_COUNT/$MAX_RETRIES), waiting ${RETRY_INTERVAL}s..."
      sleep $RETRY_INTERVAL
    else
      echo "  ✅ Bucket $BUCKET confirmed deleted"
      break
    fi
  done
  
  if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "  ⚠️  Bucket $BUCKET still exists after $MAX_RETRIES attempts"
    echo "  This may cause deployment to fail. Bucket may be in a 'deleting' state."
  fi
done

# Final wait to ensure AWS has fully propagated deletions
echo ""
echo "Final wait (30 seconds) to ensure AWS has fully propagated deletions..."
sleep 30

# Final verification
echo ""
echo "Final verification..."
ALL_DELETED=true
for BUCKET in "$BLUEPRINTS_BUCKET" "$CACHE_BUCKET"; do
  if aws s3api head-bucket --bucket "$BUCKET" --region "$REGION" 2>/dev/null; then
    echo "  ⚠️  WARNING: $BUCKET still exists - deployment may fail"
    ALL_DELETED=false
  else
    echo "  ✅ $BUCKET confirmed deleted"
  fi
done

if [ "$ALL_DELETED" = "false" ]; then
  echo ""
  echo "⚠️  Some buckets still exist. Deployment may fail with 409 conflict errors."
  echo "This usually means buckets are in a 'deleting' state and need more time."
else
  echo ""
  echo "✅ All buckets confirmed deleted - safe to proceed with deployment"
fi

