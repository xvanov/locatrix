"""
Error handling utility with custom exception classes and error formatting.

This module provides custom exception classes with error codes and
user-friendly messages according to the architecture specification.
"""
from typing import Optional, Dict, Any


class LocationDetectionError(Exception):
    """Base exception class for Location Detection AI service errors."""
    
    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500
    ):
        """
        Initialize error.
        
        Args:
            code: Error code (e.g., 'INVALID_FILE_FORMAT')
            message: User-friendly error message
            details: Additional error details (default: None)
            status_code: HTTP status code (default: 500)
        """
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert error to dictionary format for API responses.
        
        Returns:
            Dictionary with error code, message, and details
        """
        error_dict = {
            'code': self.code,
            'message': self.message
        }
        
        if self.details:
            error_dict['details'] = self.details
        
        return error_dict
    
    def to_api_response(self, request_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Convert error to API response format.
        
        Args:
            request_id: Request ID for correlation (default: None)
            
        Returns:
            API response dictionary with error format
        """
        response = {
            'status': 'error',
            'error': self.to_dict()
        }
        
        if request_id:
            response['meta'] = {'request_id': request_id}
        
        return response


class InvalidFileFormatError(LocationDetectionError):
    """Error raised when file format is not supported."""
    
    def __init__(self, received_format: str, allowed_formats: list = None):
        """
        Initialize invalid file format error.
        
        Args:
            received_format: Format that was received
            allowed_formats: List of allowed formats (default: ['png', 'jpg', 'pdf'])
        """
        if allowed_formats is None:
            allowed_formats = ['png', 'jpg', 'pdf']
        
        message = f"File format must be one of: {', '.join(allowed_formats).upper()}"
        details = {
            'received_format': received_format,
            'allowed_formats': allowed_formats
        }
        
        super().__init__(
            code='INVALID_FILE_FORMAT',
            message=message,
            details=details,
            status_code=400
        )


class FileTooLargeError(LocationDetectionError):
    """Error raised when file size exceeds limit."""
    
    def __init__(self, file_size: int, max_size: int):
        """
        Initialize file too large error.
        
        Args:
            file_size: Size of the file in bytes
            max_size: Maximum allowed size in bytes
        """
        message = f"File size ({file_size} bytes) exceeds maximum allowed size ({max_size} bytes)"
        details = {
            'file_size': file_size,
            'max_size': max_size
        }
        
        super().__init__(
            code='FILE_TOO_LARGE',
            message=message,
            details=details,
            status_code=400
        )


class JobNotFoundError(LocationDetectionError):
    """Error raised when job ID is not found."""
    
    def __init__(self, job_id: str):
        """
        Initialize job not found error.
        
        Args:
            job_id: Job ID that was not found
        """
        message = f"Job '{job_id}' not found"
        details = {
            'job_id': job_id
        }
        
        super().__init__(
            code='JOB_NOT_FOUND',
            message=message,
            details=details,
            status_code=404
        )


class JobAlreadyCompletedError(LocationDetectionError):
    """Error raised when attempting to cancel a completed or failed job."""
    
    def __init__(self, job_id: str, current_status: str):
        """
        Initialize job already completed error.
        
        Args:
            job_id: Job ID
            current_status: Current status of the job
        """
        message = f"Job '{job_id}' cannot be cancelled because it is already {current_status}"
        details = {
            'job_id': job_id,
            'current_status': current_status
        }
        
        super().__init__(
            code='JOB_ALREADY_COMPLETED',
            message=message,
            details=details,
            status_code=400
        )


class ServiceUnavailableError(LocationDetectionError):
    """Error raised when AWS service is unavailable."""
    
    def __init__(self, service_name: str, retry_after: Optional[int] = None):
        """
        Initialize service unavailable error.
        
        Args:
            service_name: Name of the unavailable service
            retry_after: Seconds to wait before retrying (default: None)
        """
        message = f"Service '{service_name}' is currently unavailable"
        details = {
            'service_name': service_name
        }
        
        if retry_after:
            details['retry_after'] = retry_after
        
        super().__init__(
            code='SERVICE_UNAVAILABLE',
            message=message,
            details=details,
            status_code=503
        )


class RateLimitExceededError(LocationDetectionError):
    """Error raised when rate limit is exceeded."""
    
    def __init__(self, retry_after: Optional[int] = None):
        """
        Initialize rate limit exceeded error.
        
        Args:
            retry_after: Seconds to wait before retrying (default: None)
        """
        message = "Rate limit exceeded. Please try again later"
        details = {}
        
        if retry_after:
            details['retry_after'] = retry_after
        
        super().__init__(
            code='RATE_LIMIT_EXCEEDED',
            message=message,
            details=details,
            status_code=429
        )


def format_error_response(error: Exception, request_id: Optional[str] = None, api_version: Optional[str] = None) -> Dict[str, Any]:
    """
    Format an exception as an API error response.
    
    Args:
        error: Exception to format
        request_id: Request ID for correlation (default: None)
        api_version: API version string (default: None)
        
    Returns:
        API response dictionary with error format
        
    Example:
        >>> try:
        >>>     # Some operation
        >>> except JobNotFoundError as e:
        >>>     return format_error_response(e, request_id='req_123', api_version='v1')
    """
    if isinstance(error, LocationDetectionError):
        response = error.to_api_response(request_id=request_id)
        # Add API version to meta if provided
        if api_version and 'meta' in response:
            response['meta']['api_version'] = api_version
        elif api_version:
            response['meta'] = {'request_id': request_id, 'api_version': api_version}
        return response
    
    # Generic error for unexpected exceptions
    generic_error = LocationDetectionError(
        code='INTERNAL_ERROR',
        message='An internal error occurred',
        details={'error_type': type(error).__name__},
        status_code=500
    )
    
    response = generic_error.to_api_response(request_id=request_id)
    # Add API version to meta if provided
    if api_version and 'meta' in response:
        response['meta']['api_version'] = api_version
    elif api_version:
        response['meta'] = {'request_id': request_id, 'api_version': api_version}
    
    return response

