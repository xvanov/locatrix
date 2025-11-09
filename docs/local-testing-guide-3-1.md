# Local Testing Guide for Story 3.1: Preview Pipeline

This guide explains how to test the Textract service integration and preview pipeline locally.

## Testing Options

### 1. Unit Tests (Fastest - Recommended for Development)

Unit tests mock AWS services and test individual components in isolation.

**Run unit tests:**
```bash
# Run all unit tests
pytest src/tests/unit/ -v

# Run specific test files
pytest src/tests/unit/test_textract_service.py -v
pytest src/tests/unit/test_preview_service.py -v
pytest src/tests/unit/test_room_detection.py -v

# Run with coverage
pytest src/tests/unit/ --cov=src/services --cov=src/utils --cov-report=html
```

**What gets tested:**
- TextractService document analysis logic
- PreviewService cache storage and retrieval
- Room detection algorithm
- Error handling and edge cases

### 2. Integration Tests (Medium Speed)

Integration tests mock AWS services but test API endpoints end-to-end.

**Run integration tests:**
```bash
# Run all integration tests
pytest src/tests/integration/ -v

# Run preview pipeline integration tests
pytest src/tests/integration/test_preview_pipeline.py -v
```

**What gets tested:**
- REST API endpoints (`POST /api/v1/jobs/{job_id}/preview`, etc.)
- End-to-end preview pipeline flow
- Error handling and response formats

### 3. SAM Local API (Slower - For Playwright Tests)

Run the API locally using SAM CLI, then run Playwright tests against it.

**Start SAM Local API:**
```bash
# Build the application
sam build

# Start local API server (runs on http://localhost:3000)
sam local start-api --port 3000

# In another terminal, run Playwright tests
npm run test:api
```

**Note:** SAM Local API uses Docker containers and requires:
- Docker Desktop running
- AWS credentials configured (even if using mocks)
- Textract will need to be mocked or use AWS credentials

**What gets tested:**
- Full API integration with Playwright
- All 12 Story 3.1 API tests
- Real HTTP requests and responses

### 4. Mock AWS Services with LocalStack (Advanced)

For more realistic testing, use LocalStack to run AWS services locally.

**Setup LocalStack:**
```bash
# Install LocalStack (requires Docker)
pip install localstack

# Start LocalStack
localstack start

# Configure AWS CLI to use LocalStack
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
```

**Note:** Textract is not fully supported by LocalStack, so you'll still need to mock it.

## Test Structure

```
src/tests/
├── unit/
│   ├── test_textract_service.py      # TextractService unit tests
│   ├── test_preview_service.py        # PreviewService unit tests
│   └── test_room_detection.py         # Room detection algorithm tests
├── integration/
│   └── test_preview_pipeline.py       # Preview pipeline integration tests
└── e2e/
    └── test_preview_workflows.py     # End-to-end workflow tests

tests/api/
└── story-3-1-preview-pipeline.spec.ts # Playwright API tests
```

## Quick Start

**For rapid development iteration:**
```bash
# Run unit tests (fastest feedback)
pytest src/tests/unit/test_textract_service.py -v

# Run integration tests
pytest src/tests/integration/test_preview_pipeline.py -v
```

**For full API testing:**
```bash
# Terminal 1: Start SAM Local API
sam build && sam local start-api --port 3000

# Terminal 2: Run Playwright tests
npm run test:api
```

## Mocking AWS Services

All tests use `unittest.mock` to mock AWS services. Example pattern:

```python
from unittest.mock import patch, MagicMock

@patch('src.services.textract_service.boto3')
def test_textract_analysis(mock_boto3):
    # Mock Textract client
    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client
    
    # Mock Textract response
    mock_client.analyze_document.return_value = {
        'Blocks': [...],
        'DocumentMetadata': {'Pages': 1}
    }
    
    # Test your code
    service = TextractService()
    result = service.analyze_document('bucket', 'key')
    assert 'text_blocks' in result
```

## Environment Variables

For local testing, set these environment variables:

```bash
export JOBS_TABLE_NAME=test-jobs
export PREVIEW_CACHE_TABLE_NAME=test-preview-cache
export BLUEPRINTS_BUCKET_NAME=test-blueprints
export CACHE_BUCKET_NAME=test-cache
export AWS_REGION=us-east-1
```

Or use pytest fixtures to set them automatically (see existing test patterns).

## Troubleshooting

**Tests fail with "Module not found":**
- Ensure you're running from project root
- Check that `src/` is in Python path
- Use `python -m pytest` instead of `pytest`

**SAM Local API won't start:**
- Ensure Docker Desktop is running
- Check port 3000 is not in use
- Try `sam local start-api --port 3001`

**Playwright tests fail:**
- Ensure SAM Local API is running on correct port
- Check `BASE_URL` in `playwright.config.ts` matches SAM port
- Verify API endpoints are accessible: `curl http://localhost:3000/health`

**Textract errors:**
- Textract requires AWS credentials or mocking
- Use mocks in unit/integration tests
- For SAM Local, configure AWS credentials or mock Textract

## Next Steps

1. Create unit tests for new services (see test files below)
2. Create integration tests for preview endpoints
3. Run tests locally before committing
4. Ensure all tests pass before marking story complete

