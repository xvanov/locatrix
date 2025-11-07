# Epic Technical Specification: Foundation & Infrastructure

Date: 2025-11-07T22:12:10Z
Author: BMad
Epic ID: 1
Status: Draft

---

## Overview

Epic 1: Foundation & Infrastructure establishes the foundational AWS SAM project structure, core infrastructure resources, and deployment pipeline that enables all subsequent development work for the Location Detection AI service. This epic delivers the essential infrastructure components required for the serverless architecture, including API Gateway setup, Lambda function configuration, DynamoDB tables, S3 buckets, IAM roles, and configuration management utilities. The epic follows a vertical slicing approach, delivering working, testable functionality from the first story (health check API) through complete job management infrastructure.

This epic aligns with the PRD goal of building an AI service capable of automatically detecting room boundaries on architectural blueprints, providing the infrastructure foundation that supports the multi-stage processing pipeline, job management, and API integration requirements defined in the product requirements.

## Objectives and Scope

**In-Scope:**
- AWS SAM project initialization and structure
- API Gateway v2 (HTTP API) configuration
- Lambda function handlers for REST API
- DynamoDB tables for job status and preview caching
- S3 buckets for blueprint storage and result caching
- IAM roles and permissions for Lambda functions
- Configuration management via Parameter Store
- Secrets management via Secrets Manager
- Structured JSON logging utilities
- Error handling utilities with custom exception classes
- Retry logic with exponential backoff
- Job management service and data models
- REST API endpoints for job creation, retrieval, and cancellation
- Input validation for blueprint file formats
- CI/CD pipeline setup (GitHub Actions or AWS CodePipeline)
- Environment-specific resource naming
- S3 bucket lifecycle policies
- DynamoDB capacity settings

**Out-of-Scope:**
- AI/ML processing logic (deferred to Epic 3)
- WebSocket API implementation (deferred to Epic 2)
- Multi-stage processing pipeline (deferred to Epic 3)
- Frontend application development (deferred to Epic 5)
- Comprehensive testing strategy (deferred to Epic 6)
- Production deployment configuration (deferred to Epic 6)

## System Architecture Alignment

This epic implements the foundational components defined in the architecture document, establishing the AWS SAM project structure and core infrastructure resources. The implementation follows the architecture's decision to use AWS SAM as the starter template, Python 3.11 as the runtime, API Gateway v2 for REST API, DynamoDB for job status and preview caching, and S3 for file storage and result caching.

The epic delivers the infrastructure components referenced in the architecture's project structure, including the `template.yaml` SAM template, `src/api/rest_api.py` REST API handler, `src/services/job_service.py` job management service, `src/models/job.py` data models, and `src/utils/` utilities for configuration, secrets, logging, errors, and retry logic. The implementation aligns with the architecture's naming conventions, error handling patterns, and data model structures, ensuring consistency across all subsequent epics.

## Detailed Design

### Services and Modules

| Service/Module | Responsibility | Inputs | Outputs | Owner |
|----------------|----------------|--------|---------|-------|
| **REST API Handler** (`src/api/rest_api.py`) | Handle HTTP requests, route to appropriate handlers, format responses | HTTP request events from API Gateway | HTTP responses (JSON) | API Team |
| **Health Check Handler** (`src/api/health.py`) | Provide service health status and dependency checks | HTTP GET /health requests | Health status JSON | API Team |
| **Job Service** (`src/services/job_service.py`) | Business logic for job creation, retrieval, cancellation, status tracking | Job creation requests, job IDs | Job objects, status updates | Backend Team |
| **Config Utility** (`src/utils/config.py`) | Retrieve configuration values from Parameter Store | Config parameter names | Configuration values | Infrastructure Team |
| **Secrets Utility** (`src/utils/secrets.py`) | Retrieve secrets from Secrets Manager with caching | Secret names | Secret values | Infrastructure Team |
| **Logging Utility** (`src/utils/logging.py`) | Structured JSON logging with request/job correlation | Log messages, context | CloudWatch log entries | Infrastructure Team |
| **Error Utility** (`src/utils/errors.py`) | Custom exception classes and error handling | Error conditions | Exception objects | Backend Team |
| **Retry Utility** (`src/utils/retry.py`) | Exponential backoff retry logic for transient failures | Function calls, retry config | Function results or exceptions | Backend Team |

### Data Models and Contracts

**Job Model** (`src/models/job.py`):
```python
{
    "job_id": "job_20240115_abc123",  # String, format: job_{timestamp}_{random}
    "status": "pending",  # String: pending, processing, completed, failed, cancelled
    "created_at": "2024-01-15T10:30:00Z",  # ISO 8601 timestamp
    "updated_at": "2024-01-15T10:30:00Z",  # ISO 8601 timestamp
    "blueprint_s3_key": "blueprints/job_20240115_abc123/blueprint.pdf",  # String
    "blueprint_format": "pdf",  # String: png, jpg, pdf
    "blueprint_hash": "abc123def456",  # String, MD5 or SHA256 hash
    "result_s3_key": null,  # String or null, S3 key for results
    "error": null  # Object or null, error details if failed
}
```

**DynamoDB Table: `jobs`**
- **Partition Key:** `job_id` (String)
- **Attributes:** status, created_at, updated_at, blueprint_s3_key, blueprint_format, blueprint_hash, result_s3_key, error
- **TTL:** 7 days (auto-delete old jobs)

**DynamoDB Table: `preview_cache`**
- **Partition Key:** `blueprint_hash` (String)
- **Attributes:** rooms (list/map), timestamp, model_version, expires_at
- **TTL:** 1 hour (using expires_at attribute)

**S3 Bucket: `location-detection-{env}-blueprints`**
- **Purpose:** Store uploaded blueprint files
- **Key Format:** `blueprints/{job_id}/{filename}`
- **Lifecycle Policy:** Delete files after 30 days

**S3 Bucket: `location-detection-{env}-cache`**
- **Purpose:** Store processing results (preview, intermediate, final)
- **Key Format:** `cache/{type}/{identifier}/{filename}`
- **Lifecycle Policy:** Delete files after 30 days

### APIs and Interfaces

**REST API Endpoints:**

1. **Health Check**
   - **Method:** `GET`
   - **Path:** `/health`
   - **Handler:** `src/api/health.py`
   - **Response:** `{"status": "healthy", "services": {...}}`
   - **Status Codes:** 200 (healthy), 503 (unhealthy)

2. **Create Job**
   - **Method:** `POST`
   - **Path:** `/api/v1/jobs`
   - **Handler:** `src/api/rest_api.py` → `src/services/job_service.py`
   - **Request Body:**
     ```json
     {
       "blueprint": {
         "file": "base64_encoded_file_or_url",
         "format": "png|jpg|pdf"
       }
     }
     ```
   - **Response:** `{"status": "success", "data": {"job_id": "...", "status": "pending", ...}}`
   - **Status Codes:** 201 (created), 400 (invalid input), 500 (server error)

3. **Get Job Status**
   - **Method:** `GET`
   - **Path:** `/api/v1/jobs/{job_id}`
   - **Handler:** `src/api/rest_api.py` → `src/services/job_service.py`
   - **Response:** `{"status": "success", "data": {"job_id": "...", "status": "...", ...}}`
   - **Status Codes:** 200 (success), 404 (not found), 500 (server error)

4. **Cancel Job**
   - **Method:** `DELETE`
   - **Path:** `/api/v1/jobs/{job_id}`
   - **Handler:** `src/api/rest_api.py` → `src/services/job_service.py`
   - **Response:** `{"status": "success", "data": {"job_id": "...", "status": "cancelled", ...}}`
   - **Status Codes:** 200 (success), 404 (not found), 409 (cannot cancel), 500 (server error)

**Error Response Format:**
```json
{
  "status": "error",
  "error": {
    "code": "ERROR_CODE",
    "message": "User-friendly message",
    "details": {...}
  },
  "meta": {
    "request_id": "req_xyz789"
  }
}
```

**Error Codes:**
- `INVALID_FILE_FORMAT` - File format not supported (PNG, JPG, PDF only)
- `FILE_TOO_LARGE` - File exceeds 50MB size limit
- `JOB_NOT_FOUND` - Job ID not found
- `JOB_ALREADY_COMPLETED` - Cannot cancel completed job
- `SERVICE_UNAVAILABLE` - AWS service unavailable

### Workflows and Sequencing

**Job Creation Workflow:**
1. Client sends POST request to `/api/v1/jobs` with blueprint file
2. REST API handler validates request format and file type
3. Job service generates unique `job_id` (format: `job_{timestamp}_{random}`)
4. Job service calculates blueprint hash (MD5 or SHA256)
5. Job service uploads blueprint file to S3 bucket (`blueprints/{job_id}/{filename}`)
6. Job service creates job record in DynamoDB `jobs` table with status `pending`
7. Job service returns job_id and status to client
8. (Future: Job service triggers Step Functions state machine for processing)

**Job Retrieval Workflow:**
1. Client sends GET request to `/api/v1/jobs/{job_id}`
2. REST API handler extracts job_id from path
3. Job service queries DynamoDB `jobs` table by job_id
4. If job found, return job status and metadata
5. If job not found, return 404 error

**Job Cancellation Workflow:**
1. Client sends DELETE request to `/api/v1/jobs/{job_id}`
2. REST API handler extracts job_id from path
3. Job service queries DynamoDB `jobs` table by job_id
4. If job not found, return 404 error
5. If job status is `completed` or `failed`, return 409 error (cannot cancel)
6. Update job status to `cancelled` in DynamoDB
7. (Future: Cancel Step Functions execution if in progress)
8. Return cancellation confirmation

**Configuration Retrieval Workflow:**
1. Lambda function needs configuration value
2. Config utility checks local cache (if implemented)
3. If not cached, retrieve from Parameter Store
4. Cache value for subsequent requests
5. Return configuration value

**Secrets Retrieval Workflow:**
1. Lambda function needs secret value
2. Secrets utility checks local cache (TTL: 5 minutes)
3. If not cached or expired, retrieve from Secrets Manager
4. Cache value with TTL
5. Return secret value

## Non-Functional Requirements

### Performance

**NFR-001:** Health check endpoint must respond within 1 second (PRD NFR-003)
- **Target:** API Gateway + Lambda response time < 1 second
- **Measurement:** CloudWatch metrics for API Gateway latency
- **Implementation:** Optimize Lambda cold start, use connection pooling for DynamoDB

**NFR-002:** Job creation endpoint must respond within 3 seconds
- **Target:** File upload to S3 + DynamoDB write < 3 seconds
- **Measurement:** CloudWatch metrics for API Gateway latency
- **Implementation:** Optimize S3 upload, use DynamoDB on-demand capacity

**NFR-003:** Job retrieval endpoint must respond within 500ms
- **Target:** DynamoDB query < 500ms
- **Measurement:** CloudWatch metrics for DynamoDB read latency
- **Implementation:** Use DynamoDB on-demand capacity, optimize query patterns

**NFR-004:** System must handle blueprint files up to 50MB (PRD NFR-004)
- **Target:** Support file uploads up to 50MB
- **Measurement:** S3 upload success rate, API Gateway payload size limits
- **Implementation:** Configure API Gateway payload size limits, use S3 multipart upload for large files

### Security

**NFR-005:** All API endpoints must use HTTPS/TLS encryption (PRD NFR-005)
- **Target:** API Gateway configured with HTTPS only
- **Measurement:** API Gateway configuration, SSL certificate validation
- **Implementation:** API Gateway v2 HTTP API with HTTPS only, enforce TLS 1.2+

**NFR-006:** Uploaded blueprint files must be encrypted at rest (PRD NFR-006)
- **Target:** S3 bucket encryption enabled (SSE-S3 or SSE-KMS)
- **Measurement:** S3 bucket encryption configuration
- **Implementation:** Configure S3 bucket encryption at rest, use SSE-S3 for MVP

**NFR-007:** API must implement authentication and authorization (PRD NFR-007)
- **Target:** API key or token-based authentication (MVP), OAuth 2.0 / JWT (future)
- **Measurement:** Authentication success rate, unauthorized access attempts
- **Implementation:** API Gateway API key or custom authorizer, store tokens in Parameter Store or Secrets Manager

**NFR-008:** System must not log or store sensitive user data (PRD NFR-008)
- **Target:** Minimize data logging, exclude sensitive information
- **Measurement:** Log review, data retention compliance
- **Implementation:** Structured logging excludes sensitive data, implement data minimization

**NFR-009:** Blueprint files must be automatically deleted after processing (PRD NFR-009)
- **Target:** S3 lifecycle policy deletes files after 30 days
- **Measurement:** S3 lifecycle policy configuration, file retention compliance
- **Implementation:** Configure S3 lifecycle policies, set TTL for DynamoDB records

**NFR-010:** System must implement rate limiting (PRD NFR-010)
- **Target:** API Gateway throttling configured (1000 requests/second default)
- **Measurement:** API Gateway throttling metrics, rate limit violations
- **Implementation:** Configure API Gateway throttling, implement per-user rate limits (future)

**NFR-011:** System must comply with data privacy regulations (PRD NFR-011)
- **Target:** GDPR/CCPA compliance for data handling
- **Measurement:** Data retention policies, user data deletion capabilities
- **Implementation:** Implement data retention policies, support user data deletion requests

**NFR-012:** System must maintain audit logs (PRD NFR-012)
- **Target:** CloudWatch logs for all API requests and job operations
- **Measurement:** CloudWatch log retention, audit log completeness
- **Implementation:** Structured JSON logging with request IDs, CloudWatch log retention policies

### Reliability/Availability

**NFR-014:** System availability must be at least 99.5% during business hours (PRD NFR-014)
- **Target:** 99.5% uptime during business hours
- **Measurement:** CloudWatch availability metrics, API Gateway uptime
- **Implementation:** Use managed AWS services (API Gateway, Lambda, DynamoDB, S3), implement retry logic for transient failures

**NFR-015:** System must implement error handling and graceful degradation (PRD NFR-015)
- **Target:** Graceful error handling, user-friendly error messages
- **Measurement:** Error rate, error recovery success rate
- **Implementation:** Custom exception classes, structured error responses, retry logic for transient failures

**NFR-016:** System must support automatic retry mechanisms (PRD NFR-016)
- **Target:** Exponential backoff retry (1s, 2s, 4s, 8s), max 3-5 retries
- **Measurement:** Retry success rate, retry attempt counts
- **Implementation:** Retry utility with exponential backoff, configurable retry limits

### Observability

**NFR-017:** System must implement structured logging (Architecture requirement)
- **Target:** JSON-formatted logs with request IDs, job IDs, correlation IDs
- **Measurement:** Log format compliance, log completeness
- **Implementation:** Structured JSON logging utility, CloudWatch Logs integration

**NFR-018:** System must track key metrics (Architecture requirement)
- **Target:** CloudWatch metrics for API requests, job operations, errors
- **Measurement:** CloudWatch metrics availability, metric completeness
- **Implementation:** CloudWatch custom metrics, API Gateway metrics, Lambda metrics

**NFR-019:** System must support monitoring and alerting (Architecture requirement)
- **Target:** CloudWatch alarms for critical errors, performance degradation
- **Measurement:** Alert response time, alert accuracy
- **Implementation:** CloudWatch alarms, SNS notifications for critical alerts

## Dependencies and Integrations

**Python Dependencies (requirements.txt):**
- `boto3>=1.28.0,<2.0.0` - AWS SDK for Python
- `botocore>=1.31.0,<2.0.0` - Low-level AWS service client
- `python-dateutil>=2.8.0,<3.0.0` - Date/time utilities
- `requests>=2.31.0,<3.0.0` - HTTP library (if needed for external integrations)

**AWS Services:**
- **API Gateway v2 (HTTP API)** - REST API endpoint
- **Lambda** (Python 3.11 runtime) - Serverless compute
- **DynamoDB** - Job status storage and preview caching
- **S3** - Blueprint file storage and result caching
- **Parameter Store** - Configuration management
- **Secrets Manager** - Secrets management
- **CloudWatch** - Logging and monitoring
- **IAM** - Roles and permissions

**External Integrations:**
- None for Epic 1 (future: Step Functions, SQS, SageMaker, Textract in later epics)

**Development Dependencies:**
- **AWS SAM CLI** >=1.100.0 - Infrastructure as code and deployment
- **AWS CLI** >=2.13.0 - AWS service management
- **Python 3.11** - Runtime language
- **pytest>=7.4.0,<8.0.0** (dev) - Testing framework
- **moto>=4.2.0,<5.0.0** (dev) - AWS service mocking for tests

**Infrastructure Dependencies:**
- **CloudFormation** (via SAM) - Resource provisioning
- **Git** - Version control
- **GitHub Actions** (or AWS CodePipeline) - CI/CD pipeline

## Acceptance Criteria (Authoritative)

1. **Story 1.1: Deploy Health Check API with Project Setup**
   - Given AWS CLI and SAM CLI are installed
   - When the project is initialized and health check endpoint is deployed
   - Then `template.yaml` exists with API Gateway v2 (HTTP API) and Lambda function
   - And `samconfig.toml` exists for deployment configuration
   - And `requirements.txt` exists for Python dependencies
   - And `src/api/rest_api.py` exists with health check handler
   - And `GET /health` endpoint returns 200 status with service information
   - And `.gitignore` is configured for Python and SAM
   - And the project can be built with `sam build`
   - And the project can be deployed to AWS with `sam deploy --guided`
   - And the health endpoint can be tested end-to-end via API Gateway
   - And CORS headers are configured for frontend integration

2. **Story 1.2: Deploy Complete Job Management API with Infrastructure**
   - Given the health check API is deployed
   - When infrastructure resources, configuration, logging, and job management API are deployed
   - Then DynamoDB table `jobs` exists with partition key `job_id` (String)
   - And DynamoDB table `preview_cache` exists with partition key `blueprint_hash` (String)
   - And S3 bucket `location-detection-{env}-blueprints` exists for uploaded files
   - And S3 bucket `location-detection-{env}-cache` exists for processing results
   - And IAM roles exist with appropriate permissions for Lambda functions
   - And `src/utils/config.py` exists for Parameter Store integration
   - And `src/utils/secrets.py` exists for Secrets Manager integration
   - And `src/utils/logging.py` exists with structured JSON logging
   - And `src/utils/errors.py` exists with custom exception classes
   - And `src/utils/retry.py` exists with exponential backoff retry logic
   - And `src/services/job_service.py` exists with job management logic
   - And `src/models/job.py` exists with job data models
   - And `POST /api/v1/jobs` endpoint creates jobs with blueprint file upload
   - And `GET /api/v1/jobs/{job_id}` endpoint retrieves job status
   - And `DELETE /api/v1/jobs/{job_id}` endpoint cancels jobs
   - And input validation exists for file formats (PNG, JPG, PDF)
   - And job status tracking exists in DynamoDB
   - And all resources use environment variables for naming (`{env}` = dev/prod)
   - And S3 buckets have lifecycle policies configured
   - And DynamoDB tables have appropriate read/write capacity settings
   - And configuration values can be retrieved at runtime
   - And secrets are cached to reduce API calls
   - And logs include request IDs, job IDs, and correlation IDs
   - And jobs are stored in DynamoDB with unique job_id
   - And blueprint files are uploaded to S3 with proper organization
   - And job creation, retrieval, and cancellation can be tested end-to-end via API Gateway
   - And invalid file formats and job IDs return appropriate error messages
   - And cancelled jobs cannot be resumed

3. **Story 1.3: CI/CD Pipeline Setup**
   - Given the SAM project is set up
   - When the CI/CD pipeline is configured
   - Then GitHub Actions workflow (or equivalent) exists for automated builds
   - And automated testing exists before deployment
   - And deployment to dev environment occurs on merge to main
   - And deployment to prod environment occurs on tagged releases
   - And the pipeline runs `sam build` and `sam deploy`
   - And tests are executed before deployment
   - And deployment status is reported back to the pull request

## Traceability Mapping

| AC | Spec Section | Component(s)/API(s) | Test Idea |
|----|--------------|---------------------|-----------|
| AC-1.1.1 | Services and Modules | `template.yaml`, API Gateway v2, Lambda | Verify SAM template validates, API Gateway and Lambda resources exist |
| AC-1.1.2 | APIs and Interfaces | `GET /health`, `src/api/health.py` | Test health endpoint returns 200 with service status |
| AC-1.1.3 | Workflows and Sequencing | `sam build`, `sam deploy` | Verify project builds and deploys successfully |
| AC-1.2.1 | Data Models and Contracts | DynamoDB table `jobs`, `preview_cache` | Verify tables exist with correct schema and partition keys |
| AC-1.2.2 | Data Models and Contracts | S3 buckets `location-detection-{env}-blueprints`, `location-detection-{env}-cache` | Verify buckets exist with lifecycle policies |
| AC-1.2.3 | Services and Modules | `src/utils/config.py`, Parameter Store | Test configuration retrieval from Parameter Store |
| AC-1.2.4 | Services and Modules | `src/utils/secrets.py`, Secrets Manager | Test secrets retrieval with caching from Secrets Manager |
| AC-1.2.5 | Services and Modules | `src/utils/logging.py`, CloudWatch | Verify structured JSON logs with request IDs |
| AC-1.2.6 | Services and Modules | `src/utils/errors.py` | Test custom exception classes and error handling |
| AC-1.2.7 | Services and Modules | `src/utils/retry.py` | Test exponential backoff retry logic |
| AC-1.2.8 | APIs and Interfaces | `POST /api/v1/jobs`, `src/services/job_service.py` | Test job creation with blueprint file upload |
| AC-1.2.9 | APIs and Interfaces | `GET /api/v1/jobs/{job_id}` | Test job retrieval by job_id |
| AC-1.2.10 | APIs and Interfaces | `DELETE /api/v1/jobs/{job_id}` | Test job cancellation |
| AC-1.2.11 | Workflows and Sequencing | Input validation | Test file format validation (PNG, JPG, PDF) |
| AC-1.2.12 | Workflows and Sequencing | Job status tracking | Test job status updates in DynamoDB |
| AC-1.3.1 | Workflows and Sequencing | CI/CD pipeline | Test automated build and deployment on merge to main |
| AC-1.3.2 | Workflows and Sequencing | CI/CD pipeline | Test automated testing before deployment |
| AC-1.3.3 | Workflows and Sequencing | CI/CD pipeline | Test deployment status reporting to pull request |

## Risks, Assumptions, Open Questions

**Risks:**

1. **Risk: AWS Service Limits and Quotas**
   - **Impact:** High - May prevent deployment or cause service failures
   - **Probability:** Medium
   - **Mitigation:** Review AWS service limits early, request quota increases if needed, implement error handling for quota exceeded errors

2. **Risk: Lambda Cold Start Performance**
   - **Impact:** Medium - May affect health check response time requirement (< 1 second)
   - **Probability:** Medium
   - **Mitigation:** Optimize Lambda package size, use provisioned concurrency for critical endpoints, monitor cold start times

3. **Risk: DynamoDB Capacity Planning**
   - **Impact:** Medium - May cause throttling or increased costs
   - **Probability:** Low
   - **Mitigation:** Use on-demand capacity for MVP, monitor usage patterns, switch to provisioned capacity if needed

4. **Risk: S3 Bucket Naming Conflicts**
   - **Impact:** Low - May prevent deployment in some AWS accounts
   - **Probability:** Low
   - **Mitigation:** Use environment-specific naming, check bucket availability before deployment

5. **Risk: CI/CD Pipeline Configuration Complexity**
   - **Impact:** Medium - May delay deployment automation
   - **Probability:** Medium
   - **Mitigation:** Start with simple GitHub Actions workflow, iterate on complexity, document deployment procedures

**Assumptions:**

1. **Assumption:** AWS account has appropriate permissions for creating resources (API Gateway, Lambda, DynamoDB, S3, IAM)
   - **Validation:** Verify AWS account permissions before deployment
   - **Contingency:** Request additional permissions or use separate deployment account

2. **Assumption:** AWS SAM CLI and AWS CLI are installed and configured
   - **Validation:** Verify CLI versions and AWS credentials before deployment
   - **Contingency:** Provide installation and configuration instructions

3. **Assumption:** Python 3.11 runtime is available in AWS Lambda
   - **Validation:** Verify Python 3.11 availability in target AWS region
   - **Contingency:** Use Python 3.10 if 3.11 is not available

4. **Assumption:** Blueprint files will be uploaded via base64 encoding or S3 pre-signed URLs
   - **Validation:** Confirm file upload method with frontend team
   - **Contingency:** Support both methods if needed

**Open Questions:**

1. **Question:** What is the expected concurrent job creation rate?
   - **Impact:** Affects DynamoDB capacity planning and API Gateway throttling configuration
   - **Next Step:** Gather usage estimates from product team, configure throttling accordingly

2. **Question:** Should authentication be implemented in Epic 1 or deferred to Epic 2?
   - **Impact:** Affects API Gateway configuration and security implementation
   - **Next Step:** Confirm with security team, implement basic API key authentication if needed

3. **Question:** What is the retention period for job records in DynamoDB?
   - **Impact:** Affects TTL configuration and storage costs
   - **Next Step:** Confirm with product team, set TTL to 7 days as default

4. **Question:** Should CI/CD pipeline support blue/green deployments?
   - **Impact:** Affects deployment strategy and rollback capabilities
   - **Next Step:** Confirm with DevOps team, implement basic deployment first, add blue/green later if needed

## Test Strategy Summary

**Test Levels:**

1. **Unit Tests:**
   - **Scope:** Individual functions and classes in `src/utils/`, `src/services/`, `src/models/`
   - **Framework:** pytest
   - **Coverage Target:** 80% for core services
   - **Examples:**
     - Test configuration retrieval from Parameter Store
     - Test secrets retrieval with caching
     - Test retry logic with exponential backoff
     - Test job model validation
     - Test error handling and exception classes

2. **Integration Tests:**
   - **Scope:** API endpoints, DynamoDB operations, S3 operations
   - **Framework:** pytest with moto (AWS service mocking)
   - **Coverage Target:** All API endpoints and critical workflows
   - **Examples:**
     - Test health check endpoint
     - Test job creation with file upload
     - Test job retrieval by job_id
     - Test job cancellation
     - Test input validation for file formats
     - Test error handling for invalid inputs

3. **End-to-End Tests:**
   - **Scope:** Complete workflows from API request to DynamoDB/S3 storage
   - **Framework:** pytest with localstack or test AWS account
   - **Coverage Target:** Critical user workflows
   - **Examples:**
     - Test complete job creation workflow (API → S3 → DynamoDB)
     - Test complete job retrieval workflow (API → DynamoDB)
     - Test complete job cancellation workflow (API → DynamoDB)

**Test Frameworks:**
- **pytest** - Python testing framework
- **moto** - AWS service mocking for unit/integration tests
- **localstack** (optional) - Local AWS service emulation for E2E tests

**Test Coverage:**
- **Unit Tests:** 80% coverage for core services (`src/services/`, `src/utils/`)
- **Integration Tests:** 100% coverage for API endpoints
- **E2E Tests:** Critical workflows (job creation, retrieval, cancellation)

**Edge Cases:**
- Invalid file formats (GIF, BMP, etc.)
- File size exceeding 50MB limit
- Missing or invalid job_id
- DynamoDB throttling scenarios
- S3 upload failures
- Parameter Store/Secrets Manager unavailability
- Concurrent job creation requests

**Performance Tests:**
- Health check endpoint response time (< 1 second)
- Job creation endpoint response time (< 3 seconds)
- Job retrieval endpoint response time (< 500ms)
- Concurrent job creation (10+ simultaneous requests)

