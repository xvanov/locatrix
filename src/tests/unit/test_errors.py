"""
Unit tests for error handling utility.
"""
from src.utils.errors import (
    LocationDetectionError,
    InvalidFileFormatError,
    FileTooLargeError,
    JobNotFoundError,
    JobAlreadyCompletedError,
    format_error_response
)


class TestLocationDetectionError:
    """Test LocationDetectionError base class."""

    def test_error_creation(self):
        """Test error creation."""
        error = LocationDetectionError(
            code='TEST_ERROR',
            message='Test error message',
            details={'key': 'value'},
            status_code=400
        )

        assert error.code == 'TEST_ERROR'
        assert error.message == 'Test error message'
        assert error.details == {'key': 'value'}
        assert error.status_code == 400

    def test_to_dict(self):
        """Test error to dictionary conversion."""
        error = LocationDetectionError(
            code='TEST_ERROR',
            message='Test error message',
            details={'key': 'value'}
        )

        error_dict = error.to_dict()
        assert error_dict['code'] == 'TEST_ERROR'
        assert error_dict['message'] == 'Test error message'
        assert error_dict['details'] == {'key': 'value'}

    def test_to_api_response(self):
        """Test error to API response conversion."""
        error = LocationDetectionError(
            code='TEST_ERROR',
            message='Test error message'
        )

        response = error.to_api_response(request_id='req_123')
        assert response['status'] == 'error'
        assert response['error']['code'] == 'TEST_ERROR'
        assert response['meta']['request_id'] == 'req_123'


class TestInvalidFileFormatError:
    """Test InvalidFileFormatError."""

    def test_invalid_file_format_error(self):
        """Test invalid file format error."""
        error = InvalidFileFormatError('gif', ['png', 'jpg', 'pdf'])

        assert error.code == 'INVALID_FILE_FORMAT'
        assert error.status_code == 400
        assert error.details['received_format'] == 'gif'
        assert 'png' in error.details['allowed_formats']


class TestFileTooLargeError:
    """Test FileTooLargeError."""

    def test_file_too_large_error(self):
        """Test file too large error."""
        error = FileTooLargeError(file_size=100000000, max_size=50000000)

        assert error.code == 'FILE_TOO_LARGE'
        assert error.status_code == 400
        assert error.details['file_size'] == 100000000
        assert error.details['max_size'] == 50000000


class TestJobNotFoundError:
    """Test JobNotFoundError."""

    def test_job_not_found_error(self):
        """Test job not found error."""
        error = JobNotFoundError('job_123')

        assert error.code == 'JOB_NOT_FOUND'
        assert error.status_code == 404
        assert error.details['job_id'] == 'job_123'


class TestJobAlreadyCompletedError:
    """Test JobAlreadyCompletedError."""

    def test_job_already_completed_error(self):
        """Test job already completed error."""
        error = JobAlreadyCompletedError('job_123', 'completed')

        assert error.code == 'JOB_ALREADY_COMPLETED'
        assert error.status_code == 400
        assert error.details['job_id'] == 'job_123'
        assert error.details['current_status'] == 'completed'


class TestFormatErrorResponse:
    """Test format_error_response function."""

    def test_format_custom_error(self):
        """Test formatting custom error."""
        error = JobNotFoundError('job_123')
        response = format_error_response(error, request_id='req_123')

        assert response['status'] == 'error'
        assert response['error']['code'] == 'JOB_NOT_FOUND'
        assert response['meta']['request_id'] == 'req_123'

    def test_format_generic_error(self):
        """Test formatting generic error."""
        error = ValueError('Generic error')
        response = format_error_response(error, request_id='req_123')

        assert response['status'] == 'error'
        assert response['error']['code'] == 'INTERNAL_ERROR'
        assert response['meta']['request_id'] == 'req_123'

