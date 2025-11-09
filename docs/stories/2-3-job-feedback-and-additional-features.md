# Story 2.3: Job Feedback and Additional Features

Status: ready-for-dev

## Story

As a developer,
I want a feedback endpoint and additional job management features,
So that users can provide feedback and the system supports additional use cases.

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

## Tasks / Subtasks

- [ ] Task 1: Create feedback endpoint handler (AC: #1, #2, #4)
  - [ ] Add `POST /api/v1/jobs/{job_id}/feedback` route to `src/api/rest_api.py`
  - [ ] Extract job_id from path parameters
  - [ ] Validate job_id exists in DynamoDB
  - [ ] Parse and validate feedback request body
  - [ ] Generate request_id and log request
  - [ ] Call feedback service to store feedback
  - [ ] Return success response with feedback_id
  - [ ] Handle error cases (job not found, invalid feedback format)
  - [ ] Test: Verify feedback endpoint accepts valid requests
  - [ ] Test: Verify feedback endpoint rejects invalid requests

- [ ] Task 2: Create feedback service for storing feedback (AC: #1, #2)
  - [ ] Create `src/services/feedback_service.py` service class
  - [ ] Implement `submit_feedback()` method
  - [ ] Generate unique feedback_id (format: `fb_{timestamp}_{random}`)
  - [ ] Validate feedback format (feedback type, room_id if applicable, correction data)
  - [ ] Store feedback in DynamoDB `feedback` table
  - [ ] Associate feedback with job_id
  - [ ] Store timestamp and metadata
  - [ ] Test: Verify feedback is stored correctly in DynamoDB
  - [ ] Test: Verify feedback validation works correctly

- [ ] Task 3: Create feedback data model (AC: #1, #2)
  - [ ] Create `src/models/feedback.py` with Feedback model class
  - [ ] Define feedback data structure: feedback_id, job_id, feedback type, room_id, correction, created_at
  - [ ] Implement `to_dynamodb_item()` method
  - [ ] Implement `from_dynamodb_item()` method
  - [ ] Add validation for feedback type (`wrong`, `correct`, `partial`)
  - [ ] Add validation for correction data structure
  - [ ] Test: Verify feedback model serialization/deserialization
  - [ ] Test: Verify feedback model validation

- [ ] Task 4: Create DynamoDB feedback table in SAM template (AC: #1, #2)
  - [ ] Add `FeedbackTable` resource to `template.yaml`
  - [ ] Configure partition key: `feedback_id` (String)
  - [ ] Configure sort key: `job_id` (String)
  - [ ] Add GSI for querying feedback by job_id
  - [ ] Configure TTL attribute (optional, for data retention)
  - [ ] Configure IAM permissions for Lambda functions
  - [ ] Test: Verify table is created correctly on deployment

- [ ] Task 5: Implement feedback retrieval functionality (AC: #3)
  - [ ] Add `GET /api/v1/jobs/{job_id}/feedback` route to `src/api/rest_api.py`
  - [ ] Query DynamoDB for feedback associated with job_id
  - [ ] Return list of feedback items
  - [ ] Support pagination if needed
  - [ ] Test: Verify feedback retrieval works correctly
  - [ ] Test: Verify pagination works correctly

- [ ] Task 6: Enhance error handling for feedback endpoint (AC: #4)
  - [ ] Add custom error codes: `INVALID_FEEDBACK`, `FEEDBACK_NOT_FOUND`
  - [ ] Validate feedback type is one of allowed values
  - [ ] Validate correction data structure if provided
  - [ ] Return appropriate HTTP status codes (400 for validation errors, 404 for not found)
  - [ ] Return user-friendly error messages
  - [ ] Test: Verify error handling for invalid feedback
  - [ ] Test: Verify error handling for missing job

- [ ] Task 7: Update job service to support feedback association (AC: #1, #2)
  - [ ] Add method to retrieve feedback count for a job
  - [ ] Optionally include feedback summary in job status response
  - [ ] Test: Verify feedback association with jobs

- [ ] Task 8: Add feedback validation rules (AC: #2, #4)
  - [ ] Validate feedback type: must be `wrong`, `correct`, or `partial`
  - [ ] Validate room_id: must exist in job results if provided
  - [ ] Validate correction: must have valid bounding_box format if feedback is `wrong`
  - [ ] Validate correction bounding_box coordinates are within blueprint bounds
  - [ ] Test: Verify all validation rules work correctly

- [ ] Task 9: Update tests for feedback functionality (AC: #1-4)
  - [ ] Create unit tests for feedback service
  - [ ] Create unit tests for feedback model
  - [ ] Create integration tests for feedback endpoint
  - [ ] Create integration tests for feedback retrieval
  - [ ] Test error scenarios (invalid feedback, job not found)
  - [ ] Mock DynamoDB for testing
  - [ ] Test: Verify all tests pass with new functionality

- [ ] Task 10: Update API documentation (AC: #1-4)
  - [ ] Document feedback endpoint in API documentation
  - [ ] Include request/response examples
  - [ ] Document error codes and error responses
  - [ ] Document feedback data model
  - [ ] Test: Verify API documentation is accurate

## Dev Notes

### Architecture Patterns and Constraints

This story implements the feedback endpoint for job management, building upon the REST API enhancements from Story 2.1 and the job management infrastructure from Story 1.2. The implementation follows the architecture document's decision to use REST API endpoints for job operations, maintaining consistency with established patterns for request routing, error handling, and response formatting.

**Key Architecture Decisions:**
- **REST API Endpoint:** Use `POST /api/v1/jobs/{job_id}/feedback` for feedback submission [Source: docs/architecture.md#API-Contracts]
- **Data Storage:** Store feedback in DynamoDB `feedback` table with partition key `feedback_id` and sort key `job_id` [Source: docs/tech-spec-epic-2.md#Data-Models-and-Contracts]
- **Feedback Format:** Use standardized feedback format with type (`wrong`, `correct`, `partial`), room_id, and correction data [Source: docs/tech-spec-epic-2.md#Data-Models-and-Contracts]
- **Error Handling:** Follow established error response format from architecture.md [Source: docs/architecture.md#Error-Handling]
- **Request ID:** Include request_id in all responses for tracing [Source: docs/architecture.md#Format-Patterns]

**Feedback Request Format:**
```json
{
  "feedback": "wrong",
  "room_id": "room_001",
  "correction": {
    "bounding_box": [60, 60, 210, 310]
  }
}
```

**Feedback Response Format:**
```json
{
  "status": "success",
  "data": {
    "feedback_id": "fb_abc123",
    "job_id": "job_20240115_abc123",
    "message": "Feedback submitted successfully",
    "request_id": "req_xyz789"
  },
  "meta": {
    "request_id": "req_xyz789",
    "api_version": "v1"
  }
}
```

**Error Response Format:**
```json
{
  "status": "error",
  "error": {
    "code": "INVALID_FEEDBACK",
    "message": "Feedback type must be 'wrong', 'correct', or 'partial'",
    "details": {
      "received_type": "invalid"
    }
  },
  "meta": {
    "request_id": "req_xyz789"
  }
}
```

### Project Structure Notes

The feedback functionality should integrate seamlessly with the existing AWS SAM project structure:

```
src/
├── api/
│   └── rest_api.py          # REST API handler (add feedback endpoint)
├── services/
│   ├── job_service.py       # Job management service (from Story 1.2)
│   └── feedback_service.py  # NEW: Feedback service
├── models/
│   ├── job.py               # Job data models (from Story 1.2)
│   └── feedback.py          # NEW: Feedback data model
└── utils/
    ├── logging.py            # Structured logging (already exists)
    ├── errors.py            # Error handling utilities (already exists)
    └── retry.py             # Retry logic (already exists)
```

[Source: docs/architecture.md#Project-Structure]

**Naming Conventions:**
- Feedback ID format: `fb_{timestamp}_{random}` [Source: docs/tech-spec-epic-2.md#Data-Models-and-Contracts]
- DynamoDB table: `feedback` [Source: docs/tech-spec-epic-2.md#DynamoDB-Schema]
- API endpoint: `/api/v1/jobs/{job_id}/feedback` [Source: docs/architecture.md#API-Contracts]

### Learnings from Previous Story

**From Story 2-2-websocket-api-and-real-time-progress-updates (Status: ready-for-dev)**

Story 2.2 implemented the WebSocket API for real-time progress updates, including connection management, message sending, and integration with pipeline stages. The following patterns and decisions from that story should be maintained:

- **Request ID Generation:** Story 2.2 uses request ID generation format `req_{timestamp}_{random}`. Feedback endpoint should include request IDs for tracing [Source: docs/stories/2-2-websocket-api-and-real-time-progress-updates.md#Architecture-Patterns-and-Constraints]
- **Error Handling:** Story 2.2 established standardized error response format. Feedback error messages should follow similar patterns [Source: docs/stories/2-2-websocket-api-and-real-time-progress-updates.md#Architecture-Patterns-and-Constraints]
- **Structured Logging:** Story 2.2 uses structured JSON logging with request_id, job_id, and correlation_id. Feedback service should use the same logging utilities [Source: docs/stories/2-2-websocket-api-and-real-time-progress-updates.md#Dev-Notes]
- **DynamoDB Patterns:** Story 2.2 created `websocket_connections` table with partition key and sort key. Feedback table should follow similar pattern [Source: docs/stories/2-2-websocket-api-and-real-time-progress-updates.md#Dev-Notes]
- **Service Structure:** Story 2.2 created `src/services/websocket_service.py` following service pattern. Feedback service should follow same structure [Source: docs/stories/2-2-websocket-api-and-real-time-progress-updates.md#Project-Structure-Notes]

**Key Files to Reuse:**
- `src/utils/logging.py` - Use existing structured logging for feedback operations
- `src/utils/errors.py` - Use existing error classes, add feedback-specific error codes if needed
- `src/api/rest_api.py` - Add feedback endpoint following existing REST API patterns
- `src/services/job_service.py` - Integrate with job service to validate job_id exists

**New Files Created in Previous Story (to be updated when Story 2-2 is completed):**
- When Story 2-2 is marked as done, review its Dev Agent Record File List section and update this section to reference any NEW files created (e.g., `src/api/websocket_api.py`, `src/services/websocket_service.py`, `src/models/websocket_connection.py`) that may be relevant for feedback implementation patterns.

### Testing Standards

**Unit Testing:**
- Test feedback service submission logic
- Test feedback model validation and serialization
- Test feedback validation rules
- Test error handling for invalid feedback

**Integration Testing:**
- Test feedback endpoint end-to-end with mocked DynamoDB
- Test feedback retrieval functionality
- Test feedback association with jobs
- Test error scenarios (invalid feedback, job not found)

**Test Structure:**
```
src/tests/
├── unit/
│   ├── test_feedback_service.py    # Test feedback service
│   └── test_feedback_model.py      # Test feedback model
├── integration/
│   └── test_feedback_endpoints.py  # Test feedback endpoints end-to-end
```

[Source: docs/architecture.md#Project-Structure]

**Test Coverage:**
- Target: 80% code coverage for feedback components
- All acceptance criteria must have corresponding tests
- Edge cases: Invalid feedback formats, missing jobs, invalid room_ids, invalid correction data

### References

- [Source: docs/stories/PRD.md] - Product requirements document with overall project goals and feature requirements
- [Source: docs/epics.md#Story-2.3-Job-Feedback-and-Additional-Features] - Story acceptance criteria and technical notes
- [Source: docs/tech-spec-epic-2.md#APIs-and-Interfaces] - Technical specification and detailed API contracts
- [Source: docs/tech-spec-epic-2.md#Data-Models-and-Contracts] - Feedback data model specification
- [Source: docs/architecture.md#API-Contracts] - REST API architecture and response formats
- [Source: docs/architecture.md#Error-Handling] - Error handling patterns and error codes
- [Source: docs/stories/2-2-websocket-api-and-real-time-progress-updates.md] - Previous story with WebSocket API implementation

## Dev Agent Record

### Context Reference

- docs/stories/2-3-job-feedback-and-additional-features.context.xml

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

## Change Log

- 2025-01-15: Story created (drafted)
- 2025-11-08: Enhanced References section with explicit PRD citation and added placeholder for previous story file references

