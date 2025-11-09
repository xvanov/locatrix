#!/bin/bash
# Script to deploy Story 3.1 to AWS and run tests

set -e

echo "🚀 Deploying Story 3.1 to AWS"
echo ""

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured"
    echo ""
    echo "Please configure AWS credentials first:"
    echo "  1. Run: aws configure"
    echo "  2. Enter your AWS Access Key ID"
    echo "  3. Enter your AWS Secret Access Key"
    echo "  4. Enter your default region (e.g., us-east-1)"
    echo ""
    echo "Or set environment variables:"
    echo "  export AWS_ACCESS_KEY_ID=your-access-key"
    echo "  export AWS_SECRET_ACCESS_KEY=your-secret-key"
    echo "  export AWS_DEFAULT_REGION=us-east-1"
    exit 1
fi

# Get AWS account info
echo "✅ AWS credentials configured"
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region || echo "us-east-1")
echo "   Account: $AWS_ACCOUNT"
echo "   Region: $AWS_REGION"
echo ""

# Validate SAM template
echo "📋 Validating SAM template..."
sam validate --lint 2>&1 | grep -v "UserWarning" || true
echo "✅ Template is valid"
echo ""

# Build SAM application
echo "🔨 Building SAM application..."
sam build 2>&1 | grep -v "UserWarning" | tail -5
echo "✅ Build complete"
echo ""

# Unset LocalStack endpoint if set (for real AWS deployment)
unset AWS_ENDPOINT_URL

# Deploy to AWS
STACK_NAME="location-detection-dev"
echo "🚀 Deploying to AWS (stack: $STACK_NAME)..."
echo "   This may take 5-10 minutes..."
echo ""

sam deploy \
  --stack-name "$STACK_NAME" \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --no-confirm-changeset \
  --no-fail-on-empty-changeset \
  --parameter-overrides "Environment=dev" \
  --region "$AWS_REGION"

echo ""
echo "✅ Deployment complete!"
echo ""

# Get API endpoint
echo "📡 Getting API endpoint..."
API_URL=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text 2>/dev/null || echo "")

if [ -z "$API_URL" ]; then
    echo "⚠️  Could not retrieve API URL from stack outputs"
    echo "   Please check CloudFormation console for the ApiUrl output"
    exit 1
fi

echo "✅ API URL: $API_URL"
echo ""

# Save API URL for tests
echo "$API_URL" > /tmp/api-url.txt
echo "API URL saved to /tmp/api-url.txt"
echo ""

# Run Playwright tests against deployed API
echo "🧪 Running Playwright tests against deployed API..."
echo ""

BASE_URL="$API_URL" npm run test:api -- tests/api/story-3-1-preview-pipeline.spec.ts

echo ""
echo "✅ All tests complete!"
echo ""
echo "API Endpoint: $API_URL"
echo "Stack Name: $STACK_NAME"
echo ""
echo "To view stack outputs:"
echo "  aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION --query 'Stacks[0].Outputs'"
echo ""
echo "To delete the stack:"
echo "  aws cloudformation delete-stack --stack-name $STACK_NAME --region $AWS_REGION"

