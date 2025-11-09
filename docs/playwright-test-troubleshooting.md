# Running Playwright Tests for Story 3.1

## Issue: SAM Local API Startup Time

SAM Local needs to build Docker images on first run, which can take 1-2 minutes. The test script now waits up to 2 minutes.

## Critical: AWS Services Required

**SAM Local does NOT provide DynamoDB, S3, or Textract services.**

The Playwright tests require AWS services to be available. You have three options:

### Option 1: Use LocalStack (Recommended for Local Testing)

LocalStack provides local AWS service emulation:

```bash
# Install LocalStack
pip install localstack

# Start LocalStack (runs DynamoDB, S3, etc. locally)
localstack start

# Configure AWS CLI to use LocalStack
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

# Update SAM template environment variables to point to LocalStack
# Then run SAM Local API
sam build
sam local start-api --port 3000 --env-vars env-localstack.json
```

**Note:** Textract is not fully supported by LocalStack, so you'll need to mock it or use real AWS credentials.

### Option 2: Use Real AWS Services (For Staging/Production Testing)

Deploy to AWS and run tests against the deployed API:

```bash
# Deploy to AWS
sam build
sam deploy --guided

# Get API endpoint from stack outputs
API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name location-detection-api \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text)

# Run tests against deployed API
BASE_URL=$API_ENDPOINT npm run test:api
```

### Option 3: Mock AWS Services in Code (Advanced)

Add environment variable to enable mock mode and update Lambda handlers to use mocks when enabled.

## Quick Fix Options

### Option 1: Pre-build Docker Images (Recommended)
Run SAM Local once manually to build images, then use the script:

```bash
# Terminal 1: Build images (let it complete)
sam build
sam local start-api --port 3000

# Wait until you see "Running on http://127.0.0.1:3000"
# Then Ctrl+C to stop it

# Terminal 2: Run tests (images are now cached)
./scripts/test-story-3-1.sh
```

### Option 2: Run Tests Manually
```bash
# Terminal 1: Start API (let it build images)
sam build
sam local start-api --port 3000

# Terminal 2: Run tests
npm run test:api -- tests/api/story-3-1-preview-pipeline.spec.ts
```

### Option 3: Use Updated Script
The script now waits up to 2 minutes. Just run:
```bash
./scripts/test-story-3-1.sh
```

## Check Current Status

```bash
# Check if SAM is running
ps aux | grep "sam local"

# Check SAM logs
tail -f /tmp/sam-local-api.log

# Check if API is responding
curl http://localhost:3000/health
```

## Current Test Status

The Playwright tests are now updated to:
- ✅ Use valid base64-encoded test files (PNG, JPG, PDF)
- ✅ Create jobs via API before testing preview
- ✅ Handle file format validation correctly

**Remaining Issue:** SAM Local doesn't provide DynamoDB/S3, so tests will fail with `ResourceNotFoundException` unless you use LocalStack or real AWS services.

