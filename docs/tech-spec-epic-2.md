# Epic Technical Specification: API Gateway & Job Management

Date: 2025-01-15
Author: BMad
Epic ID: 2
Status: Draft

---

## Overview

Epic 2: API Gateway & Job Management builds upon the foundational infrastructure established in Epic 1, enhancing the REST API with improved routing, error handling, and request management capabilities, and introducing a WebSocket API for real-time progress updates. This epic focuses on creating robust API endpoints and job management services that support the multi-stage processing pipeline and enable seamless integration with frontend applications.

This epic aligns with the PRD requirements for REST API endpoints (FR-005), job status tracking (FR-008), input validation (FR-007), and real-time progress updates (FR-009 - Growth feature). The epic enhances the core job management functionality delivered in Story 1.2, adding WebSocket support for real-time communication and additional job management features including feedback submission.

## Objectives and Scope

**In-Scope:**
- Enhanced REST API handler with improved routing and request management
- Request ID generation and logging for all endpoints
- Enhanced error handling and response formatting
- Support for multiple API versions
- Enhanced job service with additional job management logic
- Enhanced job data models with additional fields
- Improved input validation for file formats and sizes
- Enhanced error handling for edge cases
- WebSocket API implementation with API Gateway WebSocket integration
- Connection management (connect, disconnect, send message)
- Progress update message format per architecture specification
- Job ID association with WebSocket connections
- WebSocket service for sending messages
- Integration with pipeline stages to send progress updates
- Message queuing for reliable delivery
- Error handling for failed message sends
- Job feedback endpoint (`POST /api/v1/jobs/{job_id}/feedback`)
- Feedback storage and validation
- Additional job management features as needed

**Out-of-Scope:**
- AI/ML processing logic (deferred to Epic 3)
- Multi-stage processing pipeline implementation (deferred to Epic 3)
- Caching service implementation (deferred to Epic 4)
- Frontend application development (deferred to Epic 5)
- Comprehensive testing strategy (deferred to Epic 6)
- Production deployment configuration (deferred to Epic 6)

## System Architecture Alignment

This epic extends the API Gateway and job management components established in Epic 1, implementing the REST API enhancements and WebSocket API defined in the architecture document. The implementation follows the architecture's decision to use API Gateway v2 (HTTP API) for REST endpoints and API Gateway WebSocket API for real-time updates, maintaining consistency with the established patterns for request routing, error handling, and response formatting.

The epic delivers the API components referenced in the architecture's project structure, including enhanced `src/api/rest_api.py` REST API handler, new `src/api/websocket_api.py` WebSocket API handler, enhanced `src/services/job_service.py` job management service, enhanced `src/models/job.py` data models, and new `src/services/websocket_service.py` WebSocket service. The implementation aligns with the architecture's API contracts, message formats, and connection management patterns, ensuring seamless integration with the processing pipeline in Epic 3.

## Detailed Design

### Services and Modules

| Service/Module | Responsibility | Inputs | Outputs | Owner |
|----------------|----------------|--------|---------|-------|
| **REST API Handler** (`src/api/rest_api.py`) | Enhanced REST API routing, request ID generation, error handling, response formatting | HTTP requests (POST, GET, DELETE) | HTTP responses (JSON) | API Team |
| **WebSocket API Handler** (`src/api/websocket_api.py`) | WebSocket connection management, message routing | WebSocket events (connect, disconnect, message) | WebSocket messages | API Team |
| **Job Service** (`src/services/job_service.py`) | Enhanced job management logic, concurrent request handling | Job operations (create, get, cancel, update) | Job data models | Backend Team |
| **WebSocket Service** (`src/services/websocket_service.py`) | WebSocket message sending, connection management, retry logic | Progress updates, job status | WebSocket messages | Backend Team |
| **Job Model** (`src/models/job.py`) | Enhanced job data models with additional fields | Job data | Job data models | Backend Team |

### Data Models and Contracts

**Enhanced Job Model:**
```python
{
    "job_id": "job_20240115_abc123",
    "status": "processing",
    "stage": "stage_1",
    "progress": 50,
    "message": "Detecting walls...",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:15Z",
    "estimated_seconds_remaining": 15,
    "result_s3_key": "cache/final/job_20240115_abc123/results.json",
    "blueprint_s3_key": "blueprints/job_20240115_abc123/blueprint.pdf",
    "blueprint_format": "pdf",
    "blueprint_hash": "abc123def456",
    "request_id": "req_xyz789",
    "correlation_id": "corr_abc123",
    "api_version": "v1"
}
```

**WebSocket Connection Model:**
```python
{
    "connection_id": "conn_abc123",
    "job_id": "job_20240115_abc123",
    "created_at": "2024-01-15T10:30:00Z",
    "last_activity": "2024-01-15T10:30:15Z",
    "status": "connected"
}
```

**Feedback Model:**
```python
{
    "feedback_id": "fb_abc123",
    "job_id": "job_20240115_abc123",
    "feedback": "wrong",
    "room_id": "room_001",
    "correction": {
        "bounding_box": [60, 60, 210, 310]
    },
    "created_at": "2024-01-15T10:35:00Z"
}
```

**DynamoDB Schema:**

**Table: `jobs` (Enhanced)**
- **Partition Key:** `job_id` (string)
- **Attributes:**
  - `status` (string): `pending`, `processing`, `stage_1_complete`, `stage_2_complete`, `completed`, `failed`, `cancelled`
  - `stage` (string): Current processing stage
  - `progress` (number): 0-100
  - `message` (string): Status message
  - `request_id` (string): Request ID for tracing
  - `correlation_id` (string): Correlation ID for distributed tracing
  - `api_version` (string): API version used
  - `created_at` (string): ISO 8601 timestamp
  - `updated_at` (string): ISO 8601 timestamp
  - `result_s3_key` (string): S3 key for final results
  - `blueprint_s3_key` (string): S3 key for uploaded blueprint
  - `estimated_seconds_remaining` (number): Estimated time remaining
- **TTL:** 7 days

**Table: `websocket_connections` (New)**
- **Partition Key:** `connection_id` (string)
- **Sort Key:** `job_id` (string)
- **Attributes:**
  - `created_at` (string): ISO 8601 timestamp
  - `last_activity` (string): ISO 8601 timestamp
  - `status` (string): `connected`, `disconnected`
- **TTL:** 1 hour (auto-cleanup disconnected connections)

**Table: `feedback` (New)**
- **Partition Key:** `feedback_id` (string)
- **Sort Key:** `job_id` (string)
- **Attributes:**
  - `feedback` (string): Feedback type (`wrong`, `correct`, `partial`)
  - `room_id` (string): Room ID if applicable
  - `correction` (map): Correction data if applicable
  - `created_at` (string): ISO 8601 timestamp

### APIs and Interfaces

**REST API Endpoints:**

**1. Enhanced Create Job**
- **Method:** `POST`
- **Path:** `/api/v1/jobs`
- **Request:**
```json
{
  "blueprint": {
    "file": "base64_encoded_file_or_url",
    "format": "png|jpg|pdf"
  },
  "options": {
    "preview_only": false,
    "model_version": "1.0.0"
  }
}
```
- **Response:**
```json
{
  "status": "success",
  "data": {
    "job_id": "job_20240115_abc123",
    "status": "processing",
    "created_at": "2024-01-15T10:30:00Z",
    "request_id": "req_xyz789"
  },
  "meta": {
    "request_id": "req_xyz789",
    "api_version": "v1"
  }
}
```

**2. Enhanced Get Job Status**
- **Method:** `GET`
- **Path:** `/api/v1/jobs/{job_id}`
- **Response:**
```json
{
  "status": "success",
  "data": {
    "job_id": "job_20240115_abc123",
    "status": "stage_2_complete",
    "stage": "intermediate",
    "progress": 66,
    "message": "Refining room boundaries...",
    "estimated_seconds_remaining": 10,
    "results": {
      "rooms": [...]
    },
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:15Z",
    "request_id": "req_xyz789"
  },
  "meta": {
    "request_id": "req_xyz789",
    "api_version": "v1"
  }
}
```

**3. Enhanced Cancel Job**
- **Method:** `DELETE`
- **Path:** `/api/v1/jobs/{job_id}`
- **Response:**
```json
{
  "status": "success",
  "data": {
    "job_id": "job_20240115_abc123",
    "status": "cancelled",
    "message": "Job cancelled successfully",
    "request_id": "req_xyz789"
  },
  "meta": {
    "request_id": "req_xyz789",
    "api_version": "v1"
  }
}
```

**4. Submit Feedback (New)**
- **Method:** `POST`
- **Path:** `/api/v1/jobs/{job_id}/feedback`
- **Request:**
```json
{
  "feedback": "wrong",
  "room_id": "room_001",
  "correction": {
    "bounding_box": [60, 60, 210, 310]
  }
}
```
- **Response:**
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

**Error Codes:**
- `INVALID_FILE_FORMAT` - File format not supported
- `FILE_TOO_LARGE` - File exceeds size limit (50MB)
- `JOB_NOT_FOUND` - Job ID not found
- `JOB_ALREADY_COMPLETED` - Job already completed or cancelled
- `INVALID_FEEDBACK` - Invalid feedback format
- `SERVICE_UNAVAILABLE` - AWS service unavailable
- `RATE_LIMIT_EXCEEDED` - Too many requests

**WebSocket API:**

**Connection URL:** `wss://{api-id}.execute-api.{region}.amazonaws.com/api/v1/ws`

**Message Types:**

**1. Progress Update (Server → Client):**
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

**2. Stage Complete (Server → Client):**
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

**3. Job Complete (Server → Client):**
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

**4. Cancel Job (Client → Server):**
```json
{
  "type": "cancel_job",
  "job_id": "job_20240115_abc123"
}
```

**5. Request Status (Client → Server):**
```json
{
  "type": "request_status",
  "job_id": "job_20240115_abc123"
}
```

### Workflows and Sequencing

**Job Creation Workflow:**
1. Client sends POST request to `/api/v1/jobs` with blueprint file
2. REST API handler generates request ID and logs request
3. REST API handler validates file format and size
4. REST API handler calls job service to create job
5. Job service generates job ID, calculates blueprint hash, uploads to S3
6. Job service creates DynamoDB record with status `pending`
7. REST API handler returns job ID and status
8. Job is queued for processing (Epic 3)

**WebSocket Connection Workflow:**
1. Client connects to WebSocket endpoint
2. WebSocket API handler receives `$connect` event
3. Handler stores connection ID in DynamoDB
4. Client sends `subscribe` message with job ID
5. Handler associates connection ID with job ID
6. Handler sends confirmation message to client
7. Processing stages send progress updates via WebSocket service
8. WebSocket service retrieves connection IDs for job ID
9. WebSocket service sends messages via API Gateway Management API
10. On disconnect, handler cleans up connection records

**Progress Update Workflow:**
1. Processing stage completes (Epic 3)
2. Stage calls WebSocket service to send progress update
3. WebSocket service queries DynamoDB for connection IDs associated with job ID
4. WebSocket service sends message via API Gateway Management API
5. If send fails, service logs error and retries (doesn't block processing)
6. Client receives progress update message
7. Client updates UI with progress information

**Feedback Submission Workflow:**
1. Client sends POST request to `/api/v1/jobs/{job_id}/feedback`
2. REST API handler validates feedback format
3. REST API handler calls job service to store feedback
4. Job service creates feedback record in DynamoDB
5. REST API handler returns success response

## Non-Functional Requirements

### Performance

- **API Response Time:** REST API endpoints must respond within 1 second for 95% of requests (excluding processing time)
- **WebSocket Message Latency:** Progress updates must be delivered within 500ms of stage completion
- **Concurrent Connections:** System must support at least 100 concurrent WebSocket connections per job
- **Request Throughput:** REST API must handle at least 100 requests/second
- **Connection Cleanup:** Disconnected WebSocket connections must be cleaned up within 1 hour

**Performance Targets:**
- REST API endpoint response: <1 second (p95)
- WebSocket message delivery: <500ms (p95)
- Connection establishment: <200ms (p95)
- Feedback submission: <500ms (p95)

### Security

- **Authentication:** API endpoints must implement authentication (API key or token) per NFR-007
- **Authorization:** IAM roles must follow least privilege principle
- **Encryption:** All API communication must use HTTPS/TLS per NFR-005
- **Input Validation:** All inputs must be validated to prevent injection attacks
- **Rate Limiting:** API must implement rate limiting per NFR-010
- **WebSocket Security:** WebSocket connections must be authenticated and authorized
- **Connection Isolation:** WebSocket connections must be isolated per job ID

**Security Requirements:**
- API key authentication for REST API
- WebSocket connection authentication
- Input validation for all endpoints
- Rate limiting: 100 requests/second per API key
- HTTPS/TLS for all API communication

### Reliability/Availability

- **System Availability:** 99.5% availability during business hours per NFR-014
- **Error Handling:** Graceful error handling and degradation per NFR-015
- **Retry Logic:** Automatic retry for transient failures per NFR-016
- **WebSocket Reliability:** Failed message sends must not block processing
- **Connection Recovery:** Clients must be able to reconnect and resume progress updates

**Reliability Targets:**
- System availability: 99.5% during business hours
- WebSocket message delivery success rate: >99%
- REST API success rate: >99.5%
- Automatic retry for transient failures (exponential backoff)

### Observability

- **Logging:** Structured JSON logging with request IDs, job IDs, and correlation IDs
- **Metrics:** CloudWatch metrics for API request counts, response times, error rates
- **Tracing:** Request ID and correlation ID for distributed tracing
- **WebSocket Metrics:** Connection counts, message delivery rates, failure rates
- **Alerting:** CloudWatch alarms for error rates, latency, and availability

**Observability Requirements:**
- Structured JSON logs with request_id, job_id, correlation_id
- CloudWatch metrics: API request count, response time, error rate
- WebSocket metrics: Connection count, message delivery rate, failure rate
- CloudWatch alarms: Error rate >1%, latency >1s, availability <99.5%

## Dependencies and Integrations

**External Dependencies:**
- **boto3** (>=1.28.0,<2.0.0) - AWS SDK for Python
- **botocore** (>=1.31.0,<2.0.0) - AWS SDK core library

**AWS Service Dependencies:**
- **API Gateway v2 (HTTP API)** - REST API endpoints
- **API Gateway WebSocket API** - WebSocket connections
- **DynamoDB** - Job status, WebSocket connections, feedback storage
- **S3** - Blueprint file storage (from Epic 1)
- **Lambda** - API handlers and services
- **IAM** - Permissions and roles
- **CloudWatch** - Logging and monitoring
- **Parameter Store** - Configuration (from Epic 1)
- **Secrets Manager** - Secrets (from Epic 1)

**Internal Dependencies:**
- **Epic 1:** Job management API, DynamoDB tables, S3 buckets, configuration utilities, logging utilities, error handling utilities, retry utilities
- **Epic 3:** Processing pipeline stages (for progress updates)

**Integration Points:**
- REST API → Job Service → DynamoDB/S3
- WebSocket API → WebSocket Service → API Gateway Management API
- Processing Pipeline (Epic 3) → WebSocket Service → WebSocket Clients

## Acceptance Criteria (Authoritative)

1. **REST API Enhancements:**
   - Enhanced `src/api/rest_api.py` with improved routing
   - Request ID generation and logging for all endpoints
   - Enhanced error handling and response formatting
   - Support for multiple API versions
   - API responses follow the format from architecture.md
   - CORS headers configured for frontend integration
   - Request routing supports multiple endpoints

2. **Job Service Enhancements:**
   - Enhanced `src/services/job_service.py` with additional job management logic
   - Enhanced `src/models/job.py` with additional job data models
   - Improved input validation for file formats and sizes
   - Enhanced error handling for edge cases
   - Job service handles concurrent requests properly
   - Job responses include all required fields from architecture.md

3. **WebSocket API Implementation:**
   - `src/api/websocket_api.py` with API Gateway WebSocket integration
   - Connection management (connect, disconnect, send message)
   - Progress update message format from architecture.md
   - Job ID association with WebSocket connections
   - `src/services/websocket_service.py` for sending messages
   - Integration with pipeline stages to send progress updates
   - Message queuing for reliable delivery
   - Error handling for failed message sends

4. **WebSocket Functionality:**
   - Clients can connect and subscribe to job updates
   - Progress messages are sent in real-time during processing
   - Connections are cleaned up on disconnect
   - Progress updates are sent at each pipeline stage
   - Messages include stage, progress percentage, and estimated time
   - Failed message sends are logged but don't stop processing

5. **Feedback Endpoint:**
   - `POST /api/v1/jobs/{job_id}/feedback` endpoint to submit feedback
   - Feedback is stored and associated with the job
   - Feedback validation and error handling
   - Feedback is validated and stored properly
   - Feedback can be retrieved for analysis
   - Invalid feedback returns appropriate error messages

## Traceability Mapping

| AC ID | Acceptance Criteria | Spec Section | Component/API | Test Idea |
|-------|-------------------|--------------|--------------|-----------|
| AC-1 | REST API enhancements with improved routing | APIs and Interfaces | `src/api/rest_api.py` | Test request routing for all endpoints |
| AC-2 | Request ID generation and logging | Observability | `src/api/rest_api.py` | Verify request IDs in logs and responses |
| AC-3 | Enhanced error handling and response formatting | APIs and Interfaces | `src/api/rest_api.py` | Test error responses match architecture format |
| AC-4 | Support for multiple API versions | APIs and Interfaces | `src/api/rest_api.py` | Test API versioning in requests/responses |
| AC-5 | Enhanced job service with additional logic | Services and Modules | `src/services/job_service.py` | Test concurrent request handling |
| AC-6 | Enhanced job data models | Data Models | `src/models/job.py` | Test job model validation and serialization |
| AC-7 | Improved input validation | APIs and Interfaces | `src/api/rest_api.py` | Test file format and size validation |
| AC-8 | WebSocket API implementation | APIs and Interfaces | `src/api/websocket_api.py` | Test WebSocket connection lifecycle |
| AC-9 | Connection management | Workflows | `src/api/websocket_api.py` | Test connect, disconnect, message handling |
| AC-10 | Progress update message format | APIs and Interfaces | `src/services/websocket_service.py` | Test message format matches architecture |
| AC-11 | Job ID association with connections | Data Models | `websocket_connections` table | Test connection-job association |
| AC-12 | WebSocket service for sending messages | Services and Modules | `src/services/websocket_service.py` | Test message sending via API Gateway |
| AC-13 | Integration with pipeline stages | Workflows | `src/services/websocket_service.py` | Test progress updates from pipeline |
| AC-14 | Message queuing and retry | Workflows | `src/services/websocket_service.py` | Test retry logic for failed sends |
| AC-15 | Feedback endpoint | APIs and Interfaces | `src/api/rest_api.py` | Test feedback submission and validation |
| AC-16 | Feedback storage | Data Models | `feedback` table | Test feedback persistence and retrieval |

## Risks, Assumptions, Open Questions

**Risks:**

1. **WebSocket Connection Scalability**
   - **Risk:** High number of concurrent WebSocket connections may impact performance
   - **Impact:** Medium - May limit system scalability
   - **Mitigation:** Implement connection pooling, monitor connection counts, set connection limits

2. **Message Delivery Reliability**
   - **Risk:** WebSocket messages may fail to deliver, impacting user experience
   - **Impact:** Medium - Users may not receive progress updates
   - **Mitigation:** Implement retry logic, fallback to polling, log failures for monitoring

3. **API Versioning Complexity**
   - **Risk:** Multiple API versions may increase maintenance complexity
   - **Impact:** Low - Managed through proper versioning strategy
   - **Mitigation:** Use clear versioning strategy, document version lifecycle, plan deprecation

**Assumptions:**

1. **Processing Pipeline Integration:** Assumes Epic 3 will provide pipeline stages that can call WebSocket service
2. **Connection Management:** Assumes API Gateway WebSocket API handles connection lifecycle reliably
3. **Message Format:** Assumes frontend clients can parse WebSocket message format
4. **Feedback Usage:** Assumes feedback will be used for model improvement (future epic)

**Open Questions:**

1. **Q:** What is the expected maximum number of concurrent WebSocket connections per job?
   - **Answer Needed:** To determine connection limits and scaling strategy
2. **Q:** Should feedback be stored in separate table or same table as jobs?
   - **Answer Needed:** To determine data model design
3. **Q:** What is the retention policy for feedback data?
   - **Answer Needed:** To determine TTL and lifecycle policies

## Test Strategy Summary

**Test Levels:**

1. **Unit Tests:**
   - REST API handler functions (routing, request ID generation, error handling)
   - WebSocket API handler functions (connection management, message routing)
   - Job service functions (enhanced logic, concurrent handling)
   - WebSocket service functions (message sending, retry logic)
   - Job model validation and serialization
   - Feedback validation logic

2. **Integration Tests:**
   - REST API endpoints with mocked AWS services
   - WebSocket API connection lifecycle with mocked API Gateway
   - Job service integration with DynamoDB and S3
   - WebSocket service integration with API Gateway Management API
   - Feedback endpoint integration with DynamoDB

3. **End-to-End Tests:**
   - Complete job creation workflow with WebSocket subscription
   - Progress update delivery via WebSocket
   - Feedback submission and retrieval
   - Error handling and recovery scenarios

**Test Frameworks:**
- **pytest** - Python unit and integration testing
- **moto** - AWS service mocking
- **WebSocket client libraries** - WebSocket testing

**Test Coverage:**
- Target: 80% code coverage for core services
- All acceptance criteria must have corresponding tests
- Edge cases: Invalid inputs, connection failures, message delivery failures

**Edge Cases:**
- Concurrent WebSocket connections for same job
- WebSocket connection failure during processing
- Message delivery failure and retry
- Invalid feedback format
- Job cancellation during WebSocket connection
- API version mismatch

