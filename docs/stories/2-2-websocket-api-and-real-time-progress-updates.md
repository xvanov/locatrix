# Story 2.2: WebSocket API and Real-time Progress Updates

Status: drafted

## Story

As a developer,
I want a WebSocket API with real-time progress update capabilities,
So that clients can receive real-time progress updates during processing.

## Acceptance Criteria

1. **Given** The REST API is working
   **When** I create the WebSocket API handler and service
   **Then** The following are implemented:
   - `src/api/websocket_api.py` with API Gateway WebSocket integration
   - Connection management (connect, disconnect, send message)
   - Progress update message format from architecture.md
   - Job ID association with WebSocket connections
   - `src/services/websocket_service.py` for sending messages
   - Integration with pipeline stages to send progress updates
   - Message queuing for reliable delivery
   - Error handling for failed message sends

2. **And** Clients can connect and subscribe to job updates

3. **And** Progress messages are sent in real-time during processing

4. **And** Connections are cleaned up on disconnect

5. **And** Progress updates are sent at each pipeline stage

6. **And** Messages include stage, progress percentage, and estimated time

7. **And** Failed message sends are logged but don't stop processing

## Tasks / Subtasks

- [ ] Task 1: Create WebSocket API handler with API Gateway integration (AC: #1)
  - [ ] Create `src/api/websocket_api.py` Lambda handler
  - [ ] Implement `$connect` event handler to store connection ID
  - [ ] Implement `$disconnect` event handler to clean up connections
  - [ ] Implement `$default` message handler for client messages
  - [ ] Extract connection ID from event context
  - [ ] Handle connection lifecycle events
  - [ ] Test: Verify WebSocket connection lifecycle works correctly

- [ ] Task 2: Implement connection management and job ID association (AC: #1, #2, #4)
  - [ ] Create DynamoDB table `websocket_connections` with partition key `connection_id` and sort key `job_id`
  - [ ] Store connection ID and job ID mapping on connect
  - [ ] Handle `subscribe` message from client to associate job_id with connection
  - [ ] Clean up connection records on disconnect
  - [ ] Implement TTL for connection records (1 hour)
  - [ ] Test: Verify connection management and job ID association

- [ ] Task 3: Create WebSocket service for sending messages (AC: #1, #3, #5, #6)
  - [ ] Create `src/services/websocket_service.py` service class
  - [ ] Implement `send_message()` method using API Gateway Management API
  - [ ] Query DynamoDB to find connections for a job_id
  - [ ] Send progress update messages to all connected clients
  - [ ] Format messages according to architecture.md message format
  - [ ] Include stage, progress percentage, and estimated time in messages
  - [ ] Test: Verify message sending works correctly

- [ ] Task 4: Implement progress update message formats (AC: #1, #5, #6)
  - [ ] Implement `progress_update` message type with stage, progress, message, estimated_seconds_remaining
  - [ ] Implement `stage_complete` message type with stage and results
  - [ ] Implement `job_complete` message type with final results
  - [ ] Implement `job_failed` message type with error details
  - [ ] Implement `job_cancelled` message type
  - [ ] Include timestamp in all messages
  - [ ] Test: Verify message formats match architecture specification

- [ ] Task 5: Implement message queuing and retry logic (AC: #1, #7)
  - [ ] Implement retry logic for failed message sends using existing `retry.py` utilities
  - [ ] Log failed message sends but don't stop processing
  - [ ] Handle API Gateway Management API errors gracefully
  - [ ] Implement exponential backoff for retries
  - [ ] Cache connection IDs for performance
  - [ ] Test: Verify retry logic handles failures correctly

- [ ] Task 6: Integrate with pipeline stages for progress updates (AC: #1, #5)
  - [ ] Add WebSocket service integration points in pipeline stage handlers
  - [ ] Send progress updates at start of each stage
  - [ ] Send progress updates during stage processing (if applicable)
  - [ ] Send stage_complete message when stage finishes
  - [ ] Send job_complete message when all stages complete
  - [ ] Handle job failures and send job_failed message
  - [ ] Test: Verify progress updates are sent at each pipeline stage

- [ ] Task 7: Handle client messages (subscribe, cancel_job, request_status) (AC: #2)
  - [ ] Parse incoming client messages (JSON format)
  - [ ] Handle `subscribe` message to associate job_id with connection
  - [ ] Handle `cancel_job` message to cancel job processing
  - [ ] Handle `request_status` message to send current job status
  - [ ] Validate message format and return error for invalid messages
  - [ ] Test: Verify client message handling works correctly

- [ ] Task 8: Update SAM template for WebSocket API (AC: #1)
  - [ ] Add WebSocket API Gateway resource to template.yaml
  - [ ] Configure WebSocket API routes ($connect, $disconnect, $default)
  - [ ] Add Lambda function for WebSocket handler
  - [ ] Configure IAM permissions for API Gateway Management API
  - [ ] Configure IAM permissions for DynamoDB websocket_connections table
  - [ ] Test: Verify SAM template deploys correctly

- [ ] Task 9: Create WebSocket connection model (AC: #1)
  - [ ] Create connection data model with connection_id, job_id, created_at, last_activity, status
  - [ ] Implement to_dynamodb_item() and from_dynamodb_item() methods
  - [ ] Add validation for connection data
  - [ ] Test: Verify connection model works correctly

- [ ] Task 10: Update tests for WebSocket functionality (AC: #1-7)
  - [ ] Create unit tests for WebSocket API handler
  - [ ] Create unit tests for WebSocket service
  - [ ] Create integration tests for WebSocket connection lifecycle
  - [ ] Create integration tests for message sending
  - [ ] Create integration tests for client message handling
  - [ ] Mock API Gateway Management API for testing
  - [ ] Test: Verify all tests pass with new functionality

## Dev Notes

### Architecture Patterns and Constraints

This story implements the WebSocket API for real-time progress updates, building upon the REST API enhancements from Story 2.1. The implementation follows the architecture document's decision to use API Gateway WebSocket API for real-time updates, maintaining consistency with established patterns for connection management, message formatting, and error handling.

**Key Architecture Decisions:**
- **WebSocket API:** Use API Gateway WebSocket API for real-time progress updates [Source: docs/architecture.md#Decision-Summary]
- **Connection Management:** Store connection IDs in DynamoDB mapped to job IDs [Source: docs/tech-spec-epic-2.md#Data-Models-and-Contracts]
- **Message Format:** Use standardized message format from architecture.md with type, job_id, stage, progress, message, estimated_seconds_remaining, timestamp [Source: docs/architecture.md#WebSocket-Message-Format]
- **API Gateway Management API:** Use API Gateway Management API to send messages to connected clients [Source: docs/tech-spec-epic-2.md#Technical-Notes]
- **Retry Logic:** Implement retry logic for failed message sends using existing retry utilities [Source: docs/architecture.md#Error-Handling]

**WebSocket Message Formats:**
All WebSocket messages must follow the standardized format from architecture.md:

**Progress Update:**
```json
{
  "type": "progress_update",
  "job_id": "job_20240115_abc123",
  "stage": "stage_1",
  "progress": 50,
  "message": "Detecting walls...",
  "estimated_seconds_remaining": 15,
  "timestamp": "2024-01-15T10:30:15Z"
}
```

**Stage Complete:**
```json
{
  "type": "stage_complete",
  "job_id": "job_20240115_abc123",
  "stage": "stage_1",
  "results": {
    "rooms": [...]
  },
  "timestamp": "2024-01-15T10:30:20Z"
}
```

**Job Complete:**
```json
{
  "type": "job_complete",
  "job_id": "job_20240115_abc123",
  "results": {
    "rooms": [...]
  },
  "timestamp": "2024-01-15T10:30:45Z"
}
```

**Client Messages:**
Clients can send the following message types:
- `subscribe`: Associate connection with job_id
- `cancel_job`: Cancel job processing
- `request_status`: Request current job status

**Connection Lifecycle:**
1. Client connects → `$connect` event → Store connection_id in DynamoDB
2. Client sends `subscribe` message → Associate job_id with connection_id
3. Pipeline stages send progress updates → WebSocket service sends messages to connected clients
4. Client disconnects → `$disconnect` event → Clean up connection record

### Project Structure Notes

The WebSocket API implementation should integrate seamlessly with the existing AWS SAM project structure:

```
src/
├── api/
│   ├── rest_api.py          # REST API handler (from Story 2.1)
│   └── websocket_api.py     # NEW: WebSocket API handler
├── services/
│   ├── job_service.py       # Job management service (from Story 2.1)
│   └── websocket_service.py # NEW: WebSocket message sending service
├── models/
│   ├── job.py               # Job data models (from Story 2.1)
│   └── websocket_connection.py # NEW: WebSocket connection model
└── utils/
    ├── logging.py            # Structured logging (already exists)
    ├── errors.py             # Error handling utilities (already exists)
    └── retry.py              # Retry logic (already exists)
```

[Source: docs/architecture.md#Project-Structure]

**Naming Conventions:**
- WebSocket connection ID format: `conn_{timestamp}_{random}` [Source: docs/tech-spec-epic-2.md#Data-Models-and-Contracts]
- Message type format: `progress_update`, `stage_complete`, `job_complete`, `job_failed`, `job_cancelled` [Source: docs/architecture.md#WebSocket-Message-Format]
- DynamoDB table: `websocket_connections` [Source: docs/tech-spec-epic-2.md#DynamoDB-Schema]

### Learnings from Previous Story

**From Story 2-1-rest-api-enhancements-and-job-service-improvements (Status: ready-for-dev)**

Story 2.1 enhanced the REST API handler and job service with improved routing, request ID generation, error handling, API versioning, and concurrent request handling. The following patterns and decisions from that story should be maintained:

- **Request ID Generation:** Story 2.1 implemented request ID generation format `req_{timestamp}_{random}`. WebSocket messages should include correlation IDs for tracing [Source: docs/stories/2-1-rest-api-enhancements-and-job-service-improvements.md#Architecture-Patterns-and-Constraints]
- **Error Handling:** Story 2.1 established standardized error response format. WebSocket error messages should follow similar patterns [Source: docs/stories/2-1-rest-api-enhancements-and-job-service-improvements.md#Architecture-Patterns-and-Constraints]
- **Structured Logging:** Story 2.1 uses structured JSON logging with request_id, job_id, and correlation_id. WebSocket service should use the same logging utilities [Source: docs/stories/2-1-rest-api-enhancements-and-job-service-improvements.md#Dev-Notes]
- **Retry Logic:** Story 2.1 uses existing retry utilities from `src/utils/retry.py`. WebSocket service should use the same retry logic for failed message sends [Source: docs/stories/2-1-rest-api-enhancements-and-job-service-improvements.md#Dev-Notes]
- **Job Service:** Story 2.1 enhanced `src/services/job_service.py` with additional fields (request_id, correlation_id, api_version). WebSocket service should integrate with the enhanced job service [Source: docs/stories/2-1-rest-api-enhancements-and-job-service-improvements.md#Dev-Notes]

**Key Files to Reuse:**
- `src/utils/logging.py` - Use existing structured logging for WebSocket events
- `src/utils/errors.py` - Use existing error classes, add WebSocket-specific error codes if needed
- `src/utils/retry.py` - Use existing retry logic for API Gateway Management API calls
- `src/services/job_service.py` - Integrate with enhanced job service to get job status for progress updates
- `src/models/job.py` - Use enhanced job model with additional fields

### Testing Standards

**Unit Testing:**
- Test WebSocket API handler for $connect, $disconnect, and $default events
- Test WebSocket service message sending logic
- Test connection model validation and serialization
- Test message format generation (progress_update, stage_complete, job_complete)
- Test retry logic for failed message sends
- Test error handling for invalid client messages

**Integration Testing:**
- Test WebSocket connection lifecycle end-to-end
- Test message sending to connected clients
- Test job ID association with connections
- Test connection cleanup on disconnect
- Test integration with pipeline stages (mocked)
- Test concurrent connections for same job

**Test Structure:**
```
src/tests/
├── unit/
│   ├── test_websocket_api.py      # Test WebSocket API handler
│   ├── test_websocket_service.py  # Test WebSocket service
│   └── test_websocket_connection.py # Test connection model
├── integration/
│   └── test_websocket_endpoints.py # Test WebSocket endpoints end-to-end
```

[Source: docs/architecture.md#Project-Structure]

**Test Coverage:**
- Target: 80% code coverage for WebSocket components
- All acceptance criteria must have corresponding tests
- Edge cases: Connection failures, message send failures, concurrent connections, invalid messages

### References

- [Source: docs/epics.md#Story-2.2-WebSocket-API-and-Real-time-Progress-Updates] - Story acceptance criteria and technical notes
- [Source: docs/tech-spec-epic-2.md#WebSocket-API] - Technical specification and detailed message formats
- [Source: docs/architecture.md#WebSocket-API] - WebSocket API architecture and message formats
- [Source: docs/architecture.md#Communication-Patterns] - WebSocket event types and communication patterns
- [Source: docs/stories/2-1-rest-api-enhancements-and-job-service-improvements.md] - Previous story with REST API enhancements

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

## Change Log

- 2025-01-15: Story created (drafted)

