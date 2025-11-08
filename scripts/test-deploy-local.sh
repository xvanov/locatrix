#!/bin/bash
# Script to test stack deletion and creation locally
# Usage: ./scripts/test-deploy-local.sh [dev|prod] [--non-interactive] [--skip-build] [--cleanup-only]
#   --non-interactive: Auto-approve all deletions (for CI/CD)
#   --skip-build: Skip SAM build step (for CI/CD when artifacts are already available)
#   --cleanup-only: Stop after cleanup steps, before build/deploy (for CI/CD)

set -e

ENV=${1:-dev}
NON_INTERACTIVE=false
SKIP_BUILD=false
CLEANUP_ONLY=false

# Parse flags and environment
while [[ $# -gt 0 ]]; do
  case $1 in
    --non-interactive)
      NON_INTERACTIVE=true
      shift
      ;;
    --skip-build)
      SKIP_BUILD=true
      shift
      ;;
    --cleanup-only)
      CLEANUP_ONLY=true
      shift
      ;;
    dev|prod)
      ENV=$1
      shift
      ;;
    *)
      shift
      ;;
  esac
done

REGION=${AWS_REGION:-us-east-1}
STACK_NAME="location-detection-${ENV}"

echo "🧪 Testing stack deletion and creation for: $ENV"
if [ "$NON_INTERACTIVE" = "true" ]; then
  echo "Mode: Non-interactive (auto-approve)"
fi
if [ "$SKIP_BUILD" = "true" ]; then
  echo "Mode: Skip build (using existing artifacts)"
fi
if [ "$CLEANUP_ONLY" = "true" ]; then
  echo "Mode: Cleanup only (stop before build/deploy)"
fi
echo "Region: $REGION"
echo ""

# Step 1: Clean up orphaned S3 buckets (use the dedicated script)
echo "📦 Step 1: Cleaning up orphaned S3 buckets..."
if [ "$NON_INTERACTIVE" = "true" ]; then
  # Run bucket cleanup script (it's already non-interactive)
  ./scripts/delete-buckets.sh "$ENV" || echo "Bucket cleanup completed or no buckets found"
else
  echo "Running bucket cleanup..."
  ./scripts/delete-buckets.sh "$ENV" || echo "Bucket cleanup completed or no buckets found"
fi

# Step 2: Check for conflicting stack (location-detection-api)
echo ""
echo "📦 Step 2: Checking for conflicting stacks..."
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
    if [ "$NON_INTERACTIVE" = "true" ]; then
      echo "🗑️  Auto-deleting conflicting stack (non-interactive mode)..."
      DELETE_CONFLICTING=true
    else
      read -p "Delete $CONFLICTING_STACK? (y/N): " -n 1 -r
      echo
      if [[ $REPLY =~ ^[Yy]$ ]]; then
        DELETE_CONFLICTING=true
      else
        DELETE_CONFLICTING=false
      fi
    fi
    
    if [ "$DELETE_CONFLICTING" = "true" ]; then
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

# Step 3: Check current stack status
echo ""
echo "📦 Step 3: Checking current stack status..."
STACK_STATUS=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].StackStatus' \
  --output text \
  --region "$REGION" 2>/dev/null || echo "NOT_FOUND")

echo "Stack status: $STACK_STATUS"
echo ""

# Step 4: Delete stack if it exists in a failed state
if [ "$STACK_STATUS" = "ROLLBACK_COMPLETE" ] || [ "$STACK_STATUS" = "CREATE_FAILED" ] || [ "$STACK_STATUS" = "DELETE_FAILED" ]; then
  echo "🗑️  Step 4: Deleting failed stack..."
  aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION"
  echo "Waiting for stack deletion to complete..."
  aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --region "$REGION"
  echo "✅ Stack deleted"
elif [ "$STACK_STATUS" != "NOT_FOUND" ]; then
  echo "⚠️  Stack exists with status: $STACK_STATUS"
  if [ "$NON_INTERACTIVE" = "true" ]; then
    echo "ℹ️  Non-interactive mode: Will update existing stack"
    # Don't delete, just update
  else
    read -p "Delete this stack? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION"
      aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --region "$REGION"
      echo "✅ Stack deleted"
    else
      echo "Skipping deletion (will update)"
    fi
  fi
else
  echo "✅ No stack found - ready for creation"
fi

# Exit early if cleanup-only mode
if [ "$CLEANUP_ONLY" = "true" ]; then
  echo ""
  echo "✅ Cleanup completed (cleanup-only mode)"
  exit 0
fi

# Step 5: Build (unless skipped)
if [ "$SKIP_BUILD" != "true" ]; then
  echo ""
  echo "🔨 Step 5: Building SAM application..."
  sam build --use-container || sam build
else
  echo ""
  echo "⏭️  Step 5: Skipping build (using existing artifacts)"
fi

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

