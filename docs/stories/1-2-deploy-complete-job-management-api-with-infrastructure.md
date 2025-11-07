# Story 1.2: Deploy Complete Job Management API with Infrastructure

Status: ready-for-dev

## Story

As a developer,
I want to deploy infrastructure resources, configuration management, logging, and a complete job management API,
So that users can create, retrieve, and cancel jobs with a testable, end-to-end workflow.

## Acceptance Criteria

1. **Given** The health check API is deployed
   **When** I add infrastructure resources, configuration, logging, and deploy the complete job management API
   **Then** The following are implemented:
   - DynamoDB table `jobs` with partition key `job_id` (String)
   - DynamoDB table `preview_cache` with partition key `blueprint_hash` (String)
   - S3 bucket `location-detection-{env}-blueprints` for uploaded files
   - S3 bucket `location-detection-{env}-cache` for processing results
   - IAM roles with appropriate permissions for Lambda functions
   - `src/utils/config.py` for Parameter Store integration
   - `src/utils/secrets.py` for Secrets Manager integration
   - `src/utils/logging.py` with structured JSON logging
   - `src/utils/errors.py` with custom exception classes
   - `src/utils/retry.py` with exponential backoff retry logic
   - `src/services/job_service.py` with job management logic
   - `src/models/job.py` with job data models
   - `POST /api/v1/jobs` endpoint to create jobs with blueprint file upload
   - `GET /api/v1/jobs/{job_id}` endpoint to retrieve job status
   - `DELETE /api/v1/jobs/{job_id}` endpoint to cancel jobs
   - Input validation for file formats (PNG, JPG, PDF)
   - Job status tracking in DynamoDB

2. **And** All resources use environment variables for naming (`{env}` = dev/prod)

3. **And** S3 buckets have lifecycle policies configured

4. **And** DynamoDB tables have appropriate read/write capacity settings

5. **And** Configuration values can be retrieved at runtime

6. **And** Secrets are cached to reduce API calls

7. **And** Logs include request IDs, job IDs, and correlation IDs

8. **And** Jobs are stored in DynamoDB with unique job_id

9. **And** Blueprint files are uploaded to S3 with proper organization

10. **And** Job creation, retrieval, and cancellation can be tested end-to-end via API Gateway

11. **And** Invalid file formats and job IDs return appropriate error messages

12. **And** Cancelled jobs cannot be resumed

## Tasks / Subtasks

- [ ] Task 1: Configure DynamoDB tables in SAM template (AC: #1, #4)
  - [ ] Add `jobs` table with partition key `job_id` (String) and TTL attribute
  - [ ] Add `preview_cache` table with partition key `blueprint_hash` (String) and TTL attribute
  - [ ] Configure DynamoDB billing mode (on-demand for MVP)
  - [ ] Set TTL for `jobs` table (7 days) and `preview_cache` table (1 hour)
  - [ ] Configure IAM permissions for Lambda functions to access DynamoDB tables
  - [ ] Test: Verify tables are created with correct schema and capacity settings

- [ ] Task 2: Configure S3 buckets in SAM template (AC: #1, #3)
  - [ ] Add S3 bucket `location-detection-{env}-blueprints` for uploaded files
  - [ ] Add S3 bucket `location-detection-{env}-cache` for processing results
  - [ ] Configure S3 bucket encryption at rest (SSE-S3)
  - [ ] Configure lifecycle policies to delete files after 30 days
  - [ ] Configure bucket policies for security
  - [ ] Configure IAM permissions for Lambda functions to access S3 buckets
  - [ ] Test: Verify buckets are created with encryption and lifecycle policies

- [ ] Task 3: Implement configuration utility (AC: #1, #5)
  - [ ] Create `src/utils/config.py` for Parameter Store integration
  - [ ] Implement function to retrieve configuration values from Parameter Store
  - [ ] Implement caching mechanism to reduce API calls
  - [ ] Handle errors for missing or invalid configuration values
  - [ ] Test: Unit test configuration retrieval with mocked Parameter Store

- [ ] Task 4: Implement secrets utility (AC: #1, #6)
  - [ ] Create `src/utils/secrets.py` for Secrets Manager integration
  - [ ] Implement function to retrieve secrets from Secrets Manager
  - [ ] Implement caching mechanism with TTL (5 minutes) to reduce API calls
  - [ ] Handle errors for missing or invalid secrets
  - [ ] Test: Unit test secrets retrieval with mocked Secrets Manager and caching

- [ ] Task 5: Implement logging utility (AC: #1, #7)
  - [ ] Create `src/utils/logging.py` with structured JSON logging
  - [ ] Implement JSON formatter for CloudWatch logs
  - [ ] Include request IDs, job IDs, and correlation IDs in log entries
  - [ ] Configure log levels (ERROR, WARN, INFO, DEBUG)
  - [ ] Test: Verify structured JSON logs are created with required fields

- [ ] Task 6: Implement error handling utility (AC: #1, #11)
  - [ ] Create `src/utils/errors.py` with custom exception classes
  - [ ] Implement error codes: INVALID_FILE_FORMAT, FILE_TOO_LARGE, JOB_NOT_FOUND, JOB_ALREADY_COMPLETED, SERVICE_UNAVAILABLE
  - [ ] Implement error response formatting according to architecture.md
  - [ ] Test: Unit test custom exception classes and error formatting

- [ ] Task 7: Implement retry utility (AC: #1)
  - [ ] Create `src/utils/retry.py` with exponential backoff retry logic
  - [ ] Implement exponential backoff: 1s, 2s, 4s, 8s
  - [ ] Configure max retries (3-5 retries)
  - [ ] Handle transient failures appropriately
  - [ ] Test: Unit test retry logic with mocked failures

- [ ] Task 8: Implement job data models (AC: #1)
  - [ ] Create `src/models/job.py` with job data models
  - [ ] Define Job model with fields: job_id, status, created_at, updated_at, blueprint_s3_key, blueprint_format, blueprint_hash, result_s3_key, error
  - [ ] Implement job status enum: pending, processing, completed, failed, cancelled
  - [ ] Implement job validation logic
  - [ ] Test: Unit test job model creation and validation

- [ ] Task 9: Implement job service (AC: #1, #8, #9, #12)
  - [ ] Create `src/services/job_service.py` with job management logic
  - [ ] Implement `create_job()` function: generate job_id, calculate blueprint hash, upload to S3, create DynamoDB record
  - [ ] Implement `get_job()` function: query DynamoDB by job_id
  - [ ] Implement `cancel_job()` function: update job status to cancelled, prevent cancellation of completed/failed jobs
  - [ ] Implement job_id generation: format `job_{timestamp}_{random}`
  - [ ] Implement blueprint hash calculation (MD5 or SHA256)
  - [ ] Implement S3 upload with proper key organization: `blueprints/{job_id}/{filename}`
  - [ ] Test: Unit test job service functions with mocked AWS services

- [ ] Task 10: Implement REST API endpoints (AC: #1, #10, #11)
  - [ ] Enhance `src/api/rest_api.py` with job management endpoints
  - [ ] Implement `POST /api/v1/jobs` endpoint: validate request, call job_service.create_job(), return response
  - [ ] Implement `GET /api/v1/jobs/{job_id}` endpoint: extract job_id, call job_service.get_job(), return response
  - [ ] Implement `DELETE /api/v1/jobs/{job_id}` endpoint: extract job_id, call job_service.cancel_job(), return response
  - [ ] Implement request routing based on HTTP method and path
  - [ ] Format responses according to architecture.md API response format
  - [ ] Configure CORS headers for frontend integration
  - [ ] Test: Integration test API endpoints with mocked services

- [ ] Task 11: Implement input validation (AC: #1, #11)
  - [ ] Implement file format validation: accept PNG, JPG, PDF only
  - [ ] Implement file size validation: reject files exceeding 50MB
  - [ ] Return appropriate error messages for invalid formats: INVALID_FILE_FORMAT error code
  - [ ] Return appropriate error messages for invalid job IDs: JOB_NOT_FOUND error code
  - [ ] Test: Unit test input validation logic

- [ ] Task 12: Update SAM template with API Gateway routes (AC: #1, #10)
  - [ ] Add API Gateway routes for `POST /api/v1/jobs`
  - [ ] Add API Gateway routes for `GET /api/v1/jobs/{job_id}`
  - [ ] Add API Gateway routes for `DELETE /api/v1/jobs/{job_id}`
  - [ ] Configure API Gateway integration with Lambda function
  - [ ] Configure request/response transformations
  - [ ] Test: Verify API Gateway routes are configured correctly

- [ ] Task 13: Configure IAM roles and permissions (AC: #1, #2)
  - [ ] Configure Lambda execution role with DynamoDB read/write permissions
  - [ ] Configure Lambda execution role with S3 read/write permissions
  - [ ] Configure Lambda execution role with Parameter Store read permissions
  - [ ] Configure Lambda execution role with Secrets Manager read permissions
  - [ ] Use least privilege principle for IAM permissions
  - [ ] Test: Verify IAM roles have correct permissions

- [ ] Task 14: Deploy and verify end-to-end functionality (AC: #10, #11, #12)
  - [ ] Deploy updated SAM template to AWS
  - [ ] Test job creation: POST /api/v1/jobs with valid blueprint file
  - [ ] Verify job is stored in DynamoDB with correct fields
  - [ ] Verify blueprint file is uploaded to S3 with correct key
  - [ ] Test job retrieval: GET /api/v1/jobs/{job_id}
  - [ ] Verify job status is returned correctly
  - [ ] Test job cancellation: DELETE /api/v1/jobs/{job_id}
  - [ ] Verify job status is updated to cancelled
  - [ ] Test error handling: invalid file format, invalid job ID, cancel completed job
  - [ ] Verify appropriate error messages are returned
  - [ ] Test: End-to-end test of complete job lifecycle via API Gateway

## Dev Notes

### Architecture Patterns and Constraints

This story builds upon Story 1.1's foundation and implements the complete job management infrastructure and API endpoints. The implementation follows the architecture document's decisions for DynamoDB state management, S3 file storage, Parameter Store configuration, Secrets Manager secrets, structured logging, error handling, and retry logic.

**Key Architecture Decisions:**
- **DynamoDB Tables:** Use DynamoDB for job status storage (`jobs` table) and fast preview caching (`preview_cache` table) with TTL for automatic cleanup [Source: docs/architecture.md#Data-Architecture]
- **S3 Buckets:** Use S3 for blueprint file storage (`location-detection-{env}-blueprints`) and result caching (`location-detection-{env}-cache`) with lifecycle policies [Source: docs/architecture.md#Data-Architecture]
- **Configuration Management:** Use Parameter Store for configuration values with caching to reduce API calls [Source: docs/architecture.md#Decision-Summary]
- **Secrets Management:** Use Secrets Manager for secrets with caching (TTL: 5 minutes) to reduce API calls [Source: docs/architecture.md#Decision-Summary]
- **Structured Logging:** Use structured JSON logging with request IDs, job IDs, and correlation IDs for CloudWatch integration [Source: docs/architecture.md#Consistency-Patterns]
- **Error Handling:** Use custom exception classes with error codes and user-friendly messages [Source: docs/architecture.md#Error-Handling]
- **Retry Logic:** Use exponential backoff retry (1s, 2s, 4s, 8s) with max 3-5 retries for transient failures [Source: docs/architecture.md#Decision-Summary]

**API Response Format:**
The job management endpoints should return responses in the format specified in architecture.md:
```json
{
  "status": "success",
  "data": {
    "job_id": "job_20240115_abc123",
    "status": "pending",
    "created_at": "2024-01-15T10:30:00Z"
  },
  "meta": {
    "request_id": "req_xyz789"
  }
}
```
[Source: docs/architecture.md#API-Contracts]

**Error Response Format:**
Error responses should follow the architecture's error format:
```json
{
  "status": "error",
  "error": {
    "code": "INVALID_FILE_FORMAT",
    "message": "File format must be PNG, JPG, or PDF",
    "details": {
      "received_format": "gif"
    }
  },
  "meta": {
    "request_id": "req_xyz789"
  }
}
```
[Source: docs/architecture.md#APIs-and-Interfaces]

**Job ID Generation:**
Job IDs should follow the format: `job_{timestamp}_{random}` (e.g., `job_20240115_abc123`) [Source: docs/architecture.md#Naming-Patterns]

**S3 Key Organization:**
Blueprint files should be stored with key format: `blueprints/{job_id}/{filename}` [Source: docs/architecture.md#Location-Patterns]

### Project Structure Notes

The project structure should align with the architecture document's defined structure:
```
location-detection-api/
├── template.yaml                 # SAM template with DynamoDB, S3, IAM resources
├── src/
│   ├── utils/
│   │   ├── config.py             # Parameter Store integration
│   │   ├── secrets.py            # Secrets Manager integration
│   │   ├── logging.py            # Structured JSON logging
│   │   ├── errors.py            # Custom exception classes
│   │   └── retry.py             # Exponential backoff retry logic
│   ├── services/
│   │   └── job_service.py        # Job management service
│   ├── models/
│   │   └── job.py                # Job data models
│   └── api/
│       └── rest_api.py           # REST API handler with job endpoints
```

[Source: docs/architecture.md#Project-Structure]

**Naming Conventions:**
- DynamoDB Tables: Format `{resource}s` (plural, lowercase) or `{resource}_{purpose}` (e.g., `jobs`, `preview_cache`) [Source: docs/architecture.md#Naming-Patterns]
- S3 Buckets: Format `{project}-{environment}-{purpose}` (e.g., `location-detection-dev-blueprints`) [Source: docs/architecture.md#Naming-Patterns]
- S3 Object Keys: Format `{category}/{subcategory}/{identifier}` (e.g., `blueprints/{job_id}/{filename}`) [Source: docs/architecture.md#Naming-Patterns]
- Python Modules: Format `snake_case.py` (e.g., `job_service.py`) [Source: docs/architecture.md#Naming-Patterns]
- Python Classes: Format `PascalCase` (e.g., `JobService`) [Source: docs/architecture.md#Naming-Patterns]

### Learnings from Previous Story

**From Story 1-1-deploy-health-check-api-with-project-setup (Status: in-progress)**

Story 1.1 established the foundational AWS SAM project structure and health check API endpoint. While Story 1.1 is still in progress, the following patterns and decisions from that story should be maintained:

- **Project Structure:** The SAM project structure initialized in Story 1.1 should be extended, not modified. New files should be added to existing directories (`src/utils/`, `src/services/`, `src/models/`) [Source: docs/stories/1-1-deploy-health-check-api-with-project-setup.md#Project-Structure-Notes]
- **API Gateway v2 (HTTP API):** Story 1.1 configured API Gateway v2 for the health check endpoint. Story 1.2 should add new routes to the same API Gateway, not create a new one [Source: docs/stories/1-1-deploy-health-check-api-with-project-setup.md#Architecture-Patterns-and-Constraints]
- **CORS Configuration:** Story 1.1 configured CORS headers for frontend integration. Story 1.2 should maintain the same CORS configuration [Source: docs/stories/1-1-deploy-health-check-api-with-project-setup.md#Architecture-Patterns-and-Constraints]
- **Response Format:** Story 1.1 established the API response format. Story 1.2 should follow the same format for consistency [Source: docs/stories/1-1-deploy-health-check-api-with-project-setup.md#Architecture-Patterns-and-Constraints]

**Note:** Since Story 1.1 is still in progress, there are no completion notes, file lists, or review findings to reference yet. Once Story 1.1 is completed, future stories should reference its Dev Agent Record for learnings.

### Testing Standards

**Unit Testing:**
- Use pytest for unit tests
- Test utility functions (`config.py`, `secrets.py`, `logging.py`, `errors.py`, `retry.py`) in isolation
- Test job service functions with mocked AWS services (DynamoDB, S3)
- Test job model validation logic
- Mock AWS service calls using moto library
- Target: 80% coverage for core services

**Integration Testing:**
- Test API endpoints with mocked AWS services
- Test DynamoDB operations (create, read, update)
- Test S3 operations (upload, retrieve)
- Test Parameter Store and Secrets Manager integration
- Test error handling and validation
- Verify API response formats match architecture specification

**End-to-End Testing:**
- Test complete job creation workflow: API → S3 → DynamoDB
- Test complete job retrieval workflow: API → DynamoDB
- Test complete job cancellation workflow: API → DynamoDB
- Test error scenarios: invalid file format, invalid job ID, cancel completed job
- Use localstack or test AWS account for E2E tests

**Test Structure:**
Follow the architecture's test organization:
```
src/tests/
├── unit/
│   ├── test_config.py
│   ├── test_secrets.py
│   ├── test_logging.py
│   ├── test_errors.py
│   ├── test_retry.py
│   ├── test_job_service.py
│   └── test_job_model.py
├── integration/
│   ├── test_api_endpoints.py
│   └── test_job_workflows.py
```

[Source: docs/architecture.md#Structure-Patterns]

### References

- [Source: docs/epics.md#Story-1.2-Deploy-Complete-Job-Management-API-with-Infrastructure] - Story acceptance criteria and technical notes
- [Source: docs/stories/PRD.md#FR-001-Accept-blueprint-files] - Functional requirement for accepting blueprint files
- [Source: docs/stories/PRD.md#FR-005-REST-API-endpoint] - Functional requirement for REST API endpoint
- [Source: docs/stories/PRD.md#FR-007-Input-validation] - Functional requirement for input validation
- [Source: docs/stories/PRD.md#FR-008-Job-status-tracking] - Functional requirement for job status tracking
- [Source: docs/architecture.md#Data-Architecture] - DynamoDB schema, S3 bucket structure, and data models
- [Source: docs/architecture.md#APIs-and-Interfaces] - REST API endpoint specifications and response formats
- [Source: docs/architecture.md#Decision-Summary] - Architecture decisions for DynamoDB, S3, Parameter Store, Secrets Manager, logging, error handling, retry logic
- [Source: docs/architecture.md#Naming-Patterns] - Naming conventions for DynamoDB tables, S3 buckets, Python modules, and classes
- [Source: docs/architecture.md#Error-Handling] - Error handling strategy and error codes
- [Source: docs/architecture.md#Consistency-Patterns] - Logging format and structured JSON logging requirements
- [Source: docs/tech-spec-epic-1.md#Story-1.2-Deploy-Complete-Job-Management-API-with-Infrastructure] - Technical specification and detailed acceptance criteria
- [Source: docs/tech-spec-epic-1.md#Data-Models-and-Contracts] - Job model schema and DynamoDB table definitions
- [Source: docs/tech-spec-epic-1.md#APIs-and-Interfaces] - REST API endpoint specifications and error codes
- [Source: docs/tech-spec-epic-1.md#Workflows-and-Sequencing] - Job creation, retrieval, and cancellation workflows
- [Source: docs/tech-spec-epic-1.md#Non-Functional-Requirements] - Performance, security, reliability, and observability requirements

## Dev Agent Record

### Context Reference

- docs/stories/1-2-deploy-complete-job-management-api-with-infrastructure.context.xml

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

## Change Log

- 2025-01-15: Story created (drafted)

