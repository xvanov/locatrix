"""
Integration tests for feedback API endpoints.

These tests verify the feedback endpoints end-to-end with mocked DynamoDB.
All tests are written in RED phase - they will fail until implementation is complete.
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
def mock_feedback_service():
    """Mock FeedbackService."""
    with patch('src.api.rest_api.FeedbackService') as mock_service_class:
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
        'headers': {},
        'body': None
    }


@pytest.fixture
def existing_job():
    """Create an existing job for testing."""
    return Job(
        job_id='job_20240115_abc123',
        status=JobStatus.PENDING,
        blueprint_format='pdf',
        blueprint_hash='abc123'
    )


class TestSubmitFeedback:
    """Test POST /api/v1/jobs/{job_id}/feedback endpoint."""
    
    def test_submit_feedback_success(self, api_event_base, mock_job_service, mock_feedback_service, existing_job):
        """
        GIVEN: A valid job exists
        WHEN: I submit feedback with valid data
        THEN: Feedback is stored and success response is returned
        """
        # GIVEN: Job exists
        mock_job_service.get_job.return_value = existing_job
        
        # GIVEN: Feedback service returns success
        mock_feedback = {
            'feedback_id': 'fb_20240115_xyz789',
            'job_id': 'job_20240115_abc123',
            'feedback': 'wrong',
            'room_id': 'room_001',
            'correction': {
                'bounding_box': [60, 60, 210, 310]
            },
            'created_at': '2024-01-15T10:30:00Z'
        }
        mock_feedback_service.submit_feedback.return_value = mock_feedback
        
        # WHEN: Submit feedback
        api_event_base['requestContext']['http']['method'] = 'POST'
        api_event_base['requestContext']['http']['path'] = '/api/v1/jobs/job_20240115_abc123/feedback'
        api_event_base['body'] = json.dumps({
            'feedback': 'wrong',
            'room_id': 'room_001',
            'correction': {
                'bounding_box': [60, 60, 210, 310]
            }
        })
        
        response = handler(api_event_base, None)
        
        # THEN: Success response returned
        assert response['statusCode'] == 201
        body = json.loads(response['body'])
        assert body['status'] == 'success'
        assert body['data']['feedback_id'] == 'fb_20240115_xyz789'
        assert body['data']['job_id'] == 'job_20240115_abc123'
        assert body['data']['message'] == 'Feedback submitted successfully'
        assert 'request_id' in body['data']
        assert 'meta' in body
        assert 'request_id' in body['meta']
        assert 'api_version' in body['meta']
    
    def test_submit_feedback_job_not_found(self, api_event_base, mock_job_service):
        """
        GIVEN: Job does not exist
        WHEN: I submit feedback for non-existent job
        THEN: 404 error is returned
        """
        # GIVEN: Job does not exist
        from src.utils.errors import JobNotFoundError
        mock_job_service.get_job.side_effect = JobNotFoundError('job_invalid')
        
        # WHEN: Submit feedback
        api_event_base['requestContext']['http']['method'] = 'POST'
        api_event_base['requestContext']['http']['path'] = '/api/v1/jobs/job_invalid/feedback'
        api_event_base['body'] = json.dumps({
            'feedback': 'wrong',
            'room_id': 'room_001'
        })
        
        response = handler(api_event_base, None)
        
        # THEN: 404 error returned
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['status'] == 'error'
        assert body['error']['code'] == 'JOB_NOT_FOUND'
        assert 'meta' in body
        assert 'request_id' in body['meta']
    
    def test_submit_feedback_invalid_type(self, api_event_base, mock_job_service, mock_feedback_service, existing_job):
        """
        GIVEN: A valid job exists
        WHEN: I submit feedback with invalid feedback type
        THEN: 400 error with INVALID_FEEDBACK code is returned
        """
        # GIVEN: Job exists
        mock_job_service.get_job.return_value = existing_job
        
        # GIVEN: Feedback service raises InvalidFeedbackError
        from src.utils.errors import InvalidFeedbackError
        mock_feedback_service.submit_feedback.side_effect = InvalidFeedbackError(
            "Feedback type must be one of: wrong, correct, partial",
            details={'received_type': 'invalid_type'}
        )
        
        # WHEN: Submit feedback with invalid type
        api_event_base['requestContext']['http']['method'] = 'POST'
        api_event_base['requestContext']['http']['path'] = '/api/v1/jobs/job_20240115_abc123/feedback'
        api_event_base['body'] = json.dumps({
            'feedback': 'invalid_type',
            'room_id': 'room_001'
        })
        
        response = handler(api_event_base, None)
        
        # THEN: 400 error returned
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['status'] == 'error'
        assert body['error']['code'] == 'INVALID_FEEDBACK'
        assert 'request_id' in body['error'].get('details', {}) or 'request_id' in body.get('meta', {})
        assert 'meta' in body
        assert 'request_id' in body['meta']
    
    def test_submit_feedback_missing_required_fields(self, api_event_base, mock_job_service, existing_job):
        """
        GIVEN: A valid job exists
        WHEN: I submit feedback without required fields
        THEN: 400 error with validation message is returned
        """
        # GIVEN: Job exists
        mock_job_service.get_job.return_value = existing_job
        
        # WHEN: Submit feedback without feedback field
        api_event_base['requestContext']['http']['method'] = 'POST'
        api_event_base['requestContext']['http']['path'] = '/api/v1/jobs/job_20240115_abc123/feedback'
        api_event_base['body'] = json.dumps({
            'room_id': 'room_001'
        })
        
        response = handler(api_event_base, None)
        
        # THEN: 400 error returned
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['status'] == 'error'
        assert 'meta' in body
        assert 'request_id' in body['meta']
    
    def test_submit_feedback_correct_type(self, api_event_base, mock_job_service, mock_feedback_service, existing_job):
        """
        GIVEN: A valid job exists
        WHEN: I submit feedback with type 'correct'
        THEN: Feedback is stored without correction data
        """
        # GIVEN: Job exists
        mock_job_service.get_job.return_value = existing_job
        
        # GIVEN: Feedback service returns success
        mock_feedback = {
            'feedback_id': 'fb_20240115_correct123',
            'job_id': 'job_20240115_abc123',
            'feedback': 'correct',
            'created_at': '2024-01-15T10:30:00Z'
        }
        mock_feedback_service.submit_feedback.return_value = mock_feedback
        
        # WHEN: Submit correct feedback
        api_event_base['requestContext']['http']['method'] = 'POST'
        api_event_base['requestContext']['http']['path'] = '/api/v1/jobs/job_20240115_abc123/feedback'
        api_event_base['body'] = json.dumps({
            'feedback': 'correct'
        })
        
        response = handler(api_event_base, None)
        
        # THEN: Success response returned
        assert response['statusCode'] == 201
        body = json.loads(response['body'])
        assert body['status'] == 'success'
        assert body['data']['feedback_id'] == 'fb_20240115_correct123'
    
    def test_submit_feedback_partial_type(self, api_event_base, mock_job_service, mock_feedback_service, existing_job):
        """
        GIVEN: A valid job exists
        WHEN: I submit feedback with type 'partial'
        THEN: Feedback is stored with partial correction data
        """
        # GIVEN: Job exists
        mock_job_service.get_job.return_value = existing_job
        
        # GIVEN: Feedback service returns success
        mock_feedback = {
            'feedback_id': 'fb_20240115_partial456',
            'job_id': 'job_20240115_abc123',
            'feedback': 'partial',
            'room_id': 'room_002',
            'correction': {
                'bounding_box': [100, 100, 200, 200]
            },
            'created_at': '2024-01-15T10:30:00Z'
        }
        mock_feedback_service.submit_feedback.return_value = mock_feedback
        
        # WHEN: Submit partial feedback
        api_event_base['requestContext']['http']['method'] = 'POST'
        api_event_base['requestContext']['http']['path'] = '/api/v1/jobs/job_20240115_abc123/feedback'
        api_event_base['body'] = json.dumps({
            'feedback': 'partial',
            'room_id': 'room_002',
            'correction': {
                'bounding_box': [100, 100, 200, 200]
            }
        })
        
        response = handler(api_event_base, None)
        
        # THEN: Success response returned
        assert response['statusCode'] == 201
        body = json.loads(response['body'])
        assert body['status'] == 'success'
        assert body['data']['feedback_id'] == 'fb_20240115_partial456'


class TestGetFeedback:
    """Test GET /api/v1/jobs/{job_id}/feedback endpoint."""
    
    def test_get_feedback_success(self, api_event_base, mock_job_service, mock_feedback_service, existing_job):
        """
        GIVEN: A valid job exists with feedback
        WHEN: I retrieve feedback for the job
        THEN: List of feedback items is returned
        """
        # GIVEN: Job exists
        mock_job_service.get_job.return_value = existing_job
        
        # GIVEN: Feedback service returns list of feedback
        mock_feedback_list = [
            {
                'feedback_id': 'fb_20240115_xyz789',
                'job_id': 'job_20240115_abc123',
                'feedback': 'wrong',
                'room_id': 'room_001',
                'correction': {
                    'bounding_box': [60, 60, 210, 310]
                },
                'created_at': '2024-01-15T10:30:00Z'
            },
            {
                'feedback_id': 'fb_20240115_correct123',
                'job_id': 'job_20240115_abc123',
                'feedback': 'correct',
                'created_at': '2024-01-15T11:00:00Z'
            }
        ]
        mock_feedback_service.get_feedback_by_job_id.return_value = mock_feedback_list
        
        # WHEN: Get feedback
        api_event_base['requestContext']['http']['method'] = 'GET'
        api_event_base['requestContext']['http']['path'] = '/api/v1/jobs/job_20240115_abc123/feedback'
        
        response = handler(api_event_base, None)
        
        # THEN: Success response with feedback list returned
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'success'
        assert len(body['data']['feedback']) == 2
        assert body['data']['feedback'][0]['feedback_id'] == 'fb_20240115_xyz789'
        assert body['data']['feedback'][1]['feedback_id'] == 'fb_20240115_correct123'
        assert 'meta' in body
        assert 'request_id' in body['meta']
        assert 'api_version' in body['meta']
    
    def test_get_feedback_job_not_found(self, api_event_base, mock_job_service):
        """
        GIVEN: Job does not exist
        WHEN: I retrieve feedback for non-existent job
        THEN: 404 error is returned
        """
        # GIVEN: Job does not exist
        from src.utils.errors import JobNotFoundError
        mock_job_service.get_job.side_effect = JobNotFoundError('job_invalid')
        
        # WHEN: Get feedback
        api_event_base['requestContext']['http']['method'] = 'GET'
        api_event_base['requestContext']['http']['path'] = '/api/v1/jobs/job_invalid/feedback'
        
        response = handler(api_event_base, None)
        
        # THEN: 404 error returned
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['status'] == 'error'
        assert body['error']['code'] == 'JOB_NOT_FOUND'
        assert 'meta' in body
        assert 'request_id' in body['meta']
    
    def test_get_feedback_empty_list(self, api_event_base, mock_job_service, mock_feedback_service, existing_job):
        """
        GIVEN: A valid job exists with no feedback
        WHEN: I retrieve feedback for the job
        THEN: Empty list is returned
        """
        # GIVEN: Job exists
        mock_job_service.get_job.return_value = existing_job
        
        # GIVEN: No feedback exists
        mock_feedback_service.get_feedback_by_job_id.return_value = []
        
        # WHEN: Get feedback
        api_event_base['requestContext']['http']['method'] = 'GET'
        api_event_base['requestContext']['http']['path'] = '/api/v1/jobs/job_20240115_abc123/feedback'
        
        response = handler(api_event_base, None)
        
        # THEN: Success response with empty list returned
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'success'
        assert body['data']['feedback'] == []
        assert 'meta' in body
        assert 'request_id' in body['meta']

