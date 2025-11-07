# Architecture

## Executive Summary

This architecture defines a serverless, AWS-native Location Detection AI service that automatically detects room boundaries on architectural blueprints. The system uses a multi-stage processing pipeline with progressive disclosure, enabling users to see results incrementally and provide feedback before expensive computations complete. The architecture is designed for API-first integration, with a minimal test frontend and clear separation between backend services and frontend applications.

**Key Architectural Principles:**
- **Progressive Disclosure:** Multi-stage pipeline (fast preview → intermediate → final) with real-time updates
- **Async Processing:** Job-based architecture with SQS + Step Functions orchestration
- **Performance-First:** Multi-tier caching (DynamoDB + S3) for instant previews
- **API-First Design:** REST + WebSocket API for easy integration with external frontends
- **AWS-Native:** Leverages managed AWS services for scalability and reliability

## Project Initialization

**First implementation story should execute:**

```bash
sam init --runtime python3.11 --name location-detection-api --app-template hello-world
```

This establishes the base architecture with these decisions:
- **Python 3.11** runtime
- **AWS SAM** project structure
- **Lambda** function handlers
- **API Gateway** REST API integration
- **Basic IAM roles** and permissions

## Decision Summary

| Category | Decision | Version | Affects Epics | Rationale |
| -------- | -------- | ------- | ------------- | --------- |
| **Starter Template** | AWS SAM | Latest (2024) | All | AWS-native serverless development, good local testing, integrates with Step Functions |
| **API Pattern** | REST + WebSocket | API Gateway v2 | All | REST for job submission, WebSocket for real-time progress updates, supports progressive disclosure |
| **Job Queue** | SQS + Step Functions | Latest | All | SQS for job queuing, Step Functions for multi-stage orchestration, enables progressive disclosure |
| **State Management** | DynamoDB + S3 | Latest | All | DynamoDB for job status and fast preview caching, S3 for results caching (performance-critical) |
| **AI Processing** | Textract + SageMaker | Latest | AI Processing Epic | Textract for preprocessing, SageMaker with YOLOv8-seg fine-tuned model for room detection, supports fast preview + full processing |
| **Error Handling** | Basic retry with exponential backoff | N/A | All | Exponential backoff (1s, 2s, 4s, 8s), max 3-5 retries, simple and effective |
| **Monitoring** | CloudWatch only | Latest | All | Logs, metrics, alerts, cost-effective for MVP |
| **Configuration** | Parameter Store + Secrets Manager | Latest | All | Parameter Store for config, Secrets Manager for secrets, secure and scalable |
| **Python Runtime** | Python 3.11 | 3.11 | All | Latest stable Python version, good AWS Lambda support |
| **Caching Strategy** | Multi-tier (DynamoDB + S3) | Latest | Caching Epic | DynamoDB for fast preview (instant), S3 for intermediate/final results (persistent) |
| **WebSocket** | API Gateway WebSocket API | Latest | All | Real-time progress updates, bidirectional communication, supports cancellation |

## Project Structure

```
location-detection-api/
├── template.yaml                 # SAM template (infrastructure as code)
├── samconfig.toml               # SAM deployment configuration
├── .gitignore
├── README.md
├── requirements.txt             # Python dependencies
├── src/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── rest_api.py          # REST API Lambda handler
│   │   ├── websocket_api.py     # WebSocket API Lambda handler
│   │   └── health.py            # Health check handler
│   ├── services/
│   │   ├── __init__.py
│   │   ├── job_service.py       # Job management service
│   │   ├── textract_service.py  # Textract integration
│   │   ├── sagemaker_service.py # SageMaker model inference
│   │   ├── cache_service.py     # Caching service (DynamoDB + S3)
│   │   └── websocket_service.py # WebSocket connection management
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── step_functions.py    # Step Functions state machine definition
│   │   ├── stage_1_preview.py   # Fast preview stage Lambda
│   │   ├── stage_2_intermediate.py # Intermediate stage Lambda
│   │   └── stage_3_final.py     # Final processing stage Lambda
│   ├── models/
│   │   ├── __init__.py
│   │   ├── job.py               # Job data models
│   │   ├── blueprint.py        # Blueprint data models
│   │   └── room.py              # Room detection result models
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── config.py           # Configuration management (Parameter Store)
│   │   ├── secrets.py           # Secrets management (Secrets Manager)
│   │   ├── logging.py           # Structured logging
│   │   ├── errors.py            # Error handling utilities
│   │   └── retry.py             # Retry logic with exponential backoff
│   └── tests/
│       ├── __init__.py
│       ├── unit/
│       │   ├── test_job_service.py
│       │   ├── test_textract_service.py
│       │   └── test_sagemaker_service.py
│       ├── integration/
│       │   ├── test_api_endpoints.py
│       │   └── test_pipeline.py
│       └── fixtures/
│           └── mock_data.py
├── frontend/                    # Minimal test frontend
│   ├── package.json
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── BlueprintUpload.jsx
│   │   │   ├── JobStatus.jsx
│   │   │   └── ResultsDisplay.jsx
│   │   └── services/
│   │       └── api.js           # API client
│   └── public/
└── docs/
    ├── api/
    │   └── openapi.yaml         # OpenAPI/Swagger documentation
    └── architecture.md           # This document
```

## Epic to Architecture Mapping

**Note:** Epics are not yet defined. This mapping represents logical epic boundaries:

| Epic | Architecture Components | Description |
|------|------------------------|-------------|
| **Epic 1: Project Foundation** | AWS SAM structure, Basic Lambda functions, API Gateway setup, Basic configuration | Establish base infrastructure and project structure |
| **Epic 2: Job Submission and Management** | REST API endpoints, Job service, DynamoDB table, SQS queue | Enable job submission, status tracking, and queue management |
| **Epic 3: Multi-Stage Processing Pipeline** | Step Functions state machine, Pipeline stage Lambdas, Progress tracking, WebSocket updates | Implement progressive disclosure with multi-stage processing |
| **Epic 4: AI Processing Integration** | Textract service, SageMaker service, Model inference logic, Fast preview + full processing | Integrate AWS AI/ML services for room detection |
| **Epic 5: Caching and Optimization** | S3 caching, DynamoDB preview cache integration, Cache service, Cache invalidation logic | Implement multi-tier caching for performance |
| **Epic 6: Frontend Integration** | Minimal test frontend, API client, WebSocket client, Results visualization | Build simple test interface for blueprint submission and results |

## Technology Stack Details

### Core Technologies

**Backend:**
- **Python 3.11** - Runtime language
- **AWS Lambda** - Serverless compute
- **API Gateway** - REST API and WebSocket API
- **Step Functions** - Multi-stage pipeline orchestration
- **SQS** - Job queue
- **DynamoDB** - Job status storage and fast preview caching
- **S3** - File storage and caching
- **Textract** - Document preprocessing
- **SageMaker** - Model inference (YOLOv8-seg fine-tuned)
- **Parameter Store** - Configuration management
- **Secrets Manager** - Secrets management
- **CloudWatch** - Logging and monitoring

**Frontend:**
- **React** - UI framework (minimal test interface)
- **WebSocket API** - Real-time updates
- **REST API** - Job submission and status

**Infrastructure:**
- **AWS SAM** - Infrastructure as code
- **CloudFormation** - Resource provisioning (via SAM)

### Integration Points

**1. API Gateway → Lambda (REST API)**
- REST API endpoints trigger Lambda functions
- Request/response format: JSON
- Authentication: API key or token

**2. API Gateway → Lambda (WebSocket API)**
- WebSocket connections trigger Lambda functions
- Real-time progress updates
- Bidirectional communication

**3. Lambda → Step Functions**
- Job submission triggers Step Functions state machine
- Step Functions orchestrates multi-stage pipeline

**4. Step Functions → Lambda (Pipeline stages)**
- Each stage is a Lambda function
- Stage 1: Fast preview (2-5 seconds)
- Stage 2: Intermediate results (10-15 seconds)
- Stage 3: Final processing (20-30 seconds)

**5. Lambda → AWS Services**
- **Textract:** Document preprocessing
- **SageMaker:** Model inference (YOLOv8-seg)
- **S3:** File storage and caching
- **DynamoDB:** Job status storage and fast preview caching
- **SQS:** Job queue
- **Parameter Store:** Configuration
- **Secrets Manager:** Secrets

**6. Lambda → WebSocket API**
- Pipeline stages send progress updates via WebSocket
- Real-time status updates to connected clients

**7. Frontend → API Gateway**
- REST API for job submission
- WebSocket API for real-time updates
- Polling fallback if WebSocket unavailable

## Implementation Patterns

These patterns ensure consistent implementation across all AI agents:

### Naming Patterns

**API Routes:**
- Format: `/api/v1/{resource}/{id}/{action}`
- Examples:
  - `POST /api/v1/jobs` - Create job
  - `GET /api/v1/jobs/{job_id}` - Get job status
  - `DELETE /api/v1/jobs/{job_id}` - Cancel job
  - `POST /api/v1/jobs/{job_id}/feedback` - Submit feedback
- Plural resources: `jobs`, `blueprints`, `rooms`

**Lambda Functions:**
- Format: `{service}_{purpose}_{type}`
- Examples:
  - `api_rest_handler`
  - `api_websocket_handler`
  - `pipeline_stage_1_preview`
  - `pipeline_stage_2_intermediate`
  - `pipeline_stage_3_final`
  - `service_job_manager`
  - `service_textract_processor`

**DynamoDB Tables:**
- Format: `{resource}s` (plural, lowercase) or `{resource}_{purpose}` (snake_case for specialized tables)
- Examples: `jobs`, `preview_cache`

**S3 Buckets:**
- Format: `{project}-{environment}-{purpose}`
- Examples:
  - `location-detection-dev-blueprints`
  - `location-detection-dev-cache`
  - `location-detection-prod-blueprints`
  - `location-detection-prod-cache`

**S3 Object Keys:**
- Format: `{category}/{subcategory}/{identifier}`
- Examples:
  - `blueprints/{job_id}/{filename}`
  - `cache/preview/{blueprint_hash}/{model_version}.json`
  - `cache/intermediate/{job_id}/stage_2.json`
  - `cache/final/{job_id}/results.json`

**Python Modules:**
- Format: `snake_case`
- Examples: `job_service.py`, `textract_service.py`

**Python Classes:**
- Format: `PascalCase`
- Examples: `JobService`, `TextractService`

**Python Functions:**
- Format: `snake_case`
- Examples: `create_job()`, `get_job_status()`

### Structure Patterns

**Test Organization:**
- Location: `src/tests/`
- Structure:
  - `unit/` - Unit tests for individual functions/classes
  - `integration/` - Integration tests for API endpoints and services
  - `fixtures/` - Test data and mocks

**Component Organization:**
- By feature/service, not by type
- Structure:
  - `api/` - API handlers
  - `services/` - Business logic services
  - `pipeline/` - Pipeline stages
  - `models/` - Data models
  - `utils/` - Shared utilities

### Format Patterns

**API Request Format:**
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

**API Response Format (Success):**
```json
{
  "status": "success",
  "data": {
    "job_id": "job_20240115_abc123",
    "status": "processing",
    "created_at": "2024-01-15T10:30:00Z"
  },
  "meta": {
    "request_id": "req_xyz789"
  }
}
```

**API Response Format (Error):**
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

**Job Status Response:**
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
      "rooms": [
        {
          "id": "room_001",
          "bounding_box": [50, 50, 200, 300],
          "name_hint": "Entry Hall",
          "confidence": 0.85
        }
      ]
    },
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:15Z"
  }
}
```

**WebSocket Message Format:**
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

### Communication Patterns

**WebSocket Events:**
- Types: `progress_update`, `stage_complete`, `job_complete`, `job_failed`, `job_cancelled`
- Format: JSON
- Bidirectional: Client can send `cancel_job`, `request_status`

**Step Functions State Transitions:**
- States: `Pending`, `Stage1Preview`, `Stage2Intermediate`, `Stage3Final`, `Completed`, `Failed`, `Cancelled`
- Transitions: Each stage completes → next stage starts
- Error handling: Failed stage → `Failed` state

**SQS Message Format:**
```json
{
  "job_id": "job_20240115_abc123",
  "blueprint_s3_key": "blueprints/job_20240115_abc123/blueprint.pdf",
  "stage": "stage_1",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Lifecycle Patterns

**Job Lifecycle:**
1. `pending` - Job created, queued in SQS
2. `processing` - Job picked up by Step Functions
3. `stage_1_complete` - Fast preview complete
4. `stage_2_complete` - Intermediate results complete
5. `completed` - Final results ready
6. `failed` - Processing failed
7. `cancelled` - User cancelled

**Loading States:**
- Format: `{"status": "processing", "stage": "...", "progress": 0-100}`
- Update frequency: Every 5 seconds or on stage completion

**Error Recovery:**
- Retry logic: Exponential backoff (1s, 2s, 4s, 8s), max 3-5 retries
- Partial results: Return partial results if available
- Graceful degradation: Show what's available, not all-or-nothing

### Location Patterns

**API Route Structure:**
- Base: `/api/v1`
- Resources: `/jobs`, `/health`, `/api-docs`
- Actions: `/jobs/{id}`, `/jobs/{id}/feedback`

**S3 Bucket Structure:**
- `blueprints/` - Original uploaded files
- `cache/preview/` - Fast preview results
- `cache/intermediate/` - Intermediate results
- `cache/final/` - Final results

**Parameter Store Paths:**
- Format: `/{project}/{environment}/{service}/{config}`
- Examples:
  - `/location-detection/prod/models/preview/version`
  - `/location-detection/prod/models/full/version`
  - `/location-detection/prod/api/rate_limit`
  - `/location-detection/prod/cache/preview/ttl`

**Secrets Manager Secrets:**
- Format: `{project}/{environment}/{service}/{secret}`
- Examples:
  - `location-detection/prod/sagemaker/api_key`
  - `location-detection/prod/textract/access_key`

### Consistency Patterns

**Date Formatting:**
- Format: ISO 8601 strings (`2024-01-15T10:30:00Z`)
- Timezone: UTC for all timestamps
- Library: Python `datetime` with `zoneinfo`

**Logging Format:**
- Structured JSON logs
- Include: `request_id`, `job_id`, `timestamp`, `level`, `message`, `context`
- Example:
```json
{
  "request_id": "req_xyz789",
  "job_id": "job_20240115_abc123",
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "message": "Job processing started",
  "context": {
    "stage": "stage_1",
    "blueprint_format": "pdf"
  }
}
```

**User-Facing Errors:**
- Format: User-friendly messages, actionable suggestions
- Example: "File format must be PNG, JPG, or PDF. Please upload a valid blueprint file."

**Technical Errors:**
- Format: Detailed error codes and context
- Location: CloudWatch logs
- Example: `ERROR_CODE: SERVICE_UNAVAILABLE, Details: SageMaker endpoint unreachable`

## Consistency Rules

### Naming Conventions

**API Routes:** `/api/v1/{resource}/{id}/{action}` (plural resources)
**Lambda Functions:** `{service}_{purpose}_{type}` (snake_case)
**DynamoDB Tables:** `{resource}s` (plural, lowercase) or `{resource}_{purpose}` (snake_case for specialized tables)
**S3 Buckets:** `{project}-{environment}-{purpose}` (kebab-case)
**S3 Object Keys:** `{category}/{subcategory}/{identifier}` (forward slashes)
**Python Modules:** `snake_case.py`
**Python Classes:** `PascalCase`
**Python Functions:** `snake_case()`

### Code Organization

**By Feature/Service, Not by Type:**
- `api/` - API handlers
- `services/` - Business logic services
- `pipeline/` - Pipeline stages
- `models/` - Data models
- `utils/` - Shared utilities

**Test Organization:**
- `tests/unit/` - Unit tests
- `tests/integration/` - Integration tests
- `tests/fixtures/` - Test data and mocks

### Error Handling

**Strategy:**
- Format: `{"error": {"code": "ERROR_CODE", "message": "User-friendly message", "details": {...}}}`
- HTTP status codes: 400 (bad request), 500 (server error), 503 (service unavailable)
- Retry logic: Exponential backoff (1s, 2s, 4s, 8s), max 3-5 retries
- Logging: Technical details in CloudWatch, user-friendly messages in API responses

**Error Codes:**
- `INVALID_FILE_FORMAT` - File format not supported
- `JOB_NOT_FOUND` - Job ID not found
- `PROCESSING_FAILED` - Processing stage failed
- `SERVICE_UNAVAILABLE` - AWS service unavailable
- `FILE_TOO_LARGE` - File exceeds size limit
- `RATE_LIMIT_EXCEEDED` - Too many requests

### Logging Strategy

**Format:**
- Structured JSON logs
- Levels: ERROR, WARN, INFO, DEBUG
- Include: Request ID, job ID, timestamp, stage, duration
- Destination: CloudWatch Logs

**Log Structure:**
```json
{
  "request_id": "req_xyz789",
  "job_id": "job_20240115_abc123",
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "message": "Job processing started",
  "context": {
    "stage": "stage_1",
    "blueprint_format": "pdf"
  }
}
```

## Data Architecture

### DynamoDB Schema

**Table: `jobs`**
- **Partition Key:** `job_id` (string, format: `job_{timestamp}_{random}`)
- **Attributes:**
  - `status` (string): `pending`, `processing`, `stage_1_complete`, `stage_2_complete`, `completed`, `failed`, `cancelled`
  - `created_at` (string): ISO 8601 timestamp
  - `updated_at` (string): ISO 8601 timestamp
  - `stage` (string): Current processing stage
  - `progress` (number): 0-100
  - `message` (string): Status message
  - `result_s3_key` (string): S3 key for final results
  - `blueprint_s3_key` (string): S3 key for uploaded blueprint
  - `estimated_seconds_remaining` (number): Estimated time remaining
- **TTL:** 7 days (auto-delete old jobs)

**Table: `preview_cache`**
- **Partition Key:** `cache_key` (string, format: `preview:{blueprint_hash}:{model_version}`)
- **Attributes:**
  - `rooms` (list/map): Room detection results
  - `timestamp` (string): ISO 8601 timestamp
  - `model_version` (string): Model version used
  - `expires_at` (number): Unix timestamp for TTL
- **TTL:** 1 hour (using `expires_at` attribute)

### S3 Bucket Structure

**Bucket: `{project}-{environment}-blueprints`**
- `blueprints/{job_id}/{filename}` - Original uploaded files

**Bucket: `{project}-{environment}-cache`**
- `cache/preview/{blueprint_hash}/{model_version}.json` - Fast preview results
- `cache/intermediate/{job_id}/stage_2.json` - Intermediate results
- `cache/final/{job_id}/results.json` - Final results

**Lifecycle Policy:**
- Delete files after 30 days

### Data Models

**Job Model:**
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
    "blueprint_s3_key": "blueprints/job_20240115_abc123/blueprint.pdf"
}
```

**Room Detection Result:**
```python
{
    "id": "room_001",
    "bounding_box": [50, 50, 200, 300],  # [x_min, y_min, x_max, y_max]
    "polygon": [[50, 50], [200, 50], [200, 300], [50, 300]],  # Precise shape (optional)
    "name_hint": "Entry Hall",
    "confidence": 0.85
}
```

## API Contracts

### REST API Endpoints

**Base URL:** `https://{api-id}.execute-api.{region}.amazonaws.com/api/v1`

**1. Create Job**
- **Method:** `POST`
- **Path:** `/jobs`
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
    "created_at": "2024-01-15T10:30:00Z"
  },
  "meta": {
    "request_id": "req_xyz789"
  }
}
```

**2. Get Job Status**
- **Method:** `GET`
- **Path:** `/jobs/{job_id}`
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
    "updated_at": "2024-01-15T10:30:15Z"
  }
}
```

**3. Cancel Job**
- **Method:** `DELETE`
- **Path:** `/jobs/{job_id}`
- **Response:**
```json
{
  "status": "success",
  "data": {
    "job_id": "job_20240115_abc123",
    "status": "cancelled",
    "message": "Job cancelled successfully"
  }
}
```

**4. Submit Feedback**
- **Method:** `POST`
- **Path:** `/jobs/{job_id}/feedback`
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

**5. Health Check**
- **Method:** `GET`
- **Path:** `/health`
- **Response:**
```json
{
  "status": "healthy",
  "services": {
    "dynamodb": "healthy",
    "s3": "healthy",
    "sagemaker": "healthy"
  }
}
```

### WebSocket API

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

## Security Architecture

**Authentication:**
- API key or simple token (MVP)
- Header: `Authorization: Bearer <token>`
- Store tokens: Parameter Store or Secrets Manager
- Future: OAuth 2.0 / JWT tokens

**Authorization:**
- IAM roles with least privilege principle
- Lambda execution roles with minimal permissions
- S3 bucket policies for access control

**Secrets Management:**
- AWS Secrets Manager for sensitive data
- Never store secrets in code or environment variables
- Rotate secrets regularly

**Encryption:**
- S3 encryption at rest (SSE-S3 or SSE-KMS)
- HTTPS in transit (API Gateway)
- DynamoDB encryption at rest

**Network Security:**
- API Gateway with HTTPS only
- VPC not needed for MVP (can add later)
- Security groups for Lambda if in VPC

## Performance Considerations

**Processing Time:**
- Stage 1 (Fast Preview): 2-5 seconds
- Stage 2 (Intermediate): 10-15 seconds
- Stage 3 (Final): 20-30 seconds
- Total: <30 seconds per blueprint (requirement met)

**Caching Strategy:**
- DynamoDB: Fast preview (instant for repeated blueprints)
- S3: Intermediate and final results (persistent)
- Cache TTL: 1 hour (preview), 24 hours (intermediate), 7 days (final)

**SageMaker Endpoint Configuration:**
- Preview: `ml.t3.medium` (faster, lower cost)
- Full: `ml.g4dn.xlarge` (accurate, higher cost)
- Auto-scaling: Min 1, Max 5 instances

**Lambda Configuration:**
- Memory: 512MB - 1GB (adjust based on performance)
- Timeout: 5 minutes (300 seconds)
- Concurrent executions: Auto-scaling

**API Gateway:**
- Throttling: 1000 requests/second (default)
- WebSocket: Connection limits per user

**Cost Optimization:**
- SageMaker: Auto-scaling (scale down to 0 when idle)
- DynamoDB: On-demand pricing for MVP, provisioned capacity for predictable workloads
- S3: Lifecycle policies to delete old data
- Lambda: Right-size memory allocation

## Deployment Architecture

**Environments:**
- **Development:** Local SAM, mock AWS services
- **Staging:** AWS with test data
- **Production:** AWS with real data

**Deployment Strategy:**
- **SAM CLI:** `sam build && sam deploy`
- **Environments:** Separate stacks per environment
- **Rollback:** SAM supports rollback via CloudFormation

**Infrastructure as Code:**
- **SAM Template:** `template.yaml`
- **CloudFormation:** Generated from SAM template
- **Version Control:** Git for infrastructure changes

**CI/CD (Future):**
- GitHub Actions or AWS CodePipeline
- Automated testing before deployment
- Blue/green deployments for zero downtime

## Development Environment

### Prerequisites

- **AWS CLI:** Latest version
- **AWS SAM CLI:** Latest version
- **Python 3.11:** Runtime language
- **Node.js 18+:** For frontend (if building minimal test frontend)
- **Docker:** For local Lambda testing (optional)
- **Git:** Version control

### Setup Commands

**1. Initialize Project:**
```bash
sam init --runtime python3.11 --name location-detection-api --app-template hello-world
```

**2. Install Dependencies:**
```bash
cd location-detection-api
pip install -r requirements.txt
```

**3. Configure AWS:**
```bash
aws configure
```

**4. Build Project:**
```bash
sam build
```

**5. Test Locally:**
```bash
sam local start-api
sam local invoke ApiRestHandler
```

**6. Deploy to AWS:**
```bash
sam deploy --guided
```

**7. Set Up Configuration:**
```bash
# Set Parameter Store values
aws ssm put-parameter --name "/location-detection/prod/models/preview/version" --value "1.0.0" --type "String"
aws ssm put-parameter --name "/location-detection/prod/models/full/version" --value "1.0.0" --type "String"

# Set Secrets Manager secrets
aws secretsmanager create-secret --name "location-detection/prod/sagemaker/api_key" --secret-string "your-api-key"
```

## Architecture Decision Records (ADRs)

### ADR-001: AWS SAM as Starter Template
**Decision:** Use AWS SAM for project initialization
**Rationale:** AWS-native serverless development, good local testing, integrates with Step Functions, simplifies deployment
**Alternatives Considered:** Serverless Framework, AWS CDK
**Status:** Accepted

### ADR-002: REST + WebSocket API Pattern
**Decision:** Use REST API for job submission, WebSocket API for real-time updates
**Rationale:** Supports progressive disclosure, better UX with immediate feedback, bidirectional communication for cancellation
**Alternatives Considered:** REST only (polling), REST + SSE
**Status:** Accepted

### ADR-003: SQS + Step Functions for Job Processing
**Decision:** Use SQS for job queue, Step Functions for multi-stage orchestration
**Rationale:** Enables progressive disclosure with multi-stage pipeline, built-in retry logic, good for async processing
**Alternatives Considered:** SQS only, EventBridge + Step Functions
**Status:** Accepted

### ADR-004: DynamoDB + S3 for State Management
**Decision:** Use DynamoDB for job status and fast preview caching, S3 for results caching
**Rationale:** Simpler architecture (no VPC required), cost-effective at low scale, fully managed, built-in TTL support, acceptable performance (1-5ms latency)
**Alternatives Considered:** DynamoDB + S3 + ElastiCache, DynamoDB only, DynamoDB + S3
**Status:** Accepted
**Note:** ElastiCache was considered but rejected for MVP due to operational complexity (VPC setup) and higher fixed costs. DynamoDB provides sufficient performance for preview caching while simplifying the architecture.

### ADR-005: Textract + SageMaker for AI Processing
**Decision:** Use Textract for preprocessing, SageMaker with YOLOv8-seg fine-tuned model for room detection
**Rationale:** Supports fast preview + full processing, flexible for future improvements, better accuracy than managed services alone
**Alternatives Considered:** Textract + Rekognition + Custom logic, SageMaker only
**Status:** Accepted

### ADR-006: Basic Retry with Exponential Backoff
**Decision:** Use basic retry logic with exponential backoff (1s, 2s, 4s, 8s), max 3-5 retries
**Rationale:** Simple and effective, good for transient failures, less complex than circuit breakers
**Alternatives Considered:** SQS dead-letter queue, Circuit breaker pattern
**Status:** Accepted

### ADR-007: CloudWatch Only for Monitoring
**Decision:** Use CloudWatch for logs, metrics, and alerts
**Rationale:** Cost-effective for MVP, good enough for initial monitoring, can add X-Ray later if needed
**Alternatives Considered:** CloudWatch + X-Ray, CloudWatch + X-Ray + Custom dashboards
**Status:** Accepted

### ADR-008: Parameter Store + Secrets Manager for Configuration
**Decision:** Use Parameter Store for configuration, Secrets Manager for secrets
**Rationale:** Secure and scalable, AWS best practice, good balance of features and simplicity
**Alternatives Considered:** Environment variables only, Parameter Store + Secrets Manager + AppConfig
**Status:** Accepted

---

_Generated by BMAD Decision Architecture Workflow v1.3.2_  
_Date: 2025-01-15_  
_For: BMad_

