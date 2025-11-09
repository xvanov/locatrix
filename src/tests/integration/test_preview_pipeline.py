"""
Integration tests for preview pipeline endpoints.
"""
import pytest
import json
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
def mock_preview_service():
    """Mock PreviewService."""
    with patch('src.api.rest_api.PreviewService') as mock_service_class:
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        yield mock_service


@pytest.fixture
def mock_preview_lambda():
    """Mock preview Lambda handler."""
    with patch('src.api.rest_api.preview_lambda_handler') as mock_handler:
        yield mock_handler


@pytest.fixture
def api_event_base():
    """Base API Gateway event structure."""
    return {
        'requestContext': {
            'requestId': 'req_123',
            'http': {
                'method': 'POST',
                'path': '/api/v1/jobs/job_123/preview'
            }
        },
        'headers': {},
        'body': '{}'
    }


@pytest.fixture
def sample_job():
    """Sample job for testing."""
    return Job(
        job_id='job_123',
        status=JobStatus.PENDING,
        blueprint_s3_key='blueprints/job_123/blueprint.pdf',
        blueprint_format='pdf',
        blueprint_hash='abc123def456'
    )


@pytest.fixture
def sample_preview_result():
    """Sample preview result."""
    return {
        'job_id': 'job_123',
        'stage': 'preview',
        'rooms': [
            {
                'id': 'room_001',
                'bounding_box': [50, 50, 200, 300],
                'name_hint': 'Kitchen',
                'confidence': 0.75
            }
        ],
        'processing_time_seconds': 3.2,
        'timestamp': '2024-01-15T10:30:00Z',
        'timing_metrics': {
            'textract_analysis_seconds': 2.1,
            'room_detection_seconds': 0.5,
            'total_seconds': 3.2
        }
    }


class TestTriggerPreview:
    """Test POST /api/v1/jobs/{job_id}/preview endpoint."""
    
    def test_trigger_preview_success(
        self, api_event_base, mock_job_service, mock_preview_lambda, sample_preview_result
    ):
        """Test successful preview trigger."""
        # Mock preview Lambda response
        mock_preview_lambda.return_value = {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'success',
                'data': sample_preview_result
            })
        }
        
        response = handler(api_event_base, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'success'
        assert body['data']['job_id'] == 'job_123'
        assert body['data']['stage'] == 'preview'
        assert len(body['data']['rooms']) == 1
        
        # Verify preview Lambda was called
        mock_preview_lambda.assert_called_once()
        call_args = mock_preview_lambda.call_args
        assert call_args[0][0]['job_id'] == 'job_123'
    
    def test_trigger_preview_invalid_job_id(self, api_event_base):
        """Test preview trigger with invalid job ID."""
        api_event_base['requestContext']['http']['path'] = '/api/v1/jobs/invalid/preview'
        
        response = handler(api_event_base, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['status'] == 'error'
        assert body['error']['code'] == 'INVALID_JOB_ID'
    
    def test_trigger_preview_lambda_error(
        self, api_event_base, mock_preview_lambda
    ):
        """Test preview trigger when Lambda returns error."""
        mock_preview_lambda.return_value = {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'error',
                'error': {
                    'code': 'INTERNAL_ERROR',
                    'message': 'Preview processing failed'
                }
            })
        }
        
        response = handler(api_event_base, None)
        
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert body['status'] == 'error'


class TestGetPreview:
    """Test GET /api/v1/jobs/{job_id}/preview endpoint."""
    
    def test_get_preview_success(
        self, mock_job_service, mock_preview_service, sample_job, sample_preview_result
    ):
        """Test successful preview retrieval from cache."""
        mock_job_service.get_job.return_value = sample_job
        mock_preview_service.get_cached_preview.return_value = sample_preview_result
        
        event = {
            'requestContext': {
                'requestId': 'req_123',
                'http': {
                    'method': 'GET',
                    'path': '/api/v1/jobs/job_123/preview'
                }
            },
            'headers': {},
            'body': None
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'success'
        assert body['data']['job_id'] == 'job_123'
        assert body['data']['stage'] == 'preview'
        
        # Verify cache lookup was called
        mock_preview_service.get_cached_preview.assert_called_once_with('abc123def456')
    
    def test_get_preview_not_found(
        self, mock_job_service, mock_preview_service, sample_job
    ):
        """Test preview retrieval when not cached."""
        mock_job_service.get_job.return_value = sample_job
        mock_preview_service.get_cached_preview.return_value = None
        
        event = {
            'requestContext': {
                'requestId': 'req_123',
                'http': {
                    'method': 'GET',
                    'path': '/api/v1/jobs/job_123/preview'
                }
            },
            'headers': {},
            'body': None
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['status'] == 'error'
        assert body['error']['code'] == 'PREVIEW_NOT_FOUND'


class TestGetTextractResults:
    """Test GET /api/v1/jobs/{job_id}/textract-results endpoint."""
    
    def test_get_textract_results_success(
        self, mock_job_service, mock_preview_service, sample_job
    ):
        """Test successful Textract results retrieval."""
        mock_job_service.get_job.return_value = sample_job
        mock_preview_service.get_textract_results.return_value = {
            'text_blocks': [{'id': '1', 'text': 'Room'}],
            'layout_blocks': [{'id': '2', 'blockType': 'TABLE'}],
            'metadata': {'pages': 1}
        }
        
        event = {
            'requestContext': {
                'requestId': 'req_123',
                'http': {
                    'method': 'GET',
                    'path': '/api/v1/jobs/job_123/textract-results'
                }
            },
            'headers': {},
            'body': None
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'success'
        assert 'text_blocks' in body['data']
        assert 'layout_blocks' in body['data']
        assert body['data']['s3_key'] == 'cache/textract/job_123/analysis.json'
        
        # Verify S3 retrieval was called
        mock_preview_service.get_textract_results.assert_called_once_with('job_123')
    
    def test_get_textract_results_not_found(
        self, mock_job_service, mock_preview_service, sample_job
    ):
        """Test Textract results retrieval when not found."""
        mock_job_service.get_job.return_value = sample_job
        mock_preview_service.get_textract_results.return_value = None
        
        event = {
            'requestContext': {
                'requestId': 'req_123',
                'http': {
                    'method': 'GET',
                    'path': '/api/v1/jobs/job_123/textract-results'
                }
            },
            'headers': {},
            'body': None
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['status'] == 'error'
        assert body['error']['code'] == 'TEXTRACT_RESULTS_NOT_FOUND'

