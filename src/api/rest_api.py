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
    from utils.errors import (
        InvalidFileFormatError,
        FileTooLargeError,
        format_error_response
    )
    from utils.logging import get_logger
except ImportError:
    # Fallback for local testing from project root
    from src.services.job_service import JobService
    from src.utils.errors import (
        InvalidFileFormatError,
        FileTooLargeError,
        format_error_response
    )
    from src.utils.logging import get_logger


logger = get_logger(__name__)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for REST API endpoints.
    
    Implements:
    - GET /health - Health check endpoint
    - POST /api/v1/jobs - Create job with blueprint file upload
    - GET /api/v1/jobs/{job_id} - Retrieve job status
    - DELETE /api/v1/jobs/{job_id} - Cancel job
    
    Args:
        event: API Gateway HTTP API event
        context: Lambda context object
        
    Returns:
        API Gateway HTTP API response with status code and body
    """
    # Extract request ID for logging
    request_id = event.get('requestContext', {}).get('requestId', '')
    logger.set_request_id(request_id)
    
    # Extract HTTP method and path from event
    http_method = event.get('requestContext', {}).get('http', {}).get('method', '')
    path = event.get('requestContext', {}).get('http', {}).get('path', '')
    
    # Handle OPTIONS for CORS preflight
    if http_method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': ''
        }
    
    try:
        # Route to appropriate handler
        if http_method == 'GET' and path == '/health':
            return handle_health_check(event, context)
        
        if http_method == 'POST' and path == '/api/v1/jobs':
            return handle_create_job(event, context)
        
        # Match GET /api/v1/jobs/{job_id} or DELETE /api/v1/jobs/{job_id}
        match = re.match(r'^/api/v1/jobs/([^/]+)$', path)
        if match:
            job_id = match.group(1)
            if http_method == 'GET':
                return handle_get_job(event, context, job_id)
            elif http_method == 'DELETE':
                return handle_cancel_job(event, context, job_id)
        
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
                'meta': {'request_id': request_id}
            })
        }
    
    except Exception as e:
        logger.error(
            f"Unhandled error in handler: {str(e)}",
            exc_info=True,
            context={'method': http_method, 'path': path}
        )
        error_response = format_error_response(e, request_id=request_id)
        status_code = getattr(e, 'status_code', 500) if hasattr(e, 'status_code') else 500
        return {
            'statusCode': status_code,
            'headers': get_cors_headers(),
            'body': json.dumps(error_response)
        }


def handle_health_check(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle GET /health endpoint.
    
    Returns service health status with service checks.
    
    Args:
        event: API Gateway HTTP API event
        context: Lambda context object
        
    Returns:
        API Gateway HTTP API response with health status
    """
    # For now, return healthy status for all services
    # In future stories, this will check actual service connectivity
    response_body = {
        'status': 'healthy',
        'services': {
            'dynamodb': 'healthy',
            's3': 'healthy',
            'sagemaker': 'healthy'
        }
    }
    
    return {
        'statusCode': 200,
        'headers': get_cors_headers(),
        'body': json.dumps(response_body)
    }


def handle_create_job(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle POST /api/v1/jobs endpoint.
    
    Creates a new job with blueprint file upload.
    
    Args:
        event: API Gateway HTTP API event
        context: Lambda context object
        
    Returns:
        API Gateway HTTP API response with job data
    """
    request_id = event.get('requestContext', {}).get('requestId', '')
    logger.set_request_id(request_id)
    
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
        
        # Create job service
        job_service = JobService()
        logger.set_job_id(None)  # Will be set after job creation
        
        # Create job
        file_obj = BytesIO(file_content)
        job = job_service.create_job(
            blueprint_file=file_obj,
            blueprint_format=blueprint_format,
            filename=filename
        )
        
        logger.set_job_id(job.job_id)
        logger.info(
            f"Job created: {job.job_id}",
            context={'job_id': job.job_id, 'format': blueprint_format}
        )
        
        # Return success response
        response_body = {
            'status': 'success',
            'data': job.to_dict(),
            'meta': {'request_id': request_id}
        }
        
        return {
            'statusCode': 201,
            'headers': get_cors_headers(),
            'body': json.dumps(response_body)
        }
    
    except (InvalidFileFormatError, FileTooLargeError) as e:
        error_response = format_error_response(e, request_id=request_id)
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
        error_response = format_error_response(e, request_id=request_id)
        status_code = getattr(e, 'status_code', 500) if hasattr(e, 'status_code') else 500
        return {
            'statusCode': status_code,
            'headers': get_cors_headers(),
            'body': json.dumps(error_response)
        }


def handle_get_job(event: Dict[str, Any], context: Any, job_id: str) -> Dict[str, Any]:
    """
    Handle GET /api/v1/jobs/{job_id} endpoint.
    
    Retrieves job status by job_id.
    
    Args:
        event: API Gateway HTTP API event
        context: Lambda context object
        job_id: Job identifier
        
    Returns:
        API Gateway HTTP API response with job data
    """
    request_id = event.get('requestContext', {}).get('requestId', '')
    logger.set_request_id(request_id)
    logger.set_job_id(job_id)
    
    try:
        # Create job service
        job_service = JobService()
        
        # Get job
        job = job_service.get_job(job_id)
        
        logger.info(
            f"Job retrieved: {job_id}",
            context={'job_id': job_id, 'status': job.status.value}
        )
        
        # Return success response
        response_body = {
            'status': 'success',
            'data': job.to_dict(),
            'meta': {'request_id': request_id}
        }
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
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
        
        error_response = format_error_response(e, request_id=request_id)
        status_code = getattr(e, 'status_code', 500) if hasattr(e, 'status_code') else 500
        return {
            'statusCode': status_code,
            'headers': get_cors_headers(),
            'body': json.dumps(error_response)
        }


def handle_cancel_job(event: Dict[str, Any], context: Any, job_id: str) -> Dict[str, Any]:
    """
    Handle DELETE /api/v1/jobs/{job_id} endpoint.
    
    Cancels a job by job_id.
    
    Args:
        event: API Gateway HTTP API event
        context: Lambda context object
        job_id: Job identifier
        
    Returns:
        API Gateway HTTP API response with updated job data
    """
    request_id = event.get('requestContext', {}).get('requestId', '')
    logger.set_request_id(request_id)
    logger.set_job_id(job_id)
    
    try:
        # Create job service
        job_service = JobService()
        
        # Cancel job
        job = job_service.cancel_job(job_id)
        
        logger.info(
            f"Job cancelled: {job_id}",
            context={'job_id': job_id}
        )
        
        # Return success response
        response_body = {
            'status': 'success',
            'data': job.to_dict(),
            'meta': {'request_id': request_id}
        }
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
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
        
        error_response = format_error_response(e, request_id=request_id)
        status_code = getattr(e, 'status_code', 500) if hasattr(e, 'status_code') else 500
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

