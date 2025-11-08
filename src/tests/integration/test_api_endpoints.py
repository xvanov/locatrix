"""
Integration tests for REST API endpoints.
"""
import pytest
import json
import base64
from unittest.mock import patch, MagicMock

from src.api.rest_api import handler
from src.models.job import Job, JobStatus


@pytest.fixture
def mock_job_service():
    """Mock JobService."""
    with patch('src.api.rest_api.JobService') as mock_service_class:
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        yield mock_service


@pytest.fixture
def api_event_base():
    """Base API Gateway event structure."""
    return {
        'requestContext': {
            'requestId': 'req_123',
            'http': {
                'method': 'GET',
                'path': '/health'
            }
        },
        'body': None
    }


class TestHealthCheck:
    """Test health check endpoint."""
    
    def test_health_check_success(self, api_event_base):
        """Test successful health check."""
        response = handler(api_event_base, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'healthy'
        assert 'data' in body
        assert 'services' in body['data']
        assert 'meta' in body
        assert 'request_id' in body['meta']
        assert 'api_version' in body['meta']


class TestCreateJob:
    """Test create job endpoint."""
    
    def test_create_job_success(self, api_event_base, mock_job_service):
        """Test successful job creation."""
        # Setup mock job
        mock_job = Job(
            job_id='job_123',
            status=JobStatus.PENDING,
            blueprint_format='pdf',
            blueprint_hash='abc123'
        )
        mock_job_service.create_job.return_value = mock_job
        
        # Setup event with valid PDF file content (PDF signature: %PDF)
        # Create minimal valid PDF content
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 1\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF'
        encoded_file = base64.b64encode(pdf_content).decode('utf-8')
        
        api_event_base['requestContext']['http']['method'] = 'POST'
        api_event_base['requestContext']['http']['path'] = '/api/v1/jobs'
        api_event_base['body'] = json.dumps({
            'blueprint': {
                'file': encoded_file,
                'format': 'pdf',
                'filename': 'test.pdf'
            }
        })
        
        response = handler(api_event_base, None)
        
        assert response['statusCode'] == 201
        body = json.loads(response['body'])
        assert body['status'] == 'success'
        assert body['data']['job_id'] == 'job_123'
        # Verify meta fields
        assert 'meta' in body
        assert 'request_id' in body['meta']
        assert 'api_version' in body['meta']
        # Verify create_job was called with new parameters
        call_args = mock_job_service.create_job.call_args
        assert call_args is not None
        # Check that request_id, correlation_id, and api_version are passed
        assert 'request_id' in call_args.kwargs or len(call_args.args) >= 4
        mock_job_service.create_job.assert_called_once()
    
    def test_create_job_invalid_format(self, api_event_base):
        """Test job creation with invalid format."""
        # Use invalid format (gif) - will fail format validation before MIME check
        file_content = b'test file content'
        encoded_file = base64.b64encode(file_content).decode('utf-8')
        
        api_event_base['requestContext']['http']['method'] = 'POST'
        api_event_base['requestContext']['http']['path'] = '/api/v1/jobs'
        api_event_base['body'] = json.dumps({
            'blueprint': {
                'file': encoded_file,
                'format': 'gif'
            }
        })
        
        response = handler(api_event_base, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['status'] == 'error'
        assert body['error']['code'] == 'INVALID_FILE_FORMAT'
        # Verify meta fields
        assert 'meta' in body
        assert 'request_id' in body['meta']
    
    def test_create_job_file_too_large(self, api_event_base):
        """Test job creation with file too large."""
        # Create a file larger than 50MB with valid PDF signature
        large_file = b'%PDF-1.4\n' + (b'x' * (51 * 1024 * 1024))
        encoded_file = base64.b64encode(large_file).decode('utf-8')
        
        api_event_base['requestContext']['http']['method'] = 'POST'
        api_event_base['requestContext']['http']['path'] = '/api/v1/jobs'
        api_event_base['body'] = json.dumps({
            'blueprint': {
                'file': encoded_file,
                'format': 'pdf'
            }
        })
        
        response = handler(api_event_base, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['status'] == 'error'
        assert body['error']['code'] == 'FILE_TOO_LARGE'
        # Verify meta fields
        assert 'meta' in body
        assert 'request_id' in body['meta']


class TestGetJob:
    """Test get job endpoint."""
    
    def test_get_job_success(self, api_event_base, mock_job_service):
        """Test successful job retrieval."""
        mock_job = Job(
            job_id='job_123',
            status=JobStatus.PENDING,
            blueprint_format='pdf'
        )
        mock_job_service.get_job.return_value = mock_job
        
        api_event_base['requestContext']['http']['method'] = 'GET'
        api_event_base['requestContext']['http']['path'] = '/api/v1/jobs/job_123'
        
        response = handler(api_event_base, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'success'
        assert body['data']['job_id'] == 'job_123'
        # Verify meta fields
        assert 'meta' in body
        assert 'request_id' in body['meta']
        assert 'api_version' in body['meta']
        assert 'X-Request-ID' in response['headers']
        mock_job_service.get_job.assert_called_once_with('job_123')
    
    def test_get_job_not_found(self, api_event_base, mock_job_service):
        """Test job not found."""
        from src.utils.errors import JobNotFoundError
        mock_job_service.get_job.side_effect = JobNotFoundError('job_123')
        
        api_event_base['requestContext']['http']['method'] = 'GET'
        api_event_base['requestContext']['http']['path'] = '/api/v1/jobs/job_123'
        
        response = handler(api_event_base, None)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['status'] == 'error'
        assert body['error']['code'] == 'JOB_NOT_FOUND'


class TestCancelJob:
    """Test cancel job endpoint."""
    
    def test_cancel_job_success(self, api_event_base, mock_job_service):
        """Test successful job cancellation."""
        mock_job = Job(
            job_id='job_123',
            status=JobStatus.CANCELLED,
            blueprint_format='pdf'
        )
        mock_job_service.cancel_job.return_value = mock_job
        
        api_event_base['requestContext']['http']['method'] = 'DELETE'
        api_event_base['requestContext']['http']['path'] = '/api/v1/jobs/job_123'
        
        response = handler(api_event_base, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'success'
        assert body['data']['status'] == 'cancelled'
        # Verify meta fields
        assert 'meta' in body
        assert 'request_id' in body['meta']
        assert 'api_version' in body['meta']
        assert 'X-Request-ID' in response['headers']
        mock_job_service.cancel_job.assert_called_once_with('job_123')
    
    def test_cancel_job_already_completed(self, api_event_base, mock_job_service):
        """Test cancelling already completed job."""
        from src.utils.errors import JobAlreadyCompletedError
        mock_job_service.cancel_job.side_effect = JobAlreadyCompletedError('job_123', 'completed')
        
        api_event_base['requestContext']['http']['method'] = 'DELETE'
        api_event_base['requestContext']['http']['path'] = '/api/v1/jobs/job_123'
        
        response = handler(api_event_base, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['status'] == 'error'
        assert body['error']['code'] == 'JOB_ALREADY_COMPLETED'


class TestCORS:
    """Test CORS headers."""
    
    def test_cors_headers_present(self, api_event_base):
        """Test CORS headers are present in responses."""
        response = handler(api_event_base, None)
        
        headers = response['headers']
        assert 'Access-Control-Allow-Origin' in headers
        assert headers['Access-Control-Allow-Origin'] == '*'
    
    def test_options_request(self, api_event_base):
        """Test OPTIONS request for CORS preflight."""
        api_event_base['requestContext']['http']['method'] = 'OPTIONS'
        
        response = handler(api_event_base, None)
        
        assert response['statusCode'] == 200
        assert response['body'] == ''

