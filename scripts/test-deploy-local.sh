#!/bin/bash
# Script to test stack deletion and creation locally
# Usage: ./scripts/test-deploy-local.sh [dev|prod]

set -e

ENV=${1:-dev}
REGION=${AWS_REGION:-us-east-1}
STACK_NAME="location-detection-${ENV}"

echo "🧪 Testing stack deletion and creation for: $ENV"
echo "Region: $REGION"
echo ""

# Step 1: Check for conflicting stack (location-detection-api)
echo "📦 Step 1: Checking for conflicting stacks..."
CONFLICTING_STACK="location-detection-api"
if [ "$ENV" = "dev" ]; then
  CONFLICTING_STATUS=$(aws cloudformation describe-stacks \
    --stack-name "$CONFLICTING_STACK" \
    --query 'Stacks[0].StackStatus' \
    --output text \
    --region "$REGION" 2>/dev/null || echo "NOT_FOUND")
  
  if [ "$CONFLICTING_STATUS" != "NOT_FOUND" ]; then
    echo "⚠️  Found conflicting stack: $CONFLICTING_STACK (status: $CONFLICTING_STATUS)"
    echo "   This stack exports the same CloudFormation exports and will conflict."
    read -p "Delete $CONFLICTING_STACK? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      echo "🗑️  Deleting conflicting stack..."
      aws cloudformation delete-stack --stack-name "$CONFLICTING_STACK" --region "$REGION"
      echo "Waiting for stack deletion to complete..."
      aws cloudformation wait stack-delete-complete --stack-name "$CONFLICTING_STACK" --region "$REGION" || echo "Stack deletion completed or timed out"
      echo "✅ Conflicting stack deleted"
      sleep 10
    else
      echo "❌ Cannot proceed - export conflict will cause deployment to fail"
      exit 1
    fi
  else
    echo "✅ No conflicting stack found"
  fi
fi

# Step 2: Check current stack status
echo ""
echo "📦 Step 2: Checking current stack status..."
STACK_STATUS=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].StackStatus' \
  --output text \
  --region "$REGION" 2>/dev/null || echo "NOT_FOUND")

echo "Stack status: $STACK_STATUS"
echo ""

# Step 3: Delete stack if it exists in a failed state
if [ "$STACK_STATUS" = "ROLLBACK_COMPLETE" ] || [ "$STACK_STATUS" = "CREATE_FAILED" ] || [ "$STACK_STATUS" = "DELETE_FAILED" ]; then
  echo "🗑️  Step 3: Deleting failed stack..."
  aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION"
  echo "Waiting for stack deletion to complete..."
  aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --region "$REGION"
  echo "✅ Stack deleted"
elif [ "$STACK_STATUS" != "NOT_FOUND" ]; then
  echo "⚠️  Stack exists with status: $STACK_STATUS"
  read -p "Delete this stack? (y/N): " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION"
    aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --region "$REGION"
    echo "✅ Stack deleted"
  else
    echo "Skipping deletion"
  fi
else
  echo "✅ No stack found - ready for creation"
fi

# Step 4: Wait and verify buckets are deleted
echo ""
echo "⏳ Step 4: Waiting for AWS to propagate deletions..."
sleep 10

BLUEPRINTS_BUCKET="location-detection-${ENV}-blueprints"
CACHE_BUCKET="location-detection-${ENV}-cache"

echo "Verifying buckets are deleted..."
MAX_RETRIES=12
RETRY_COUNT=0

for BUCKET in "$BLUEPRINTS_BUCKET" "$CACHE_BUCKET"; do
  RETRY_COUNT=0
  while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if aws s3api head-bucket --bucket "$BUCKET" --region "$REGION" 2>/dev/null; then
      echo "  ⏳ Bucket $BUCKET still exists (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES), waiting 10 seconds..."
      sleep 10
      RETRY_COUNT=$((RETRY_COUNT + 1))
    else
      echo "  ✅ Bucket $BUCKET confirmed deleted"
      break
    fi
  done
  
  if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "  ⚠️  Bucket $BUCKET still exists after $MAX_RETRIES attempts"
  fi
done

# Step 5: Build
echo ""
echo "🔨 Step 5: Building SAM application..."
sam build --use-container || sam build

# Step 6: Deploy
echo ""
echo "🚀 Step 6: Deploying to $ENV environment..."
if [ "$ENV" = "dev" ]; then
  sam deploy \
    --config-file samconfig.dev.toml \
    --stack-name "$STACK_NAME" \
    --capabilities CAPABILITY_IAM \
    --resolve-s3 \
    --no-confirm-changeset \
    --no-fail-on-empty-changeset \
    --region "$REGION"
else
  sam deploy \
    --config-file samconfig.prod.toml \
    --stack-name "$STACK_NAME" \
    --capabilities CAPABILITY_IAM \
    --resolve-s3 \
    --no-confirm-changeset \
    --no-fail-on-empty-changeset \
    --region "$REGION"
fi

# Step 7: Verify deployment
echo ""
echo "✅ Step 7: Verifying deployment..."
STACK_STATUS=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].StackStatus' \
  --output text \
  --region "$REGION")

if [ "$STACK_STATUS" = "CREATE_COMPLETE" ] || [ "$STACK_STATUS" = "UPDATE_COMPLETE" ]; then
  echo "✅ Deployment successful! Stack status: $STACK_STATUS"
  
  # Get API URL
  API_URL=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
    --output text \
    --region "$REGION")
  
  echo ""
  echo "🌐 API URL: $API_URL"
  echo "🏥 Health Check: $API_URL/health"
else
  echo "⚠️  Deployment status: $STACK_STATUS"
fi

