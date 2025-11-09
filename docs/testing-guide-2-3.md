# Story 2-3: Testing Guide

## 📊 Current Status

**Story Status:** `ready-for-dev` → **Implementation Complete** (should be updated to `review` or `done`)

**Implementation Status:**
- ✅ **Code Complete:** All feedback functionality implemented
- ✅ **Tests Passing:** 29/29 tests passing (100%)
- ✅ **SAM Template:** Updated and validated
- ⏳ **Deployment:** Ready for deployment (not yet deployed)

**Test Coverage:**
- ✅ Integration Tests: 9/9 passing
- ✅ Unit Tests (Service): 8/8 passing  
- ✅ Unit Tests (Model): 11/11 passing

---

## 🧪 Testing Instructions

### Option 1: Local Testing (Before Deployment)

#### Prerequisites
```bash
# Ensure you have Python 3.9+ and dependencies installed
pip install -r src/requirements.txt
```

#### Run All Tests
```bash
# Run all feedback tests
python3 -m pytest src/tests/integration/test_feedback_endpoints.py \
                  src/tests/unit/test_feedback_service.py \
                  src/tests/unit/test_feedback_model.py -v

# Run with coverage report
python3 -m pytest src/tests/integration/test_feedback_endpoints.py \
                  src/tests/unit/test_feedback_service.py \
                  src/tests/unit/test_feedback_model.py \
                  --cov=src --cov-report=html
```

#### Test Specific Scenarios
```bash
# Test feedback submission
pytest src/tests/integration/test_feedback_endpoints.py::TestSubmitFeedback::test_submit_feedback_success -v

# Test feedback retrieval
pytest src/tests/integration/test_feedback_endpoints.py::TestGetFeedback::test_get_feedback_success -v

# Test error handling
pytest src/tests/integration/test_feedback_endpoints.py::TestSubmitFeedback::test_submit_feedback_invalid_type -v
```

---

### Option 2: Local API Testing (SAM Local)

#### Start Local API Gateway
```bash
# Set environment variables for local testing
export FEEDBACK_TABLE_NAME=test-feedback
export JOBS_TABLE_NAME=test-jobs
export BLUEPRINTS_BUCKET_NAME=test-blueprints

# Start local API (requires Docker)
sam local start-api --port 3000
```

#### Test Endpoints with curl

**1. Create a job first (if you don't have one):**
```bash
# Note: You'll need a valid base64-encoded file
curl -X POST http://localhost:3000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "blueprint": {
      "file": "base64encodeddatahere",
      "format": "pdf"
    }
  }'
```

**2. Submit feedback (replace JOB_ID with actual job_id):**
```bash
# Submit correct feedback
curl -X POST http://localhost:3000/api/v1/jobs/JOB_ID/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "feedback": "correct"
  }'

# Submit wrong feedback with correction
curl -X POST http://localhost:3000/api/v1/jobs/JOB_ID/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "feedback": "wrong",
    "room_id": "room_001",
    "correction": {
      "bounding_box": [60, 60, 210, 310]
    }
  }'

# Submit partial feedback
curl -X POST http://localhost:3000/api/v1/jobs/JOB_ID/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "feedback": "partial",
    "room_id": "room_002",
    "correction": {
      "bounding_box": [100, 100, 200, 200]
    }
  }'
```

**3. Retrieve feedback:**
```bash
curl -X GET http://localhost:3000/api/v1/jobs/JOB_ID/feedback
```

**4. Test error cases:**
```bash
# Invalid feedback type
curl -X POST http://localhost:3000/api/v1/jobs/JOB_ID/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "feedback": "invalid_type"
  }'

# Missing required field
curl -X POST http://localhost:3000/api/v1/jobs/JOB_ID/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "room_id": "room_001"
  }'

# Job not found
curl -X POST http://localhost:3000/api/v1/jobs/job_invalid/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "feedback": "correct"
  }'
```

---

### Option 3: Testing Against Deployed API

#### Prerequisites
```bash
# Get your API URL from CloudFormation outputs
export API_URL=$(aws cloudformation describe-stacks \
  --stack-name locatrix-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text)

echo "API URL: $API_URL"
```

#### Test Script
```bash
#!/bin/bash
# Save as test-feedback-api.sh

API_URL="${API_URL:-http://localhost:3000}"
JOB_ID="job_20240115_test123"  # Replace with actual job_id

echo "Testing Feedback API at: $API_URL"
echo "=================================="

# 1. Submit correct feedback
echo -e "\n1. Submitting correct feedback..."
curl -X POST "${API_URL}/api/v1/jobs/${JOB_ID}/feedback" \
  -H "Content-Type: application/json" \
  -d '{
    "feedback": "correct"
  }' | jq '.'

# 2. Submit wrong feedback
echo -e "\n2. Submitting wrong feedback..."
curl -X POST "${API_URL}/api/v1/jobs/${JOB_ID}/feedback" \
  -H "Content-Type: application/json" \
  -d '{
    "feedback": "wrong",
    "room_id": "room_001",
    "correction": {
      "bounding_box": [60, 60, 210, 310]
    }
  }' | jq '.'

# 3. Retrieve all feedback
echo -e "\n3. Retrieving all feedback..."
curl -X GET "${API_URL}/api/v1/jobs/${JOB_ID}/feedback" | jq '.'

# 4. Test invalid feedback type
echo -e "\n4. Testing invalid feedback type (should fail)..."
curl -X POST "${API_URL}/api/v1/jobs/${JOB_ID}/feedback" \
  -H "Content-Type: application/json" \
  -d '{
    "feedback": "invalid_type"
  }' | jq '.'

# 5. Test job not found
echo -e "\n5. Testing job not found (should fail)..."
curl -X POST "${API_URL}/api/v1/jobs/job_invalid_123/feedback" \
  -H "Content-Type: application/json" \
  -d '{
    "feedback": "correct"
  }' | jq '.'
```

#### Run Test Script
```bash
chmod +x test-feedback-api.sh
./test-feedback-api.sh
```

---

### Option 4: Python Test Script

Create `test_feedback_manual.py`:

```python
#!/usr/bin/env python3
"""Manual testing script for feedback endpoints."""
import requests
import json
import sys

API_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"
JOB_ID = sys.argv[2] if len(sys.argv) > 2 else "job_20240115_test123"

def test_submit_feedback(feedback_type, **kwargs):
    """Submit feedback and return response."""
    url = f"{API_URL}/api/v1/jobs/{JOB_ID}/feedback"
    data = {"feedback": feedback_type}
    data.update(kwargs)
    
    response = requests.post(url, json=data)
    print(f"\nSubmit {feedback_type} feedback:")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json()

def test_get_feedback():
    """Retrieve all feedback for a job."""
    url = f"{API_URL}/api/v1/jobs/{JOB_ID}/feedback"
    response = requests.get(url)
    print(f"\nGet feedback:")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json()

if __name__ == "__main__":
    print(f"Testing Feedback API at: {API_URL}")
    print(f"Job ID: {JOB_ID}")
    print("=" * 50)
    
    # Test 1: Submit correct feedback
    test_submit_feedback("correct")
    
    # Test 2: Submit wrong feedback
    test_submit_feedback(
        "wrong",
        room_id="room_001",
        correction={"bounding_box": [60, 60, 210, 310]}
    )
    
    # Test 3: Submit partial feedback
    test_submit_feedback(
        "partial",
        room_id="room_002",
        correction={"bounding_box": [100, 100, 200, 200]}
    )
    
    # Test 4: Get all feedback
    test_get_feedback()
    
    # Test 5: Invalid feedback type
    test_submit_feedback("invalid_type")
    
    print("\n" + "=" * 50)
    print("Testing complete!")
```

Run it:
```bash
python3 test_feedback_manual.py [API_URL] [JOB_ID]
```

---

## ✅ Expected Test Results

### Successful Responses

**Submit Feedback (201 Created):**
```json
{
  "status": "success",
  "data": {
    "feedback_id": "fb_20240115_xyz789",
    "job_id": "job_20240115_abc123",
    "message": "Feedback submitted successfully",
    "request_id": "req_20240115_123456"
  },
  "meta": {
    "request_id": "req_20240115_123456",
    "api_version": "v1"
  }
}
```

**Get Feedback (200 OK):**
```json
{
  "status": "success",
  "data": {
    "feedback": [
      {
        "feedback_id": "fb_20240115_xyz789",
        "job_id": "job_20240115_abc123",
        "feedback": "wrong",
        "room_id": "room_001",
        "correction": {
          "bounding_box": [60, 60, 210, 310]
        },
        "created_at": "2024-01-15T10:30:00Z"
      }
    ]
  },
  "meta": {
    "request_id": "req_20240115_123456",
    "api_version": "v1"
  }
}
```

### Error Responses

**Invalid Feedback Type (400 Bad Request):**
```json
{
  "status": "error",
  "error": {
    "code": "INVALID_FEEDBACK",
    "message": "Feedback type must be one of: wrong, correct, partial",
    "details": {
      "received_type": "invalid_type"
    }
  },
  "meta": {
    "request_id": "req_20240115_123456",
    "api_version": "v1"
  }
}
```

**Job Not Found (404 Not Found):**
```json
{
  "status": "error",
  "error": {
    "code": "JOB_NOT_FOUND",
    "message": "Job 'job_invalid' not found",
    "details": {
      "job_id": "job_invalid"
    }
  },
  "meta": {
    "request_id": "req_20240115_123456",
    "api_version": "v1"
  }
}
```

---

## 📋 Testing Checklist

- [ ] All unit tests pass (29/29)
- [ ] Can submit "correct" feedback without correction data
- [ ] Can submit "wrong" feedback with correction data
- [ ] Can submit "partial" feedback with correction data
- [ ] Can retrieve all feedback for a job
- [ ] Invalid feedback type returns 400 error
- [ ] Missing required fields returns 400 error
- [ ] Wrong feedback without correction returns error
- [ ] Job not found returns 404 error
- [ ] Empty feedback list returns empty array
- [ ] Feedback IDs are unique
- [ ] Feedback is associated with correct job_id

---

## 🚀 Next Steps

1. **Update Story Status:**
   ```bash
   # Edit docs/sprint-status.yaml
   # Change line 50 from:
   #   2-3-job-feedback-and-additional-features: ready-for-dev
   # To:
   #   2-3-job-feedback-and-additional-features: review
   # Or:
   #   2-3-job-feedback-and-additional-features: done
   ```

2. **Deploy to AWS:**
   ```bash
   sam build
   sam deploy --guided
   ```

3. **Test Deployed API:**
   - Use Option 3 or 4 above with your deployed API URL

4. **Verify DynamoDB:**
   ```bash
   # Check feedback table exists
   aws dynamodb describe-table --table-name dev-feedback
   
   # Query feedback items
   aws dynamodb scan --table-name dev-feedback --limit 5
   ```

---

## 🐛 Troubleshooting

**Issue: Tests fail locally**
- Check Python version (3.9+)
- Install dependencies: `pip install -r src/requirements.txt`
- Check environment variables are set

**Issue: SAM local doesn't work**
- Ensure Docker is running
- Check port 3000 is available
- Verify SAM CLI is installed: `sam --version`

**Issue: API returns 500 errors**
- Check CloudWatch logs for Lambda function
- Verify DynamoDB table exists
- Check IAM permissions
- Verify environment variables are set correctly

**Issue: Feedback not stored**
- Check DynamoDB table permissions
- Verify table name matches environment variable
- Check CloudWatch logs for errors

---

**Ready to test!** Start with Option 1 (local tests) to verify everything works, then proceed to deployment testing.

