"""
REST API Lambda handler for Location Detection AI service.

This module provides the health check and job management endpoint handlers.
"""
import json
import base64
import re
from typing import Dict, Any, Optional
from io import BytesIO

# Handle imports for both Lambda (src/ directory) and local testing (project root)
# Lambda runs from src/ directory, so imports don't need src. prefix
# Tests run from project root, so they need src. prefix
try:
    from services.job_service import JobService
    from services.feedback_service import FeedbackService
    from services.preview_service import PreviewService
    from pipeline.stage_1_preview import lambda_handler as preview_lambda_handler
    from utils.errors import (
        InvalidFileFormatError,
        FileTooLargeError,
        JobNotFoundError,
        format_error_response
    )
    from utils.logging import get_logger
    from utils.request_id import generate_request_id, extract_api_version
except ImportError:
    # Fallback for local testing from project root
    from src.services.job_service import JobService
    from src.services.feedback_service import FeedbackService
    from src.services.preview_service import PreviewService
    from src.pipeline.stage_1_preview import lambda_handler as preview_lambda_handler
    from src.utils.errors import (
        InvalidFileFormatError,
        FileTooLargeError,
        JobNotFoundError,
        format_error_response
    )
    from src.utils.logging import get_logger
    from src.utils.request_id import generate_request_id, extract_api_version


logger = get_logger(__name__)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for REST API endpoints.
    
    Implements:
    - GET /health - Health check endpoint
    - POST /api/v1/jobs - Create job with blueprint file upload
    - GET /api/v1/jobs/{job_id} - Retrieve job status
    - DELETE /api/v1/jobs/{job_id} - Cancel job
    - POST /api/v1/jobs/{job_id}/feedback - Submit feedback for a job
    - GET /api/v1/jobs/{job_id}/feedback - Retrieve feedback for a job
    
    Args:
        event: API Gateway HTTP API event
        context: Lambda context object
        
    Returns:
        API Gateway HTTP API response with status code and body
    """
    # Generate request ID in format: req_{timestamp}_{random}
    request_id = generate_request_id()
    logger.set_request_id(request_id)

    # Extract HTTP method and path from event
    http_method = event.get('requestContext', {}).get(
        'http', {}).get('method', '')
    path = event.get('requestContext', {}).get('http', {}).get('path', '')

    # Extract API version from path (defaults to v1)
    api_version = extract_api_version(path)

    # Extract correlation ID from headers if present
    headers = event.get('headers', {}) or {}
    correlation_id = headers.get(
        'X-Correlation-ID') or headers.get('x-correlation-id')
    if correlation_id:
        logger.set_correlation_id(correlation_id)

    # Handle OPTIONS for CORS preflight
    if http_method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': ''
        }

    try:
        # Route to appropriate handler based on method and path
        if http_method == 'GET' and path == '/health':
            return handle_health_check(event, context, request_id, api_version)

        if http_method == 'POST' and path == '/api/v1/jobs':
            return handle_create_job(event, context, request_id, api_version, correlation_id)

        # Match GET /api/v1/jobs/{job_id} or DELETE /api/v1/jobs/{job_id}
        match = re.match(r'^/api/v\d+/jobs/([^/]+)$', path)
        if match:
            job_id = match.group(1)
            if http_method == 'GET':
                return handle_get_job(event, context, job_id, request_id, api_version)
            elif http_method == 'DELETE':
                return handle_cancel_job(event, context, job_id, request_id, api_version)

        # Match POST /api/v1/jobs/{job_id}/feedback or GET /api/v1/jobs/{job_id}/feedback
        match = re.match(r'^/api/v\d+/jobs/([^/]+)/feedback$', path)
        if match:
            job_id = match.group(1)
            if http_method == 'POST':
                return handle_submit_feedback(event, context, job_id, request_id, api_version)
            elif http_method == 'GET':
                return handle_get_feedback(event, context, job_id, request_id, api_version)

        # Match POST /api/v1/jobs/{job_id}/preview or GET /api/v1/jobs/{job_id}/preview
        match = re.match(r'^/api/v\d+/jobs/([^/]+)/preview$', path)
        if match:
            job_id = match.group(1)
            if http_method == 'POST':
                return handle_trigger_preview(event, context, job_id, request_id, api_version)
            elif http_method == 'GET':
                return handle_get_preview(event, context, job_id, request_id, api_version)

        # Match GET /api/v1/jobs/{job_id}/textract-results
        match = re.match(r'^/api/v\d+/jobs/([^/]+)/textract-results$', path)
        if match:
            job_id = match.group(1)
            if http_method == 'GET':
                return handle_get_textract_results(event, context, job_id, request_id, api_version)

        # Default 404 response
        return {
            'statusCode': 404,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'status': 'error',
                'error': {
                    'code': 'NOT_FOUND',
                    'message': f'Endpoint {http_method} {path} not found'
                },
                'meta': {
                    'request_id': request_id,
                    'api_version': api_version
                }
            })
        }

    except Exception as e:
        logger.error(
            f"Unhandled error in handler: {str(e)}",
            exc_info=True,
            context={'method': http_method, 'path': path}
        )
        error_response = format_error_response(
            e, request_id=request_id, api_version=api_version)
        status_code = getattr(e, 'status_code', 500) if hasattr(
            e, 'status_code') else 500
        return {
            'statusCode': status_code,
            'headers': get_cors_headers(),
            'body': json.dumps(error_response)
        }


def handle_health_check(event: Dict[str, Any], context: Any, request_id: str, api_version: str) -> Dict[str, Any]:
    """
    Handle GET /health endpoint.
    
    Returns service health status with service checks.
    
    Args:
        event: API Gateway HTTP API event
        context: Lambda context object
        request_id: Request ID for correlation
        api_version: API version string
        
    Returns:
        API Gateway HTTP API response with health status
    """
    # For now, return healthy status for all services
    # In future stories, this will check actual service connectivity
    response_body = {
        'status': 'healthy',
        'data': {
            'services': {
                'dynamodb': 'healthy',
                's3': 'healthy',
                'sagemaker': 'healthy'
            }
        },
        'meta': {
            'request_id': request_id,
            'api_version': api_version
        }
    }

    return {
        'statusCode': 200,
        'headers': get_cors_headers(),
        'body': json.dumps(response_body)
    }


def handle_create_job(
    event: Dict[str, Any],
    context: Any,
    request_id: str,
    api_version: str,
    correlation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handle POST /api/v1/jobs endpoint.
    
    Creates a new job with blueprint file upload.
    
    Args:
        event: API Gateway HTTP API event
        context: Lambda context object
        request_id: Request ID for correlation
        api_version: API version string
        correlation_id: Optional correlation ID for distributed tracing
        
    Returns:
        API Gateway HTTP API response with job data
    """
    logger.set_request_id(request_id)
    if correlation_id:
        logger.set_correlation_id(correlation_id)

    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        blueprint_data = body.get('blueprint', {})

        # Extract blueprint file and format
        file_data = blueprint_data.get('file', '')
        blueprint_format = blueprint_data.get('format', '').lower()
        filename = blueprint_data.get('filename')

        # Validate format
        if blueprint_format not in ['png', 'jpg', 'pdf']:
            raise InvalidFileFormatError(blueprint_format)

        # Decode base64 file data
        try:
            file_content = base64.b64decode(file_data)
        except Exception as e:
            raise ValueError(f"Invalid base64 file data: {str(e)}")

        # Validate file size (50MB limit)
        MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
        if len(file_content) > MAX_FILE_SIZE:
            raise FileTooLargeError(len(file_content), MAX_FILE_SIZE)

        # Validate MIME type matches declared format
        _validate_file_mime_type(file_content, blueprint_format)

        # Create job service
        job_service = JobService()
        logger.set_job_id(None)  # Will be set after job creation

        # Create job with request_id, correlation_id, and api_version
        file_obj = BytesIO(file_content)
        job = job_service.create_job(
            blueprint_file=file_obj,
            blueprint_format=blueprint_format,
            filename=filename,
            request_id=request_id,
            correlation_id=correlation_id,
            api_version=api_version
        )

        logger.set_job_id(job.job_id)
        logger.info(
            f"Job created: {job.job_id}",
            context={'job_id': job.job_id, 'format': blueprint_format,
                'api_version': api_version}
        )

        # Return success response
        response_body = {
            'status': 'success',
            'data': job.to_dict(),
            'meta': {
                'request_id': request_id,
                'api_version': api_version
            }
        }

        # Add request ID to response headers
        headers = get_cors_headers()
        headers['X-Request-ID'] = request_id

        return {
            'statusCode': 201,
            'headers': headers,
            'body': json.dumps(response_body)
        }

    except (InvalidFileFormatError, FileTooLargeError) as e:
        error_response = format_error_response(
            e, request_id=request_id, api_version=api_version)
        return {
            'statusCode': e.status_code,
            'headers': get_cors_headers(),
            'body': json.dumps(error_response)
        }
    except Exception as e:
        logger.error(
            f"Error creating job: {str(e)}",
            exc_info=True
        )
        error_response = format_error_response(
            e, request_id=request_id, api_version=api_version)
        status_code = getattr(e, 'status_code', 500) if hasattr(
            e, 'status_code') else 500
        return {
            'statusCode': status_code,
            'headers': get_cors_headers(),
            'body': json.dumps(error_response)
        }


def handle_get_job(event: Dict[str, Any], context: Any, job_id: str, request_id: str, api_version: str) -> Dict[str, Any]:
    """
    Handle GET /api/v1/jobs/{job_id} endpoint.
    
    Retrieves job status by job_id.
    
    Args:
        event: API Gateway HTTP API event
        context: Lambda context object
        job_id: Job identifier
        request_id: Request ID for correlation
        api_version: API version string
        
    Returns:
        API Gateway HTTP API response with job data
    """
    logger.set_request_id(request_id)
    logger.set_job_id(job_id)

    # Validate job_id format
    if not job_id or not job_id.startswith('job_'):
        from utils.errors import LocationDetectionError
        raise LocationDetectionError(
            code='INVALID_JOB_ID',
            message=f"Invalid job ID format: {job_id}",
            details={'job_id': job_id},
            status_code=400
        )

    try:
        # Create job service
        job_service = JobService()

        # Get job
        job = job_service.get_job(job_id)

        logger.info(
            f"Job retrieved: {job_id}",
            context={'job_id': job_id, 'status': job.status.value,
                'api_version': api_version}
        )

        # Return success response
        response_body = {
            'status': 'success',
            'data': job.to_dict(),
            'meta': {
                'request_id': request_id,
                'api_version': api_version
            }
        }

        # Add request ID to response headers
        headers = get_cors_headers()
        headers['X-Request-ID'] = request_id

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(response_body)
        }

    except Exception as e:
        # Log error (but don't let logging errors break error handling)
        try:
            logger.error(
                f"Error retrieving job {job_id}: {str(e)}",
                exc_info=True,
                context={'job_id': job_id}
            )
        except Exception:
            pass  # Don't let logging errors break error handling

        error_response = format_error_response(
            e, request_id=request_id, api_version=api_version)
        status_code = getattr(e, 'status_code', 500) if hasattr(
            e, 'status_code') else 500
        return {
            'statusCode': status_code,
            'headers': get_cors_headers(),
            'body': json.dumps(error_response)
        }


def handle_cancel_job(event: Dict[str, Any], context: Any, job_id: str, request_id: str, api_version: str) -> Dict[str, Any]:
    """
    Handle DELETE /api/v1/jobs/{job_id} endpoint.
    
    Cancels a job by job_id.
    
    Args:
        event: API Gateway HTTP API event
        context: Lambda context object
        job_id: Job identifier
        request_id: Request ID for correlation
        api_version: API version string
        
    Returns:
        API Gateway HTTP API response with updated job data
    """
    logger.set_request_id(request_id)
    logger.set_job_id(job_id)

    # Validate job_id format
    if not job_id or not job_id.startswith('job_'):
        from utils.errors import LocationDetectionError
        raise LocationDetectionError(
            code='INVALID_JOB_ID',
            message=f"Invalid job ID format: {job_id}",
            details={'job_id': job_id},
            status_code=400
        )

    try:
        # Create job service
        job_service = JobService()

        # Cancel job
        job = job_service.cancel_job(job_id)

        logger.info(
            f"Job cancelled: {job_id}",
            context={'job_id': job_id, 'api_version': api_version}
        )

        # Return success response
        response_body = {
            'status': 'success',
            'data': job.to_dict(),
            'meta': {
                'request_id': request_id,
                'api_version': api_version
            }
        }

        # Add request ID to response headers
        headers = get_cors_headers()
        headers['X-Request-ID'] = request_id

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(response_body)
        }

    except Exception as e:
        # Log error (but don't let logging errors break error handling)
        try:
            logger.error(
                f"Error cancelling job {job_id}: {str(e)}",
                exc_info=True,
                context={'job_id': job_id}
            )
        except Exception:
            pass  # Don't let logging errors break error handling

        error_response = format_error_response(
            e, request_id=request_id, api_version=api_version)
        status_code = getattr(e, 'status_code', 500) if hasattr(
            e, 'status_code') else 500
        return {
            'statusCode': status_code,
            'headers': get_cors_headers(),
            'body': json.dumps(error_response)
        }


def _validate_file_mime_type(file_content: bytes, declared_format: str) -> None:
    """
    Validate that file content matches declared MIME type.
    
    Args:
        file_content: File content bytes
        declared_format: Declared file format (png, jpg, pdf)
        
    Raises:
        InvalidFileFormatError: If MIME type doesn't match declared format
    """
    # File signatures (magic numbers) for validation
    PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
    JPEG_SIGNATURE_START = b'\xff\xd8\xff'
    PDF_SIGNATURE = b'%PDF'

    # Check file signature matches declared format
    if declared_format == 'png':
        if not file_content.startswith(PNG_SIGNATURE):
            # File signature doesn't match PNG format
            raise InvalidFileFormatError(declared_format)
    elif declared_format in ['jpg', 'jpeg']:
        if not file_content.startswith(JPEG_SIGNATURE_START):
            # File signature doesn't match JPEG format
            raise InvalidFileFormatError(declared_format)
    elif declared_format == 'pdf':
        if not file_content.startswith(PDF_SIGNATURE):
            # File signature doesn't match PDF format
            raise InvalidFileFormatError(declared_format)


def handle_submit_feedback(event: Dict[str, Any], context: Any, job_id: str, request_id: str, api_version: str) -> Dict[str, Any]:
    """
    Handle POST /api/v1/jobs/{job_id}/feedback endpoint.
    
    Submits feedback for a job.
    
    Args:
        event: API Gateway HTTP API event
        context: Lambda context object
        job_id: Job identifier
        request_id: Request ID for correlation
        api_version: API version string
        
    Returns:
        API Gateway HTTP API response with feedback data
    """
    logger.set_request_id(request_id)
    logger.set_job_id(job_id)

    # Validate job_id format
    if not job_id or not job_id.startswith('job_'):
        try:
            from utils.errors import LocationDetectionError
        except ImportError:
            from src.utils.errors import LocationDetectionError
        raise LocationDetectionError(
            code='INVALID_JOB_ID',
            message=f"Invalid job ID format: {job_id}",
            details={'job_id': job_id},
            status_code=400
        )

    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        
        # Validate required fields
        if 'feedback' not in body:
            try:
                from utils.errors import LocationDetectionError
            except ImportError:
                from src.utils.errors import LocationDetectionError
            raise LocationDetectionError(
                code='INVALID_REQUEST',
                message="Missing required field: feedback",
                details={'missing_fields': ['feedback']},
                status_code=400
            )
        
        # Verify job exists
        job_service = JobService()
        job_service.get_job(job_id)  # Will raise JobNotFoundError if not found
        
        # Create feedback service
        feedback_service = FeedbackService()
        
        # Submit feedback
        feedback = feedback_service.submit_feedback(job_id, body)
        
        # Handle both dict (from mocks) and Feedback object (from real service)
        if isinstance(feedback, dict):
            feedback_id = feedback.get('feedback_id')
            feedback_job_id = feedback.get('job_id')
        else:
            feedback_id = feedback.feedback_id
            feedback_job_id = feedback.job_id
        
        logger.info(
            f"Feedback submitted: {feedback_id} for job: {job_id}",
            context={'feedback_id': feedback_id, 'job_id': job_id, 'api_version': api_version}
        )
        
        # Return success response
        response_body = {
            'status': 'success',
            'data': {
                'feedback_id': feedback_id,
                'job_id': feedback_job_id,
                'message': 'Feedback submitted successfully',
                'request_id': request_id
            },
            'meta': {
                'request_id': request_id,
                'api_version': api_version
            }
        }
        
        # Add request ID to response headers
        headers = get_cors_headers()
        headers['X-Request-ID'] = request_id
        
        return {
            'statusCode': 201,
            'headers': headers,
            'body': json.dumps(response_body)
        }
        
    except JobNotFoundError as e:
        error_response = format_error_response(
            e, request_id=request_id, api_version=api_version)
        return {
            'statusCode': e.status_code,
            'headers': get_cors_headers(),
            'body': json.dumps(error_response)
        }
    except Exception as e:
        logger.error(
            f"Error submitting feedback for job {job_id}: {str(e)}",
            exc_info=True,
            context={'job_id': job_id}
        )
        error_response = format_error_response(
            e, request_id=request_id, api_version=api_version)
        status_code = getattr(e, 'status_code', 500) if hasattr(
            e, 'status_code') else 500
        return {
            'statusCode': status_code,
            'headers': get_cors_headers(),
            'body': json.dumps(error_response)
        }


def handle_get_feedback(event: Dict[str, Any], context: Any, job_id: str, request_id: str, api_version: str) -> Dict[str, Any]:
    """
    Handle GET /api/v1/jobs/{job_id}/feedback endpoint.
    
    Retrieves all feedback for a job.
    
    Args:
        event: API Gateway HTTP API event
        context: Lambda context object
        job_id: Job identifier
        request_id: Request ID for correlation
        api_version: API version string
        
    Returns:
        API Gateway HTTP API response with feedback list
    """
    logger.set_request_id(request_id)
    logger.set_job_id(job_id)

    # Validate job_id format
    if not job_id or not job_id.startswith('job_'):
        try:
            from utils.errors import LocationDetectionError
        except ImportError:
            from src.utils.errors import LocationDetectionError
        raise LocationDetectionError(
            code='INVALID_JOB_ID',
            message=f"Invalid job ID format: {job_id}",
            details={'job_id': job_id},
            status_code=400
        )

    try:
        # Verify job exists
        job_service = JobService()
        job_service.get_job(job_id)  # Will raise JobNotFoundError if not found
        
        # Create feedback service
        feedback_service = FeedbackService()
        
        # Get feedback
        feedback_list = feedback_service.get_feedback_by_job_id(job_id)
        
        logger.info(
            f"Retrieved {len(feedback_list)} feedback items for job: {job_id}",
            context={'job_id': job_id, 'count': len(feedback_list), 'api_version': api_version}
        )
        
        # Convert feedback objects to dictionaries (handle both dict and Feedback objects)
        feedback_dicts = []
        for feedback in feedback_list:
            if isinstance(feedback, dict):
                feedback_dicts.append(feedback)
            else:
                feedback_dicts.append(feedback.to_dict())
        
        # Return success response
        response_body = {
            'status': 'success',
            'data': {
                'feedback': feedback_dicts
            },
            'meta': {
                'request_id': request_id,
                'api_version': api_version
            }
        }
        
        # Add request ID to response headers
        headers = get_cors_headers()
        headers['X-Request-ID'] = request_id
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(response_body)
        }
        
    except JobNotFoundError as e:
        error_response = format_error_response(
            e, request_id=request_id, api_version=api_version)
        return {
            'statusCode': e.status_code,
            'headers': get_cors_headers(),
            'body': json.dumps(error_response)
        }
    except Exception as e:
        logger.error(
            f"Error retrieving feedback for job {job_id}: {str(e)}",
            exc_info=True,
            context={'job_id': job_id}
        )
        error_response = format_error_response(
            e, request_id=request_id, api_version=api_version)
        status_code = getattr(e, 'status_code', 500) if hasattr(
            e, 'status_code') else 500
        return {
            'statusCode': status_code,
            'headers': get_cors_headers(),
            'body': json.dumps(error_response)
        }


def handle_trigger_preview(event: Dict[str, Any], context: Any, job_id: str, request_id: str, api_version: str) -> Dict[str, Any]:
    """
    Handle POST /api/v1/jobs/{job_id}/preview endpoint.
    
    Triggers preview pipeline for a job.
    
    Args:
        event: API Gateway HTTP API event
        context: Lambda context object
        job_id: Job identifier
        request_id: Request ID for correlation
        api_version: API version string
        
    Returns:
        API Gateway HTTP API response with preview data
    """
    logger.set_request_id(request_id)
    logger.set_job_id(job_id)

    # Validate job_id format
    if not job_id or not job_id.startswith('job_'):
        try:
            from utils.errors import LocationDetectionError
        except ImportError:
            from src.utils.errors import LocationDetectionError
        raise LocationDetectionError(
            code='INVALID_JOB_ID',
            message=f"Invalid job ID format: {job_id}",
            details={'job_id': job_id},
            status_code=400
        )

    try:
        # Parse request body for optional parameters
        body = json.loads(event.get('body', '{}'))
        
        # Create Lambda event for preview pipeline
        preview_event = {
            'job_id': job_id,
            'simulate_full_processing_failure': body.get('simulate_full_processing_failure', False)
        }
        
        # Create a mock context for preview Lambda
        class MockContext:
            def __init__(self):
                self.aws_request_id = request_id
        
        mock_context = MockContext()
        
        # Invoke preview pipeline Lambda handler
        preview_response = preview_lambda_handler(preview_event, mock_context)
        
        # Parse response body
        response_body = json.loads(preview_response.get('body', '{}'))
        
        # Return success response
        headers = get_cors_headers()
        headers['X-Request-ID'] = request_id

        return {
            'statusCode': preview_response.get('statusCode', 200),
            'headers': headers,
            'body': json.dumps(response_body)
        }

    except Exception as e:
        logger.error(
            f"Error triggering preview for job {job_id}: {str(e)}",
            exc_info=True,
            context={'job_id': job_id}
        )
        error_response = format_error_response(
            e, request_id=request_id, api_version=api_version)
        status_code = getattr(e, 'status_code', 500) if hasattr(
            e, 'status_code') else 500
        return {
            'statusCode': status_code,
            'headers': get_cors_headers(),
            'body': json.dumps(error_response)
        }


def handle_get_preview(event: Dict[str, Any], context: Any, job_id: str, request_id: str, api_version: str) -> Dict[str, Any]:
    """
    Handle GET /api/v1/jobs/{job_id}/preview endpoint.
    
    Retrieves cached preview result for a job.
    
    Args:
        event: API Gateway HTTP API event
        context: Lambda context object
        job_id: Job identifier
        request_id: Request ID for correlation
        api_version: API version string
        
    Returns:
        API Gateway HTTP API response with preview data
    """
    logger.set_request_id(request_id)
    logger.set_job_id(job_id)

    # Validate job_id format
    if not job_id or not job_id.startswith('job_'):
        try:
            from utils.errors import LocationDetectionError
        except ImportError:
            from src.utils.errors import LocationDetectionError
        raise LocationDetectionError(
            code='INVALID_JOB_ID',
            message=f"Invalid job ID format: {job_id}",
            details={'job_id': job_id},
            status_code=400
        )

    try:
        # Verify job exists
        job_service = JobService()
        job = job_service.get_job(job_id)
        
        # Get cached preview (use same model version as preview pipeline)
        preview_service = PreviewService()
        cached_preview = None
        if job.blueprint_hash:
            # Use same model version as preview pipeline
            MODEL_VERSION = '1.0.0'
            logger.info(
                f"Looking up preview cache for job: {job_id}",
                context={
                    'job_id': job_id,
                    'blueprint_hash': job.blueprint_hash,
                    'model_version': MODEL_VERSION
                }
            )
            cached_preview = preview_service.get_cached_preview(job.blueprint_hash, MODEL_VERSION)
        else:
            logger.warning(
                f"Job {job_id} has no blueprint_hash, cannot retrieve cached preview",
                context={'job_id': job_id}
            )
        
        if not cached_preview:
            try:
                from utils.errors import LocationDetectionError
            except ImportError:
                from src.utils.errors import LocationDetectionError
            raise LocationDetectionError(
                code='PREVIEW_NOT_FOUND',
                message=f"Preview not found for job {job_id}",
                details={'job_id': job_id},
                status_code=404
            )
        
        logger.info(
            f"Retrieved cached preview for job: {job_id}",
            context={'job_id': job_id, 'api_version': api_version}
        )
        
        # Return success response
        response_body = {
            'status': 'success',
            'data': cached_preview,
            'meta': {
                'request_id': request_id,
                'api_version': api_version
            }
        }

        headers = get_cors_headers()
        headers['X-Request-ID'] = request_id

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(response_body)
        }

    except JobNotFoundError as e:
        error_response = format_error_response(
            e, request_id=request_id, api_version=api_version)
        return {
            'statusCode': e.status_code,
            'headers': get_cors_headers(),
            'body': json.dumps(error_response)
        }
    except Exception as e:
        logger.error(
            f"Error retrieving preview for job {job_id}: {str(e)}",
            exc_info=True,
            context={'job_id': job_id}
        )
        error_response = format_error_response(
            e, request_id=request_id, api_version=api_version)
        status_code = getattr(e, 'status_code', 500) if hasattr(
            e, 'status_code') else 500
        return {
            'statusCode': status_code,
            'headers': get_cors_headers(),
            'body': json.dumps(error_response)
        }


def handle_get_textract_results(event: Dict[str, Any], context: Any, job_id: str, request_id: str, api_version: str) -> Dict[str, Any]:
    """
    Handle GET /api/v1/jobs/{job_id}/textract-results endpoint.
    
    Retrieves Textract analysis results for a job.
    
    Args:
        event: API Gateway HTTP API event
        context: Lambda context object
        job_id: Job identifier
        request_id: Request ID for correlation
        api_version: API version string
        
    Returns:
        API Gateway HTTP API response with Textract results
    """
    logger.set_request_id(request_id)
    logger.set_job_id(job_id)

    # Validate job_id format
    if not job_id or not job_id.startswith('job_'):
        try:
            from utils.errors import LocationDetectionError
        except ImportError:
            from src.utils.errors import LocationDetectionError
        raise LocationDetectionError(
            code='INVALID_JOB_ID',
            message=f"Invalid job ID format: {job_id}",
            details={'job_id': job_id},
            status_code=400
        )

    try:
        # Verify job exists
        job_service = JobService()
        job_service.get_job(job_id)  # Will raise JobNotFoundError if not found
        
        # Get Textract results from S3
        preview_service = PreviewService()
        textract_results = preview_service.get_textract_results(job_id)
        
        if not textract_results:
            try:
                from utils.errors import LocationDetectionError
            except ImportError:
                from src.utils.errors import LocationDetectionError
            raise LocationDetectionError(
                code='TEXTRACT_RESULTS_NOT_FOUND',
                message=f"Textract results not found for job {job_id}",
                details={'job_id': job_id},
                status_code=404
            )
        
        # Extract S3 key from stored results
        s3_key = f"cache/textract/{job_id}/analysis.json"
        
        logger.info(
            f"Retrieved Textract results for job: {job_id}",
            context={'job_id': job_id, 's3_key': s3_key, 'api_version': api_version}
        )
        
        # Return success response
        response_body = {
            'status': 'success',
            'data': {
                's3_key': s3_key,
                'text_blocks': textract_results.get('text_blocks', []),
                'layout_blocks': textract_results.get('layout_blocks', []),
                'metadata': textract_results.get('metadata', {})
            },
            'meta': {
                'request_id': request_id,
                'api_version': api_version
            }
        }

        headers = get_cors_headers()
        headers['X-Request-ID'] = request_id

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(response_body)
        }

    except JobNotFoundError as e:
        error_response = format_error_response(
            e, request_id=request_id, api_version=api_version)
        return {
            'statusCode': e.status_code,
            'headers': get_cors_headers(),
            'body': json.dumps(error_response)
        }
    except Exception as e:
        logger.error(
            f"Error retrieving Textract results for job {job_id}: {str(e)}",
            exc_info=True,
            context={'job_id': job_id}
        )
        error_response = format_error_response(
            e, request_id=request_id, api_version=api_version)
        status_code = getattr(e, 'status_code', 500) if hasattr(
            e, 'status_code') else 500
        return {
            'statusCode': status_code,
            'headers': get_cors_headers(),
            'body': json.dumps(error_response)
        }


def get_cors_headers() -> Dict[str, str]:
    """
    Get CORS headers for API responses.
    
    Returns:
        Dictionary of CORS headers
    """
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        'Access-Control-Max-Age': '300'
    }
