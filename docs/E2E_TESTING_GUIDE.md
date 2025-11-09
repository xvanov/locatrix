# End-to-End Testing Guide for Task 14

This guide explains how to deploy and run end-to-end tests for the job management API.

## Prerequisites

1. **AWS CLI configured** with appropriate credentials
2. **SAM CLI installed** (`sam --version`)
3. **Python dependencies installed**:
   ```bash
   pip install -r requirements.txt
   pip install pytest requests boto3
   ```

## Step 1: Deploy to AWS

### Build the SAM application:
```bash
sam build
```

### Deploy to AWS:
```bash
sam deploy --guided
```

Or use the existing configuration:
```bash
sam deploy
```

**Note:** The deployment will create:
- DynamoDB tables (`{env}-jobs`, `{env}-preview-cache`)
- S3 buckets (`location-detection-{env}-blueprints`, `location-detection-{env}-cache`)
- API Gateway HTTP API
- Lambda function with IAM permissions

### Get the API Endpoint URL:

After deployment, get the API endpoint URL:

```bash
# Option 1: From SAM outputs
sam list stack-outputs --stack-name location-detection-api --region us-east-1

# Option 2: From AWS Console
# Go to CloudFormation → Stacks → location-detection-api → Outputs → ApiUrl

# Option 3: From AWS CLI
aws cloudformation describe-stacks \
  --stack-name location-detection-api \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text
```

## Step 2: Set Environment Variables

Set the API endpoint and AWS resource names:

```bash
export API_ENDPOINT="https://your-api-id.execute-api.us-east-1.amazonaws.com"
export ENVIRONMENT="dev"
export JOBS_TABLE_NAME="dev-jobs"
export BLUEPRINTS_BUCKET_NAME="location-detection-dev-blueprints"
```

Or create a `.env` file:
```bash
API_ENDPOINT=https://your-api-id.execute-api.us-east-1.amazonaws.com
ENVIRONMENT=dev
JOBS_TABLE_NAME=dev-jobs
BLUEPRINTS_BUCKET_NAME=location-detection-dev-blueprints
```

## Step 3: Run End-to-End Tests

### Run all E2E tests:
```bash
pytest src/tests/e2e/test_job_workflows.py -v
```

### Run specific test classes:
```bash
# Test job creation
pytest src/tests/e2e/test_job_workflows.py::TestJobCreation -v

# Test job retrieval
pytest src/tests/e2e/test_job_workflows.py::TestJobRetrieval -v

# Test job cancellation
pytest src/tests/e2e/test_job_workflows.py::TestJobCancellation -v

# Test error handling
pytest src/tests/e2e/test_job_workflows.py::TestErrorHandling -v

# Test complete lifecycle
pytest src/tests/e2e/test_job_workflows.py::TestJobLifecycle -v
```

### Run with detailed output:
```bash
pytest src/tests/e2e/test_job_workflows.py -v -s --tb=long
```

## Step 4: Manual Testing (Alternative)

If you prefer manual testing, use these curl commands:

### 1. Create a Job:
```bash
# Create a test PDF file (small)
echo "%PDF-1.4" > test.pdf
echo "test content" >> test.pdf

# Base64 encode it
FILE_CONTENT=$(base64 -i test.pdf)

# Create job
curl -X POST "${API_ENDPOINT}/api/v1/jobs" \
  -H "Content-Type: application/json" \
  -d "{
    \"blueprint\": {
      \"file\": \"${FILE_CONTENT}\",
      \"format\": \"pdf\",
      \"filename\": \"test.pdf\"
    }
  }"
```

### 2. Get Job Status:
```bash
# Replace JOB_ID with the job_id from step 1
curl -X GET "${API_ENDPOINT}/api/v1/jobs/JOB_ID"
```

### 3. Cancel Job:
```bash
# Replace JOB_ID with the job_id from step 1
curl -X DELETE "${API_ENDPOINT}/api/v1/jobs/JOB_ID"
```

### 4. Verify in DynamoDB:
```bash
aws dynamodb get-item \
  --table-name dev-jobs \
  --key '{"job_id": {"S": "JOB_ID"}}'
```

### 5. Verify in S3:
```bash
# Get S3 key from DynamoDB item, then:
aws s3 ls s3://location-detection-dev-blueprints/blueprints/JOB_ID/
```

## Step 5: Verify Task 14 Requirements

Check off each requirement as you verify:

- [ ] **Deploy updated SAM template to AWS** ✓ (Completed in Step 1)
- [ ] **Test job creation**: POST /api/v1/jobs with valid blueprint file ✓
- [ ] **Verify job stored in DynamoDB**: Check `dev-jobs` table has correct fields ✓
- [ ] **Verify blueprint uploaded to S3**: Check bucket has file with correct key format ✓
- [ ] **Test job retrieval**: GET /api/v1/jobs/{job_id} returns correct status ✓
- [ ] **Test job cancellation**: DELETE /api/v1/jobs/{job_id} updates status ✓
- [ ] **Test error handling**: Invalid file format returns INVALID_FILE_FORMAT ✓
- [ ] **Test error handling**: Invalid job ID returns JOB_NOT_FOUND ✓
- [ ] **Test error handling**: Cancel completed job returns appropriate error ✓
- [ ] **End-to-end lifecycle**: Create → Retrieve → Cancel workflow works ✓

## Troubleshooting

### API Gateway returns 502/503:
- Check Lambda function logs: `sam logs -n ApiRestHandlerFunction --stack-name location-detection-api --tail`
- Verify IAM permissions are correct
- Check environment variables are set in Lambda

### DynamoDB errors:
- Verify table names match environment variables
- Check IAM permissions for DynamoDB access
- Ensure tables are created (check CloudFormation stack)

### S3 errors:
- Verify bucket names match environment variables
- Check IAM permissions for S3 access
- Verify bucket policies allow Lambda access

### Tests fail with connection errors:
- Verify API_ENDPOINT is set correctly
- Check API Gateway is deployed and accessible
- Verify AWS credentials are configured

## Cleanup

After testing, you can delete the stack:

```bash
sam delete --stack-name location-detection-api
```

Or delete specific resources:
```bash
# Delete test jobs from DynamoDB
aws dynamodb delete-item \
  --table-name dev-jobs \
  --key '{"job_id": {"S": "JOB_ID"}}'

# Delete test files from S3
aws s3 rm s3://location-detection-dev-blueprints/blueprints/JOB_ID/ --recursive
```



