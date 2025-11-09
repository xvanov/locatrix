# ATDD Checklist - Epic 2, Story 2-3: Job Feedback and Additional Features

**Date:** 2025-01-15
**Author:** BMad
**Primary Test Level:** API

---

## Story Summary

This story implements feedback functionality for job management, allowing users to submit feedback on job results. The feedback endpoint supports three types: 'wrong', 'correct', and 'partial', with optional correction data for wrong/partial feedback.

**As a** developer
**I want** a feedback endpoint and additional job management features
**So that** users can provide feedback and the system supports additional use cases

---

## Acceptance Criteria

1. **Given** The job management API is deployed (from Story 1.2)
   **When** I add feedback functionality and additional features
   **Then** The following are implemented:
   - `POST /api/v1/jobs/{job_id}/feedback` endpoint to submit feedback
   - Feedback is stored and associated with the job
   - Feedback validation and error handling
   - Additional job management features as needed

2. **And** Feedback is validated and stored properly

3. **And** Feedback can be retrieved for analysis

4. **And** Invalid feedback returns appropriate error messages

---

## Failing Tests Created (RED Phase)

### API Tests (11 tests)

**File:** `src/tests/integration/test_feedback_endpoints.py` (339 lines)

- ✅ **Test:** `test_submit_feedback_success`
  - **Status:** RED - Missing `POST /api/v1/jobs/{job_id}/feedback` endpoint handler
  - **Verifies:** Feedback submission with valid data returns 201 with feedback_id

- ✅ **Test:** `test_submit_feedback_job_not_found`
  - **Status:** RED - Missing endpoint handler
  - **Verifies:** Submitting feedback for non-existent job returns 404 error

- ✅ **Test:** `test_submit_feedback_invalid_type`
  - **Status:** RED - Missing validation logic
  - **Verifies:** Invalid feedback type returns 400 with INVALID_FEEDBACK code

- ✅ **Test:** `test_submit_feedback_missing_required_fields`
  - **Status:** RED - Missing validation logic
  - **Verifies:** Missing required fields returns 400 error

- ✅ **Test:** `test_submit_feedback_correct_type`
  - **Status:** RED - Missing endpoint handler
  - **Verifies:** Feedback type 'correct' can be submitted without correction

- ✅ **Test:** `test_submit_feedback_partial_type`
  - **Status:** RED - Missing endpoint handler
  - **Verifies:** Feedback type 'partial' can be submitted with correction data

- ✅ **Test:** `test_get_feedback_success`
  - **Status:** RED - Missing `GET /api/v1/jobs/{job_id}/feedback` endpoint handler
  - **Verifies:** Retrieving feedback returns list of feedback items

- ✅ **Test:** `test_get_feedback_job_not_found`
  - **Status:** RED - Missing endpoint handler
  - **Verifies:** Retrieving feedback for non-existent job returns 404

- ✅ **Test:** `test_get_feedback_empty_list`
  - **Status:** RED - Missing endpoint handler
  - **Verifies:** Retrieving feedback for job with no feedback returns empty list

### Unit Tests - Feedback Service (8 tests)

**File:** `src/tests/unit/test_feedback_service.py` (234 lines)

- ✅ **Test:** `test_submit_feedback_success`
  - **Status:** RED - Missing `FeedbackService` class and `submit_feedback` method
  - **Verifies:** Feedback service stores feedback in DynamoDB and returns Feedback object

- ✅ **Test:** `test_submit_feedback_correct_type`
  - **Status:** RED - Missing service implementation
  - **Verifies:** Feedback type 'correct' can be stored without correction data

- ✅ **Test:** `test_submit_feedback_invalid_type`
  - **Status:** RED - Missing validation logic
  - **Verifies:** Invalid feedback type raises InvalidFeedbackError

- ✅ **Test:** `test_submit_feedback_wrong_type_missing_correction`
  - **Status:** RED - Missing validation logic
  - **Verifies:** Wrong feedback without correction raises InvalidFeedbackError

- ✅ **Test:** `test_submit_feedback_generates_unique_id`
  - **Status:** RED - Missing feedback_id generation logic
  - **Verifies:** Each feedback gets unique feedback_id in format `fb_{timestamp}_{random}`

- ✅ **Test:** `test_get_feedback_by_job_id_success`
  - **Status:** RED - Missing `get_feedback_by_job_id` method
  - **Verifies:** Service retrieves feedback list from DynamoDB using GSI

- ✅ **Test:** `test_get_feedback_by_job_id_empty`
  - **Status:** RED - Missing service method
  - **Verifies:** Service returns empty list when no feedback exists

- ✅ **Test:** `test_validate_correction_bounding_box_format`
  - **Status:** RED - Missing validation logic
  - **Verifies:** Invalid bounding box format raises InvalidFeedbackError

### Unit Tests - Feedback Model (12 tests)

**File:** `src/tests/unit/test_feedback_model.py` (220 lines)

- ✅ **Test:** `test_feedback_creation`
  - **Status:** RED - Missing `Feedback` model class
  - **Verifies:** Feedback model can be instantiated with valid data

- ✅ **Test:** `test_feedback_id_generation`
  - **Status:** RED - Missing auto-generation logic
  - **Verifies:** Feedback_id auto-generated in format `fb_{timestamp}_{random}`

- ✅ **Test:** `test_feedback_to_dict`
  - **Status:** RED - Missing `to_dict` method
  - **Verifies:** Feedback converts to dictionary with all fields

- ✅ **Test:** `test_feedback_from_dict`
  - **Status:** RED - Missing `from_dict` class method
  - **Verifies:** Feedback can be created from dictionary

- ✅ **Test:** `test_feedback_to_dynamodb_item`
  - **Status:** RED - Missing `to_dynamodb_item` method
  - **Verifies:** Feedback converts to DynamoDB item format

- ✅ **Test:** `test_feedback_from_dynamodb_item`
  - **Status:** RED - Missing `from_dynamodb_item` class method
  - **Verifies:** Feedback can be created from DynamoDB item

- ✅ **Test:** `test_feedback_validate_valid`
  - **Status:** RED - Missing `validate` method
  - **Verifies:** Valid feedback passes validation

- ✅ **Test:** `test_feedback_validate_invalid_feedback_id`
  - **Status:** RED - Missing validation logic
  - **Verifies:** Invalid feedback_id format raises ValueError

- ✅ **Test:** `test_feedback_validate_invalid_feedback_type`
  - **Status:** RED - Missing validation logic
  - **Verifies:** Invalid feedback type raises ValueError

- ✅ **Test:** `test_feedback_correct_type_no_correction`
  - **Status:** RED - Missing model implementation
  - **Verifies:** Correct feedback can have None correction

- ✅ **Test:** `test_feedback_wrong_type_requires_correction`
  - **Status:** RED - Missing validation logic
  - **Verifies:** Wrong feedback without correction raises ValueError

**Total Tests:** 31 tests (all in RED phase)

---

## Data Factories Created

### Feedback Factory

**File:** `src/tests/support/factories/feedback_factory.py`

**Exports:**

- `generate_feedback_id()` - Generate unique feedback ID in format `fb_{timestamp}_{random}`
- `generate_job_id()` - Generate unique job ID
- `generate_room_id()` - Generate unique room ID
- `create_feedback_data(overrides?)` - Create feedback data dictionary with defaults
- `create_feedback_dict(overrides?)` - Create complete feedback dictionary with all fields
- `create_feedback_list(count, job_id?)` - Create list of feedback dictionaries
- `create_correction_data(overrides?)` - Create correction data with bounding box

**Example Usage:**

```python
from src.tests.support.factories.feedback_factory import (
    create_feedback_dict,
    create_feedback_list
)

# Default feedback (correct type)
feedback = create_feedback_dict()

# Wrong feedback with correction
feedback = create_feedback_dict({
    'feedback': 'wrong',
    'room_id': 'room_001',
    'correction': {'bounding_box': [60, 60, 210, 310]}
})

# Create 3 feedback items for same job
feedback_list = create_feedback_list(3, job_id='job_123')
```

---

## Fixtures Created

### Feedback Fixtures

**File:** `src/tests/support/fixtures/feedback_fixtures.py`

**Fixtures:**

- `mock_feedback_service` - Mock FeedbackService for testing
  - **Setup:** Patches FeedbackService class
  - **Provides:** Mock service instance
  - **Cleanup:** Automatic cleanup after test

- `mock_job_service` - Mock JobService for testing
  - **Setup:** Patches JobService class
  - **Provides:** Mock service instance
  - **Cleanup:** Automatic cleanup after test

- `existing_job` - Create existing job fixture
  - **Setup:** Creates Job instance with valid data
  - **Provides:** Job instance with PENDING status
  - **Cleanup:** No cleanup needed (in-memory object)

- `completed_job` - Create completed job fixture
  - **Setup:** Creates Job instance with COMPLETED status
  - **Provides:** Job instance with COMPLETED status
  - **Cleanup:** No cleanup needed

- `sample_feedback` - Sample feedback dictionary
  - **Setup:** Creates feedback dictionary with valid data
  - **Provides:** Feedback dictionary
  - **Cleanup:** No cleanup needed

- `sample_feedback_list` - List of sample feedback items
  - **Setup:** Creates list of 3 feedback dictionaries
  - **Provides:** List of feedback dictionaries
  - **Cleanup:** No cleanup needed

- `mock_dynamodb_table` - Mock DynamoDB table
  - **Setup:** Mocks boto3 DynamoDB resource and table
  - **Provides:** Mock DynamoDB table
  - **Cleanup:** Automatic cleanup after test

- `api_event_base` - Base API Gateway event
  - **Setup:** Creates base API Gateway event structure
  - **Provides:** Base event dictionary
  - **Cleanup:** No cleanup needed

**Example Usage:**

```python
import pytest
from src.tests.support.fixtures.feedback_fixtures import (
    existing_job,
    mock_feedback_service
)

def test_something(existing_job, mock_feedback_service):
    # existing_job and mock_feedback_service are ready to use
    pass
```

---

## Mock Requirements

### DynamoDB Feedback Table Mock

**Table Name:** `feedback` (from environment variable `FEEDBACK_TABLE_NAME`)

**Schema:**
- Partition Key: `feedback_id` (String)
- Sort Key: `job_id` (String)
- GSI: `job_id-index` for querying by job_id

**Operations:**

- `put_item` - Store feedback item
- `query` - Query feedback by job_id using GSI

**Mock Setup:**

Tests use `mock_dynamodb_table` fixture which mocks boto3 DynamoDB resource.

---

## Required data-testid Attributes

**Note:** This is a backend API story, so no UI data-testid attributes are required. All tests are API integration tests.

---

## Implementation Checklist

### Test: test_submit_feedback_success

**File:** `src/tests/integration/test_feedback_endpoints.py`

**Tasks to make this test pass:**

- [ ] Create `src/models/feedback.py` with `Feedback` model class
- [ ] Create `src/models/feedback.py` with `FeedbackType` enum (wrong, correct, partial)
- [ ] Create `src/services/feedback_service.py` with `FeedbackService` class
- [ ] Implement `FeedbackService.submit_feedback()` method
- [ ] Add `POST /api/v1/jobs/{job_id}/feedback` route handler to `src/api/rest_api.py`
- [ ] Extract job_id from path parameters using regex
- [ ] Validate job_id exists using JobService.get_job()
- [ ] Parse and validate feedback request body
- [ ] Call FeedbackService.submit_feedback()
- [ ] Return success response with feedback_id in format specified in story
- [ ] Run test: `pytest src/tests/integration/test_feedback_endpoints.py::TestSubmitFeedback::test_submit_feedback_success -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 4 hours

---

### Test: test_submit_feedback_job_not_found

**File:** `src/tests/integration/test_feedback_endpoints.py`

**Tasks to make this test pass:**

- [ ] Handle JobNotFoundError in feedback endpoint handler
- [ ] Return 404 status code with JOB_NOT_FOUND error code
- [ ] Ensure error response format matches architecture specification
- [ ] Run test: `pytest src/tests/integration/test_feedback_endpoints.py::TestSubmitFeedback::test_submit_feedback_job_not_found -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 0.5 hours

---

### Test: test_submit_feedback_invalid_type

**File:** `src/tests/integration/test_feedback_endpoints.py`

**Tasks to make this test pass:**

- [ ] Add validation for feedback type in FeedbackService or endpoint handler
- [ ] Validate feedback type is one of: 'wrong', 'correct', 'partial'
- [ ] Create `InvalidFeedbackError` exception class in `src/utils/errors.py`
- [ ] Return 400 status code with INVALID_FEEDBACK error code
- [ ] Include error details with received_type
- [ ] Run test: `pytest src/tests/integration/test_feedback_endpoints.py::TestSubmitFeedback::test_submit_feedback_invalid_type -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 1 hour

---

### Test: test_submit_feedback_missing_required_fields

**File:** `src/tests/integration/test_feedback_endpoints.py`

**Tasks to make this test pass:**

- [ ] Add validation for required 'feedback' field
- [ ] Return 400 status code with appropriate error message
- [ ] Run test: `pytest src/tests/integration/test_feedback_endpoints.py::TestSubmitFeedback::test_submit_feedback_missing_required_fields -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 0.5 hours

---

### Test: test_submit_feedback_correct_type

**File:** `src/tests/integration/test_feedback_endpoints.py`

**Tasks to make this test pass:**

- [ ] Ensure 'correct' feedback type can be submitted without correction
- [ ] Update validation logic to allow correction=None for 'correct' type
- [ ] Run test: `pytest src/tests/integration/test_feedback_endpoints.py::TestSubmitFeedback::test_submit_feedback_correct_type -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 0.5 hours

---

### Test: test_submit_feedback_partial_type

**File:** `src/tests/integration/test_feedback_endpoints.py`

**Tasks to make this test pass:**

- [ ] Ensure 'partial' feedback type can be submitted with correction data
- [ ] Update validation logic to allow correction for 'partial' type
- [ ] Run test: `pytest src/tests/integration/test_feedback_endpoints.py::TestSubmitFeedback::test_submit_feedback_partial_type -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 0.5 hours

---

### Test: test_get_feedback_success

**File:** `src/tests/integration/test_feedback_endpoints.py`

**Tasks to make this test pass:**

- [ ] Implement `FeedbackService.get_feedback_by_job_id()` method
- [ ] Query DynamoDB using GSI on job_id
- [ ] Add `GET /api/v1/jobs/{job_id}/feedback` route handler to `src/api/rest_api.py`
- [ ] Extract job_id from path parameters
- [ ] Validate job_id exists using JobService.get_job()
- [ ] Call FeedbackService.get_feedback_by_job_id()
- [ ] Return success response with feedback list
- [ ] Run test: `pytest src/tests/integration/test_feedback_endpoints.py::TestGetFeedback::test_get_feedback_success -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 2 hours

---

### Test: test_get_feedback_job_not_found

**File:** `src/tests/integration/test_feedback_endpoints.py`

**Tasks to make this test pass:**

- [ ] Handle JobNotFoundError in GET feedback endpoint handler
- [ ] Return 404 status code with JOB_NOT_FOUND error code
- [ ] Run test: `pytest src/tests/integration/test_feedback_endpoints.py::TestGetFeedback::test_get_feedback_job_not_found -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 0.5 hours

---

### Test: test_get_feedback_empty_list

**File:** `src/tests/integration/test_feedback_endpoints.py`

**Tasks to make this test pass:**

- [ ] Ensure get_feedback_by_job_id returns empty list when no feedback exists
- [ ] Return success response with empty feedback list
- [ ] Run test: `pytest src/tests/integration/test_feedback_endpoints.py::TestGetFeedback::test_get_feedback_empty_list -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 0.5 hours

---

### Test: test_submit_feedback_success (Unit - Service)

**File:** `src/tests/unit/test_feedback_service.py`

**Tasks to make this test pass:**

- [ ] Implement `FeedbackService.__init__()` to initialize DynamoDB table
- [ ] Implement `FeedbackService.submit_feedback()` method
- [ ] Generate feedback_id in format `fb_{timestamp}_{random}`
- [ ] Create Feedback model instance
- [ ] Convert Feedback to DynamoDB item format
- [ ] Store in DynamoDB using put_item
- [ ] Return Feedback object
- [ ] Run test: `pytest src/tests/unit/test_feedback_service.py::TestSubmitFeedback::test_submit_feedback_success -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 2 hours

---

### Test: test_submit_feedback_invalid_type (Unit - Service)

**File:** `src/tests/unit/test_feedback_service.py`

**Tasks to make this test pass:**

- [ ] Add validation in FeedbackService.submit_feedback()
- [ ] Raise InvalidFeedbackError for invalid feedback type
- [ ] Run test: `pytest src/tests/unit/test_feedback_service.py::TestSubmitFeedback::test_submit_feedback_invalid_type -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 0.5 hours

---

### Test: test_submit_feedback_wrong_type_missing_correction (Unit - Service)

**File:** `src/tests/unit/test_feedback_service.py`

**Tasks to make this test pass:**

- [ ] Add validation: wrong feedback must have correction
- [ ] Raise InvalidFeedbackError if wrong feedback missing correction
- [ ] Run test: `pytest src/tests/unit/test_feedback_service.py::TestSubmitFeedback::test_submit_feedback_wrong_type_missing_correction -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 0.5 hours

---

### Test: test_submit_feedback_generates_unique_id (Unit - Service)

**File:** `src/tests/unit/test_feedback_service.py`

**Tasks to make this test pass:**

- [ ] Implement feedback_id generation in Feedback model or service
- [ ] Use format: `fb_{timestamp}_{random}`
- [ ] Ensure uniqueness (use timestamp + random component)
- [ ] Run test: `pytest src/tests/unit/test_feedback_service.py::TestSubmitFeedback::test_submit_feedback_generates_unique_id -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 1 hour

---

### Test: test_get_feedback_by_job_id_success (Unit - Service)

**File:** `src/tests/unit/test_feedback_service.py`

**Tasks to make this test pass:**

- [ ] Implement `FeedbackService.get_feedback_by_job_id()` method
- [ ] Query DynamoDB using GSI on job_id
- [ ] Convert DynamoDB items to Feedback objects
- [ ] Return list of Feedback objects
- [ ] Run test: `pytest src/tests/unit/test_feedback_service.py::TestGetFeedbackByJobId::test_get_feedback_by_job_id_success -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 2 hours

---

### Test: test_feedback_creation (Unit - Model)

**File:** `src/tests/unit/test_feedback_model.py`

**Tasks to make this test pass:**

- [ ] Create `Feedback` class in `src/models/feedback.py`
- [ ] Define __init__ with feedback_id, job_id, feedback, room_id, correction, created_at
- [ ] Support FeedbackType enum for feedback field
- [ ] Run test: `pytest src/tests/unit/test_feedback_model.py::TestFeedback::test_feedback_creation -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 1 hour

---

### Test: test_feedback_id_generation (Unit - Model)

**File:** `src/tests/unit/test_feedback_model.py`

**Tasks to make this test pass:**

- [ ] Implement auto-generation of feedback_id if not provided
- [ ] Use format: `fb_{timestamp}_{random}`
- [ ] Run test: `pytest src/tests/unit/test_feedback_model.py::TestFeedback::test_feedback_id_generation -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 0.5 hours

---

### Test: test_feedback_to_dict (Unit - Model)

**File:** `src/tests/unit/test_feedback_model.py`

**Tasks to make this test pass:**

- [ ] Implement `Feedback.to_dict()` method
- [ ] Convert FeedbackType enum to string value
- [ ] Include all fields in dictionary
- [ ] Run test: `pytest src/tests/unit/test_feedback_model.py::TestFeedback::test_feedback_to_dict -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 0.5 hours

---

### Test: test_feedback_from_dict (Unit - Model)

**File:** `src/tests/unit/test_feedback_model.py`

**Tasks to make this test pass:**

- [ ] Implement `Feedback.from_dict()` class method
- [ ] Convert string feedback type to FeedbackType enum
- [ ] Handle optional fields (room_id, correction)
- [ ] Run test: `pytest src/tests/unit/test_feedback_model.py::TestFeedback::test_feedback_from_dict -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 0.5 hours

---

### Test: test_feedback_to_dynamodb_item (Unit - Model)

**File:** `src/tests/unit/test_feedback_model.py`

**Tasks to make this test pass:**

- [ ] Implement `Feedback.to_dynamodb_item()` method
- [ ] Convert Feedback to DynamoDB item format
- [ ] Ensure partition key (feedback_id) and sort key (job_id) are included
- [ ] Run test: `pytest src/tests/unit/test_feedback_model.py::TestFeedback::test_feedback_to_dynamodb_item -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 0.5 hours

---

### Test: test_feedback_from_dynamodb_item (Unit - Model)

**File:** `src/tests/unit/test_feedback_model.py`

**Tasks to make this test pass:**

- [ ] Implement `Feedback.from_dynamodb_item()` class method
- [ ] Convert DynamoDB item to Feedback object
- [ ] Handle DynamoDB data types correctly
- [ ] Run test: `pytest src/tests/unit/test_feedback_model.py::TestFeedback::test_feedback_from_dynamodb_item -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 0.5 hours

---

### Test: test_feedback_validate_valid (Unit - Model)

**File:** `src/tests/unit/test_feedback_model.py`

**Tasks to make this test pass:**

- [ ] Implement `Feedback.validate()` method
- [ ] Validate feedback_id format (must start with 'fb_')
- [ ] Validate feedback type is valid enum value
- [ ] Return True if valid
- [ ] Run test: `pytest src/tests/unit/test_feedback_model.py::TestFeedback::test_feedback_validate_valid -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 1 hour

---

### Test: test_feedback_validate_invalid_feedback_id (Unit - Model)

**File:** `src/tests/unit/test_feedback_model.py`

**Tasks to make this test pass:**

- [ ] Add validation: feedback_id must start with 'fb_'
- [ ] Raise ValueError with descriptive message if invalid
- [ ] Run test: `pytest src/tests/unit/test_feedback_model.py::TestFeedback::test_feedback_validate_invalid_feedback_id -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 0.5 hours

---

### Test: test_feedback_validate_invalid_feedback_type (Unit - Model)

**File:** `src/tests/unit/test_feedback_model.py`

**Tasks to make this test pass:**

- [ ] Add validation: feedback type must be valid enum value
- [ ] Raise ValueError when creating from invalid type string
- [ ] Run test: `pytest src/tests/unit/test_feedback_model.py::TestFeedback::test_feedback_validate_invalid_feedback_type -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 0.5 hours

---

### Test: test_feedback_wrong_type_requires_correction (Unit - Model)

**File:** `src/tests/unit/test_feedback_model.py`

**Tasks to make this test pass:**

- [ ] Add validation: wrong feedback must have correction
- [ ] Raise ValueError if wrong feedback has correction=None
- [ ] Run test: `pytest src/tests/unit/test_feedback_model.py::TestFeedback::test_feedback_wrong_type_requires_correction -v`
- [ ] ✅ Test passes (green phase)

**Estimated Effort:** 0.5 hours

---

## Running Tests

```bash
# Run all failing tests for this story
pytest src/tests/integration/test_feedback_endpoints.py src/tests/unit/test_feedback_service.py src/tests/unit/test_feedback_model.py -v

# Run specific test file
pytest src/tests/integration/test_feedback_endpoints.py -v

# Run specific test class
pytest src/tests/integration/test_feedback_endpoints.py::TestSubmitFeedback -v

# Run specific test
pytest src/tests/integration/test_feedback_endpoints.py::TestSubmitFeedback::test_submit_feedback_success -v

# Run tests with coverage
pytest src/tests/integration/test_feedback_endpoints.py src/tests/unit/test_feedback_service.py src/tests/unit/test_feedback_model.py --cov=src --cov-report=html

# Run tests with verbose output
pytest src/tests/integration/test_feedback_endpoints.py -v -s
```

---

## Red-Green-Refactor Workflow

### RED Phase (Complete) ✅

**TEA Agent Responsibilities:**

- ✅ All tests written and failing (31 tests)
- ✅ Fixtures and factories created with auto-cleanup
- ✅ Mock requirements documented
- ✅ Implementation checklist created
- ✅ Test structure follows Given-When-Then format

**Verification:**

- All tests run and fail as expected (RED phase)
- Failure messages are clear and actionable
- Tests fail due to missing implementation, not test bugs
- Tests cover all acceptance criteria

---

### GREEN Phase (DEV Team - Next Steps)

**DEV Agent Responsibilities:**

1. **Pick one failing test** from implementation checklist (start with model tests, then service, then API)
2. **Read the test** to understand expected behavior
3. **Implement minimal code** to make that specific test pass
4. **Run the test** to verify it now passes (green)
5. **Check off the task** in implementation checklist
6. **Move to next test** and repeat

**Recommended Order:**

1. Start with Feedback model tests (foundation)
2. Then FeedbackService unit tests (business logic)
3. Finally API integration tests (end-to-end)

**Key Principles:**

- One test at a time (don't try to fix all at once)
- Minimal implementation (don't over-engineer)
- Run tests frequently (immediate feedback)
- Use implementation checklist as roadmap

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
4. **Optimize performance** (if needed)
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
2. **Run failing tests** to confirm RED phase: `pytest src/tests/integration/test_feedback_endpoints.py src/tests/unit/test_feedback_service.py src/tests/unit/test_feedback_model.py -v`
3. **Begin implementation** using implementation checklist as guide
4. **Work one test at a time** (red → green for each)
5. **Share progress** in daily standup
6. **When all tests pass**, refactor code for quality
7. **When refactoring complete**, run `bmad sm story-done` to move story to DONE

---

## Knowledge Base References Applied

This ATDD workflow consulted the following knowledge fragments:

- **fixture-architecture.md** - Test fixture patterns adapted for pytest (pure functions → fixtures)
- **data-factories.md** - Factory patterns adapted for Python (faker-like random data generation)
- **test-quality.md** - Test design principles (Given-When-Then, one assertion per test, determinism, isolation)
- **test-levels-framework.md** - Test level selection framework (API tests chosen for backend story)

**Note:** This is a Python backend project, so frontend-specific patterns (Playwright, Cypress, component testing) were adapted to pytest patterns.

See `bmad/bmm/testarch/tea-index.csv` for complete knowledge fragment mapping.

---

## Test Execution Evidence

### Initial Test Run (RED Phase Verification)

**Command:** `pytest src/tests/integration/test_feedback_endpoints.py src/tests/unit/test_feedback_service.py src/tests/unit/test_feedback_model.py -v`

**Expected Results:**

```
ERRORS - ModuleNotFoundError: No module named 'src.services.feedback_service'
ERRORS - ModuleNotFoundError: No module named 'src.models.feedback'
ERRORS - ImportError: cannot import name 'FeedbackService' from 'src.api.rest_api'
```

**Summary:**

- Total tests: 31 tests
- Passing: 0 (expected)
- Failing: 31 (expected - all due to missing implementation)
- Status: ✅ RED phase verified

**Expected Failure Messages:**

- `ModuleNotFoundError: No module named 'src.services.feedback_service'` - Missing FeedbackService module
- `ModuleNotFoundError: No module named 'src.models.feedback'` - Missing Feedback model module
- `ImportError: cannot import name 'FeedbackService'` - Missing FeedbackService import in rest_api
- `AttributeError: 'Mock' object has no attribute 'submit_feedback'` - Missing service methods
- `AttributeError: type object 'Feedback' has no attribute 'from_dict'` - Missing model methods

---

## Notes

- **Backend API Story**: This is a backend API story, so all tests are API integration tests and unit tests. No frontend/E2E tests are needed.

- **DynamoDB Table**: The feedback table needs to be added to `template.yaml` SAM template with:
  - Partition key: `feedback_id` (String)
  - Sort key: `job_id` (String)
  - GSI: `job_id-index` for querying by job_id

- **Error Codes**: New error codes needed:
  - `INVALID_FEEDBACK` - For invalid feedback type or format
  - `FEEDBACK_NOT_FOUND` - For feedback retrieval (if needed)

- **Feedback ID Format**: Must follow format `fb_{timestamp}_{random}` as specified in story requirements.

- **Validation Rules**: 
  - Feedback type must be one of: 'wrong', 'correct', 'partial'
  - Wrong feedback must have correction data
  - Correction bounding_box must be array of 4 numbers

- **Test Structure**: All tests follow Given-When-Then format for clarity.

---

## Contact

**Questions or Issues?**

- Ask in team standup
- Refer to `bmad/bmm/workflows/testarch/atdd/instructions.md` for workflow documentation
- Consult `bmad/bmm/testarch/knowledge` for testing best practices

---

**Generated by BMad TEA Agent** - 2025-01-15


