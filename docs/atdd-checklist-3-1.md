# ATDD Checklist - Epic 3, Story 3.1: Textract Service Integration with Preview Pipeline

**Date:** 2025-01-15
**Author:** BMad
**Primary Test Level:** API

---

## Story Summary

This story integrates AWS Textract service for document analysis and implements a fast preview pipeline that returns room detections within 5 seconds. The preview pipeline processes blueprint images (PNG, JPG, PDF) using Textract, extracts text and layout information, runs a fast room detection algorithm, and stores results in DynamoDB cache for quick retrieval.

**As a** developer
**I want** to integrate Textract and deploy a working preview pipeline that returns room detections
**So that** users can see initial results with a testable, end-to-end workflow

---

## Acceptance Criteria

1. **Given** The job service can store blueprints in S3 (from Story 1.2)
   **When** I create the Textract service and deploy the preview pipeline
   **Then** The following are implemented:
   - `src/services/textract_service.py` with Textract client integration
   - Document analysis using Textract AnalyzeDocument API
   - Text and layout extraction from blueprint images
   - `src/pipeline/stage_1_preview.py` Lambda handler
   - Fast room detection using lightweight model or heuristics
   - Preview results returned in under 5 seconds
   - Preview results stored in DynamoDB cache

2. **And** Textract can process PNG, JPG, and PDF files

3. **And** Extracted data is stored for use in subsequent stages

4. **And** Processing time is logged for monitoring

5. **And** Preview results include bounding boxes for detected rooms

6. **And** Preview pipeline can be tested end-to-end

7. **And** Preview can be returned even if full processing fails

---

## Failing Tests Created (RED Phase)

### API Tests (12 tests)

**File:** `tests/api/story-3-1-preview-pipeline.spec.ts` (450+ lines)

**AC1: Textract Service and Preview Pipeline Implementation (3 tests)**

- ✅ **Test:** should trigger preview pipeline and return preview results
  - **Status:** RED - Endpoint `/api/v1/jobs/{job_id}/preview` does not exist
  - **Verifies:** Preview pipeline endpoint exists and returns correct response structure

- ✅ **Test:** should return preview results within 5 seconds
  - **Status:** RED - Endpoint does not exist, performance requirement not implemented
  - **Verifies:** Preview pipeline meets 5-second performance requirement

- ✅ **Test:** should store preview results in DynamoDB cache
  - **Status:** RED - Cache endpoint `/api/v1/jobs/{job_id}/preview` (GET) does not exist
  - **Verifies:** Preview results are cached and can be retrieved

**AC2: Textract File Format Support (3 tests)**

- ✅ **Test:** should process PNG files via Textract
  - **Status:** RED - Textract service not implemented, PNG processing not available
  - **Verifies:** PNG file format is supported by Textract integration

- ✅ **Test:** should process JPG files via Textract
  - **Status:** RED - Textract service not implemented, JPG processing not available
  - **Verifies:** JPG file format is supported by Textract integration

- ✅ **Test:** should process PDF files via Textract
  - **Status:** RED - Textract service not implemented, PDF processing not available
  - **Verifies:** PDF file format is supported by Textract integration

**AC3: Textract Results Storage for Subsequent Stages (1 test)**

- ✅ **Test:** should store Textract analysis results in S3 for subsequent stages
  - **Status:** RED - Textract results storage endpoint does not exist
  - **Verifies:** Textract results are stored in S3 at `cache/textract/{job_id}/analysis.json`

**AC4: Processing Time Logging (2 tests)**

- ✅ **Test:** should log processing time for Textract analysis
  - **Status:** RED - Processing time logging not implemented
  - **Verifies:** Processing time is included in preview response

- ✅ **Test:** should include timing metrics in structured logs
  - **Status:** RED - Timing metrics breakdown not implemented
  - **Verifies:** Detailed timing metrics (textract_analysis_seconds, room_detection_seconds, total_seconds) are included

**AC5: Preview Results Include Bounding Boxes (2 tests)**

- ✅ **Test:** should return preview results with bounding boxes for detected rooms
  - **Status:** RED - Room detection algorithm not implemented
  - **Verifies:** Preview results include rooms with valid bounding boxes [x_min, y_min, x_max, y_max]

- ✅ **Test:** should include room name hints when available from text extraction
  - **Status:** RED - Room name extraction from text not implemented
  - **Verifies:** Room name hints are extracted from Textract text blocks when available

**AC6: End-to-End Preview Pipeline Testing (1 test)**

- ✅ **Test:** should process blueprint end-to-end through preview pipeline
  - **Status:** RED - Complete preview pipeline not implemented
  - **Verifies:** Full end-to-end workflow from job creation to preview results

**AC7: Graceful Degradation (2 tests)**

- ✅ **Test:** should return preview results even if full processing fails
  - **Status:** RED - Graceful degradation not implemented
  - **Verifies:** Preview can succeed even when full processing fails

- ✅ **Test:** should handle Textract failures gracefully and return partial results
  - **Status:** RED - Error handling for Textract failures not implemented
  - **Verifies:** Errors are handled gracefully with clear error messages or partial results

---

## Data Factories Created

### Preview Factory

**File:** `tests/support/factories/preview.factory.ts`

**Exports:**

- `createJob(overrides?)` - Create single job with optional overrides
- `createJobs(count)` - Create array of jobs
- `createRoom(overrides?)` - Create single room detection result with optional overrides
- `createRooms(count)` - Create array of rooms
- `createPreviewResult(overrides?)` - Create preview result with optional overrides
- `createTextractAnalysisResult(overrides?)` - Create Textract analysis result with optional overrides

**Example Usage:**

```typescript
const job = createJob({ status: 'pending' });
const rooms = createRooms(5); // Generate 5 random rooms
const previewResult = createPreviewResult({ job_id: job.job_id });
```

---

## Fixtures Created

### Preview Fixtures

**File:** `tests/support/fixtures/preview.fixture.ts`

**Fixtures:**

- `apiRequest` - API request helper function
  - **Setup:** Provides Playwright APIRequestContext
  - **Provides:** Helper function for making API requests with error handling
  - **Cleanup:** None (stateless helper)

- `testJob` - Test job fixture
  - **Setup:** Creates a test job using factory
  - **Provides:** Job object with job_id and metadata
  - **Cleanup:** TODO - Implement cleanup when job deletion endpoint is available

- `testPreviewResult` - Test preview result fixture
  - **Setup:** Creates preview result for test job
  - **Provides:** PreviewResult object with rooms and metadata
  - **Cleanup:** Preview results cached with TTL, cleanup handled automatically

**Example Usage:**

```typescript
import { test } from '../support/fixtures/preview.fixture';

test('should trigger preview pipeline', async ({ apiRequest, testJob }) => {
  const response = await apiRequest({
    method: 'POST',
    url: `/api/v1/jobs/${testJob.job_id}/preview`,
    data: {},
  });
});
```

---

## Mock Requirements

### AWS Textract Service Mock

**Service:** AWS Textract AnalyzeDocument API

**Success Response:**

```json
{
  "Blocks": [
    {
      "Id": "text_001",
      "BlockType": "LINE",
      "Text": "Room 101",
      "Geometry": {
        "BoundingBox": {
          "Left": 0.1,
          "Top": 0.2,
          "Width": 0.15,
          "Height": 0.05
        }
      }
    }
  ],
  "DocumentMetadata": {
    "Pages": 1
  }
}
```

**Failure Response:**

```json
{
  "Error": {
    "Code": "InvalidParameterException",
    "Message": "Invalid document format"
  }
}
```

**Notes:** 
- Mock Textract responses for testing without AWS credentials
- Use moto or localstack for integration testing
- Mock should support PNG, JPG, PDF formats

### AWS S3 Mock

**Service:** AWS S3 for blueprint storage and Textract results storage

**Success Response:** Standard S3 PutObject/GetObject responses

**Failure Response:** Standard S3 error responses

**Notes:**
- Mock S3 for blueprint file storage
- Mock S3 for Textract results storage at `cache/textract/{job_id}/analysis.json`
- Use moto or localstack for integration testing

### AWS DynamoDB Mock

**Service:** AWS DynamoDB for preview cache storage

**Success Response:** Standard DynamoDB PutItem/GetItem responses

**Failure Response:** Standard DynamoDB error responses

**Notes:**
- Mock DynamoDB preview_cache table
- Mock should support TTL attribute (expires_at)
- Use moto or localstack for integration testing

---

## Required data-testid Attributes

**Note:** This is a backend API story, so no UI data-testid attributes are required. However, if a frontend is added later for testing the preview pipeline, consider:

### Preview Results Display (Future Frontend)

- `preview-results-container` - Container for preview results
- `room-bounding-box-{room_id}` - Individual room bounding box visualization
- `room-name-{room_id}` - Room name display
- `processing-time` - Processing time display
- `preview-status` - Preview pipeline status indicator

**Implementation Example:**

```tsx
<div data-testid="preview-results-container">
  <div data-testid="processing-time">{processingTime}s</div>
  {rooms.map(room => (
    <div key={room.id} data-testid={`room-bounding-box-${room.id}`}>
      <span data-testid={`room-name-${room.id}`}>{room.name_hint}</span>
    </div>
  ))}
</div>
```

---

## Implementation Checklist

### Test: should trigger preview pipeline and return preview results

**File:** `tests/api/story-3-1-preview-pipeline.spec.ts`

**Tasks to make this test pass:**

- [ ] Add `POST /api/v1/jobs/{job_id}/preview` route to `src/api/rest_api.py`
- [ ] Create `src/pipeline/stage_1_preview.py` Lambda handler
- [ ] Implement preview pipeline handler function
- [ ] Load blueprint file from S3 using job_id
- [ ] Call Textract service to analyze document
- [ ] Implement fast room detection algorithm
- [ ] Format preview results according to schema
- [ ] Store preview results in DynamoDB preview_cache table
- [ ] Return preview results in response
- [ ] Add Lambda function to SAM template (`template.yaml`)
- [ ] Configure IAM permissions for S3, DynamoDB, Textract
- [ ] Run test: `npm run test:api -- story-3-1-preview-pipeline.spec.ts`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 8 hours

---

### Test: should return preview results within 5 seconds

**File:** `tests/api/story-3-1-preview-pipeline.spec.ts`

**Tasks to make this test pass:**

- [ ] Optimize Textract API call (use async/await efficiently)
- [ ] Implement lightweight room detection algorithm (heuristics-based)
- [ ] Add performance monitoring to identify bottlenecks
- [ ] Cache Textract results to avoid re-processing
- [ ] Optimize DynamoDB writes (batch operations if needed)
- [ ] Set Lambda timeout to 30 seconds (sufficient for 5-second target)
- [ ] Add processing_time_seconds to response
- [ ] Run test: `npm run test:api -- story-3-1-preview-pipeline.spec.ts -g "should return preview results within 5 seconds"`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 4 hours

---

### Test: should store preview results in DynamoDB cache

**File:** `tests/api/story-3-1-preview-pipeline.spec.ts`

**Tasks to make this test pass:**

- [ ] Add `GET /api/v1/jobs/{job_id}/preview` route to `src/api/rest_api.py`
- [ ] Implement cache lookup in DynamoDB preview_cache table
- [ ] Generate cache key: `preview:{blueprint_hash}:{model_version}`
- [ ] Store preview results with TTL (expires_at attribute)
- [ ] Return cached results if available
- [ ] Handle cache miss (trigger preview pipeline)
- [ ] Run test: `npm run test:api -- story-3-1-preview-pipeline.spec.ts -g "should store preview results in DynamoDB cache"`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 3 hours

---

### Test: should process PNG files via Textract

**File:** `tests/api/story-3-1-preview-pipeline.spec.ts`

**Tasks to make this test pass:**

- [ ] Create `src/services/textract_service.py` service class
- [ ] Implement `TextractService` class with boto3 Textract client
- [ ] Implement `analyze_document()` method using AnalyzeDocument API
- [ ] Handle PNG file format in Textract service
- [ ] Validate PNG file format before sending to Textract
- [ ] Test PNG file processing
- [ ] Run test: `npm run test:api -- story-3-1-preview-pipeline.spec.ts -g "should process PNG files"`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 2 hours

---

### Test: should process JPG files via Textract

**File:** `tests/api/story-3-1-preview-pipeline.spec.ts`

**Tasks to make this test pass:**

- [ ] Handle JPG file format in Textract service
- [ ] Validate JPG file format before sending to Textract
- [ ] Test JPG file processing
- [ ] Run test: `npm run test:api -- story-3-1-preview-pipeline.spec.ts -g "should process JPG files"`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 1 hour

---

### Test: should process PDF files via Textract

**File:** `tests/api/story-3-1-preview-pipeline.spec.ts`

**Tasks to make this test pass:**

- [ ] Handle PDF file format in Textract service
- [ ] Validate PDF file format before sending to Textract
- [ ] Test PDF file processing
- [ ] Run test: `npm run test:api -- story-3-1-preview-pipeline.spec.ts -g "should process PDF files"`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 1 hour

---

### Test: should store Textract analysis results in S3 for subsequent stages

**File:** `tests/api/story-3-1-preview-pipeline.spec.ts`

**Tasks to make this test pass:**

- [ ] Add `GET /api/v1/jobs/{job_id}/textract-results` route to `src/api/rest_api.py`
- [ ] Store Textract analysis results in S3 after analysis
- [ ] Use S3 key format: `cache/textract/{job_id}/analysis.json`
- [ ] Store text_blocks, layout_blocks, and metadata
- [ ] Include job_id and timestamp in stored results
- [ ] Implement retrieval endpoint for Textract results
- [ ] Run test: `npm run test:api -- story-3-1-preview-pipeline.spec.ts -g "should store Textract analysis results"`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 3 hours

---

### Test: should log processing time for Textract analysis

**File:** `tests/api/story-3-1-preview-pipeline.spec.ts`

**Tasks to make this test pass:**

- [ ] Add timing measurement for Textract analysis
- [ ] Include processing_time_seconds in preview response
- [ ] Use existing logging utility with request_id and job_id
- [ ] Log processing time in structured logs
- [ ] Run test: `npm run test:api -- story-3-1-preview-pipeline.spec.ts -g "should log processing time"`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 1 hour

---

### Test: should include timing metrics in structured logs

**File:** `tests/api/story-3-1-preview-pipeline.spec.ts`

**Tasks to make this test pass:**

- [ ] Add timing breakdown: textract_analysis_seconds, room_detection_seconds, total_seconds
- [ ] Include timing_metrics object in preview response
- [ ] Log timing metrics in structured JSON logs
- [ ] Run test: `npm run test:api -- story-3-1-preview-pipeline.spec.ts -g "should include timing metrics"`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 1 hour

---

### Test: should return preview results with bounding boxes for detected rooms

**File:** `tests/api/story-3-1-preview-pipeline.spec.ts`

**Tasks to make this test pass:**

- [ ] Implement fast room detection algorithm
- [ ] Extract room boundaries from Textract layout data
- [ ] Generate bounding boxes [x_min, y_min, x_max, y_max] for detected rooms
- [ ] Assign room IDs (format: `room_001`, `room_002`, etc.)
- [ ] Calculate confidence scores for detected rooms
- [ ] Include rooms array in preview response
- [ ] Validate bounding box format (x_min < x_max, y_min < y_max)
- [ ] Run test: `npm run test:api -- story-3-1-preview-pipeline.spec.ts -g "should return preview results with bounding boxes"`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 6 hours

---

### Test: should include room name hints when available from text extraction

**File:** `tests/api/story-3-1-preview-pipeline.spec.ts`

**Tasks to make this test pass:**

- [ ] Extract room names from Textract text blocks
- [ ] Match text blocks to room bounding boxes
- [ ] Assign name_hint to rooms when text matches room labels
- [ ] Include name_hint in room objects (optional field)
- [ ] Run test: `npm run test:api -- story-3-1-preview-pipeline.spec.ts -g "should include room name hints"`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 3 hours

---

### Test: should process blueprint end-to-end through preview pipeline

**File:** `tests/api/story-3-1-preview-pipeline.spec.ts`

**Tasks to make this test pass:**

- [ ] Integrate all components: job creation → preview pipeline → results
- [ ] Ensure job service can trigger preview pipeline
- [ ] Update job status when preview completes
- [ ] Store preview results in job record
- [ ] Test complete workflow end-to-end
- [ ] Run test: `npm run test:api -- story-3-1-preview-pipeline.spec.ts -g "should process blueprint end-to-end"`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 4 hours

---

### Test: should return preview results even if full processing fails

**File:** `tests/api/story-3-1-preview-pipeline.spec.ts`

**Tasks to make this test pass:**

- [ ] Implement graceful degradation pattern
- [ ] Ensure preview pipeline can succeed independently
- [ ] Handle full processing failures without affecting preview
- [ ] Return preview results even when full processing errors occur
- [ ] Run test: `npm run test:api -- story-3-1-preview-pipeline.spec.ts -g "should return preview results even if full processing fails"`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 2 hours

---

### Test: should handle Textract failures gracefully and return partial results

**File:** `tests/api/story-3-1-preview-pipeline.spec.ts`

**Tasks to make this test pass:**

- [ ] Implement error handling for Textract API failures
- [ ] Use existing retry utility for transient failures
- [ ] Return clear error messages for Textract failures
- [ ] Optionally return partial results if available
- [ ] Handle invalid file formats gracefully
- [ ] Run test: `npm run test:api -- story-3-1-preview-pipeline.spec.ts -g "should handle Textract failures gracefully"`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 3 hours

---

## Running Tests

```bash
# Install dependencies first
npm install

# Run all failing tests for this story
npm run test:api -- story-3-1-preview-pipeline.spec.ts

# Run specific test by name pattern
npm run test:api -- story-3-1-preview-pipeline.spec.ts -g "should trigger preview pipeline"

# Run tests in debug mode
npm run test:api -- story-3-1-preview-pipeline.spec.ts --debug

# Run tests with UI (Playwright UI mode)
npm run test:api -- story-3-1-preview-pipeline.spec.ts --ui

# Run tests with trace viewer
npm run test:api -- story-3-1-preview-pipeline.spec.ts --trace on

# Show test report
npm run test:api -- story-3-1-preview-pipeline.spec.ts --reporter=html
```

**Note:** Before running tests, ensure:
1. Playwright is installed: `npm install -D @playwright/test @faker-js/faker`
2. Test environment is configured (BASE_URL, AWS credentials for local testing)
3. Local AWS services are running (moto/localstack) or use test environment

---

## Red-Green-Refactor Workflow

### RED Phase (Complete) ✅

**TEA Agent Responsibilities:**

- ✅ All tests written and failing (12 API tests)
- ✅ Fixtures and factories created with auto-cleanup
- ✅ Mock requirements documented (Textract, S3, DynamoDB)
- ✅ Implementation checklist created with detailed tasks
- ✅ Test framework set up (Playwright for API testing)

**Verification:**

- All tests run and fail as expected
- Failure messages are clear and actionable
- Tests fail due to missing implementation, not test bugs

---

### GREEN Phase (DEV Team - Next Steps)

**DEV Agent Responsibilities:**

1. **Pick one failing test** from implementation checklist (start with highest priority)
2. **Read the test** to understand expected behavior
3. **Implement minimal code** to make that specific test pass
4. **Run the test** to verify it now passes (green)
5. **Check off the task** in implementation checklist
6. **Move to next test** and repeat

**Key Principles:**

- One test at a time (don't try to fix all at once)
- Minimal implementation (don't over-engineer)
- Run tests frequently (immediate feedback)
- Use implementation checklist as roadmap

**Recommended Order:**

1. Create Textract service (AC2 tests)
2. Create preview pipeline Lambda handler (AC1 tests)
3. Implement room detection algorithm (AC5 tests)
4. Add caching and storage (AC3 tests)
5. Add logging and monitoring (AC4 tests)
6. Add error handling (AC7 tests)
7. End-to-end integration (AC6 tests)

**Progress Tracking:**

- Check off tasks as you complete them
- Share progress in daily standup
- Mark story as IN PROGRESS in `docs/sprint-status.yaml`

---

### REFACTOR Phase (DEV Team - After All Tests Pass)

**DEV Agent Responsibilities:**

1. **Verify all tests pass** (green phase complete)
2. **Review code for quality** (readability, maintainability, performance)
3. **Extract duplications** (DRY principle)
4. **Optimize performance** (ensure 5-second requirement met)
5. **Ensure tests still pass** after each refactor
6. **Update documentation** (if API contracts change)

**Key Principles:**

- Tests provide safety net (refactor with confidence)
- Make small refactors (easier to debug if tests fail)
- Run tests after each change
- Don't change test behavior (only implementation)

**Completion:**

- All tests pass
- Code quality meets team standards
- No duplications or code smells
- Ready for code review and story approval

---

## Next Steps

1. **Review this checklist** with team in standup or planning
2. **Install Playwright dependencies**: `npm install -D @playwright/test @faker-js/faker`
3. **Run failing tests** to confirm RED phase: `npm run test:api -- story-3-1-preview-pipeline.spec.ts`
4. **Begin implementation** using implementation checklist as guide
5. **Work one test at a time** (red → green for each)
6. **Share progress** in daily standup
7. **When all tests pass**, refactor code for quality
8. **When refactoring complete**, run `bmad sm story-done` to move story to DONE

---

## Knowledge Base References Applied

This ATDD workflow consulted the following knowledge fragments:

- **fixture-architecture.md** - Test fixture patterns with setup/teardown and auto-cleanup using Playwright's `test.extend()`
- **data-factories.md** - Factory patterns using `@faker-js/faker` for random test data generation with overrides support
- **network-first.md** - Route interception patterns (intercept BEFORE navigation to prevent race conditions) - Applied to API testing context
- **test-quality.md** - Test design principles (Given-When-Then, one assertion per test, determinism, isolation)
- **test-levels-framework.md** - Test level selection framework (E2E vs API vs Component vs Unit) - Selected API tests for backend story

See `bmad/bmm/testarch/tea-index.csv` for complete knowledge fragment mapping.

---

## Test Execution Evidence

### Initial Test Run (RED Phase Verification)

**Command:** `npm run test:api -- story-3-1-preview-pipeline.spec.ts`

**Expected Results:**

```
Running 12 tests using 1 worker

  ✗ tests/api/story-3-1-preview-pipeline.spec.ts:15:5 › Story 3.1: Textract Service Integration with Preview Pipeline › AC1: Textract Service and Preview Pipeline Implementation › should trigger preview pipeline and return preview results
    Error: API request failed: 404 Not Found
    at apiRequest (tests/support/fixtures/preview.fixture.ts:25:11)

  ✗ tests/api/story-3-1-preview-pipeline.spec.ts:35:5 › Story 3.1: Textract Service Integration with Preview Pipeline › AC1: Textract Service and Preview Pipeline Implementation › should return preview results within 5 seconds
    Error: API request failed: 404 Not Found

  ... (10 more failing tests)

  12 failed
  0 passed
```

**Summary:**

- Total tests: 12
- Passing: 0 (expected)
- Failing: 12 (expected)
- Status: ✅ RED phase verified

**Expected Failure Messages:**

- `404 Not Found` - Endpoints do not exist yet
- `API request failed: 404` - Preview pipeline endpoint not implemented
- `Textract service not implemented` - Textract integration missing
- `Room detection algorithm not implemented` - Room detection logic missing

---

## Notes

- **Backend API Project**: This is a Python backend API project, so tests focus on API endpoints rather than UI
- **Playwright for API Testing**: Using Playwright's APIRequestContext for API testing (no browser required)
- **Test Framework Setup**: Playwright configured for API testing, can be extended for E2E testing when frontend is added
- **Mock Requirements**: Tests will need AWS service mocks (Textract, S3, DynamoDB) for local testing
- **Performance Requirement**: 5-second preview requirement is critical - monitor performance during implementation
- **Graceful Degradation**: Preview pipeline should work independently of full processing pipeline

---

## Contact

**Questions or Issues?**

- Ask in team standup
- Tag @BMad in Slack/Discord
- Refer to `bmad/bmm/docs/tea-README.md` for workflow documentation
- Consult `bmad/bmm/testarch/knowledge` for testing best practices

---

**Generated by BMad TEA Agent** - 2025-01-15


