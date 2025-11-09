# Step-by-Step Deployment Instructions for Story 2-3: Feedback Feature

## ✅ Completed Steps
1. ✅ Feedback Model implementation (`src/models/feedback.py`)
2. ✅ Feedback Service implementation (`src/services/feedback_service.py`)
3. ✅ API endpoints implementation (`src/api/rest_api.py`)
4. ✅ Error classes (`src/utils/errors.py`)
5. ✅ All 29 tests passing
6. ✅ SAM template updated with FeedbackTable

## 📋 Next Steps

### Step 1: Validate SAM Template Changes
Verify the template.yaml changes are correct:

```bash
# Validate CloudFormation template syntax
sam validate --template template.yaml
```

**Expected Output:** `template.yaml is a valid SAM Template`

---

### Step 2: Build the SAM Application
Build the application to ensure all dependencies are packaged correctly:

```bash
# Build the SAM application
sam build
```

**Expected Output:** Build successful with no errors

---

### Step 3: Test Locally (Optional but Recommended)
Test the feedback endpoints locally before deploying:

```bash
# Start local API Gateway
sam local start-api

# In another terminal, test the endpoints:
# 1. Create a job first (if you don't have one)
curl -X POST http://localhost:3000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{"blueprint": {"file": "base64encodeddata", "format": "pdf"}}'

# 2. Submit feedback (replace JOB_ID with actual job_id from step 1)
curl -X POST http://localhost:3000/api/v1/jobs/JOB_ID/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "feedback": "wrong",
    "room_id": "room_001",
    "correction": {
      "bounding_box": [60, 60, 210, 310]
    }
  }'

# 3. Get feedback
curl -X GET http://localhost:3000/api/v1/jobs/JOB_ID/feedback
```

---

### Step 4: Deploy to AWS (Dev Environment)
Deploy the updated stack to your dev environment:

```bash
# Deploy with guided mode (first time) or use existing config
sam deploy --guided

# Or if you have samconfig.toml already configured:
sam deploy --stack-name locatrix-dev
```

**What happens during deployment:**
- Creates/updates the `dev-feedback` DynamoDB table
- Updates Lambda function with new code and environment variables
- Adds new API Gateway routes for feedback endpoints
- Grants Lambda permissions to access FeedbackTable

**Expected Output:** 
- Stack update/create successful
- Outputs showing API URL and table names

---

### Step 5: Verify Deployment
After deployment, verify everything is working:

#### 5.1 Check DynamoDB Table
```bash
# List tables to verify FeedbackTable exists
aws dynamodb list-tables --region YOUR_REGION

# Describe the table structure
aws dynamodb describe-table \
  --table-name dev-feedback \
  --region YOUR_REGION
```

**Expected:** Table exists with:
- Partition key: `feedback_id` (String)
- Sort key: `job_id` (String)
- GSI: `job_id-index`

#### 5.2 Check Lambda Environment Variables
```bash
# Get Lambda function configuration
aws lambda get-function-configuration \
  --function-name dev-api-rest-handler \
  --region YOUR_REGION \
  --query 'Environment.Variables.FEEDBACK_TABLE_NAME'
```

**Expected:** `dev-feedback`

#### 5.3 Test API Endpoints
Get your API URL from the deployment outputs:

```bash
# Get API endpoint from CloudFormation outputs
aws cloudformation describe-stacks \
  --stack-name locatrix-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text

# Test feedback submission (replace API_URL and JOB_ID)
curl -X POST ${API_URL}/api/v1/jobs/JOB_ID/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "feedback": "correct"
  }'

# Test feedback retrieval
curl -X GET ${API_URL}/api/v1/jobs/JOB_ID/feedback
```

---

### Step 6: Update Story Status
Update the sprint status to mark the story as complete:

```bash
# Edit docs/sprint-status.yaml
# Change line 50 from:
#   2-3-job-feedback-and-additional-features: ready-for-dev
# To:
#   2-3-job-feedback-and-additional-features: done
```

Or use your preferred method to update the story status.

---

### Step 7: Run Integration Tests Against Deployed API (Optional)
If you have integration tests that run against the deployed API:

```bash
# Set API_URL environment variable
export API_URL=$(aws cloudformation describe-stacks \
  --stack-name locatrix-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text)

# Run integration tests (if you have them)
pytest tests/integration/test_feedback_endpoints_deployed.py -v
```

---

### Step 8: Deploy to Production (When Ready)
Once dev testing is complete:

```bash
# Deploy to production environment
sam deploy \
  --stack-name locatrix-prod \
  --parameter-overrides Environment=prod
```

**Note:** Make sure to:
- Review all changes in dev first
- Test thoroughly in dev environment
- Have a rollback plan ready
- Update production environment variables if needed

---

## 🔍 Troubleshooting

### Issue: SAM validate fails
**Solution:** Check YAML indentation and syntax. Use a YAML validator.

### Issue: Deployment fails with "Table already exists"
**Solution:** This is normal if updating an existing stack. The table will be updated, not recreated.

### Issue: Lambda function can't access DynamoDB
**Solution:** Verify:
1. DynamoDBCrudPolicy is included in Lambda policies
2. Table name matches exactly (case-sensitive)
3. IAM permissions propagated (may take a few seconds)

### Issue: API Gateway returns 404 for feedback endpoints
**Solution:** Verify:
1. Routes are defined in `Events` section of Lambda function
2. Path matches exactly: `/api/v1/jobs/{job_id}/feedback`
3. Method matches: POST or GET

### Issue: Tests fail after deployment
**Solution:** 
1. Check environment variables are set correctly
2. Verify table name matches what's in DynamoDB
3. Check CloudWatch logs for Lambda errors

---

## 📊 Verification Checklist

- [ ] SAM template validates successfully
- [ ] Application builds without errors
- [ ] Deployment completes successfully
- [ ] FeedbackTable created in DynamoDB
- [ ] Lambda has FEEDBACK_TABLE_NAME environment variable
- [ ] API Gateway routes configured correctly
- [ ] Can submit feedback via POST endpoint
- [ ] Can retrieve feedback via GET endpoint
- [ ] Error handling works (invalid feedback, job not found)
- [ ] Story status updated to "done"

---

## 📝 Summary of Changes Made

### Files Modified:
1. **template.yaml**
   - Added `FeedbackTable` DynamoDB table definition
   - Added `FEEDBACK_TABLE_NAME` environment variable
   - Added DynamoDB permissions for FeedbackTable
   - Added API Gateway routes for feedback endpoints
   - Added FeedbackTableName output

### Files Created:
1. **src/models/feedback.py** - Feedback model and FeedbackType enum
2. **src/services/feedback_service.py** - Feedback service with DynamoDB integration

### Files Updated:
1. **src/api/rest_api.py** - Added feedback endpoint handlers
2. **src/utils/errors.py** - Added InvalidFeedbackError and FeedbackNotFoundError

---

## 🎯 Success Criteria

The deployment is successful when:
1. ✅ All SAM template changes are deployed
2. ✅ FeedbackTable exists in DynamoDB
3. ✅ Lambda function has access to FeedbackTable
4. ✅ API endpoints respond correctly
5. ✅ All tests pass (29/29)
6. ✅ Story status updated to "done"

---

**Ready to proceed?** Start with Step 1 and work through each step sequentially.

