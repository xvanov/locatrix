"""
Test fixtures for feedback testing.

These fixtures provide reusable test setup and teardown for feedback tests.
"""
import pytest
from unittest.mock import patch, MagicMock

from src.models.job import Job, JobStatus
from src.tests.support.factories.feedback_factory import (
    create_feedback_dict,
    create_feedback_list,
    generate_job_id
)


@pytest.fixture
def mock_feedback_service():
    """Mock FeedbackService for testing."""
    with patch('src.services.feedback_service.FeedbackService') as mock_service_class:
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        yield mock_service


@pytest.fixture
def mock_job_service():
    """Mock JobService for testing."""
    with patch('src.services.job_service.JobService') as mock_service_class:
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        yield mock_service


@pytest.fixture
def existing_job():
    """
    Create an existing job fixture.
    
    Returns:
        Job instance with valid data
    """
    return Job(
        job_id=generate_job_id(),
        status=JobStatus.PENDING,
        blueprint_format='pdf',
        blueprint_hash='abc123'
    )


@pytest.fixture
def completed_job():
    """
    Create a completed job fixture.
    
    Returns:
        Job instance with COMPLETED status
    """
    return Job(
        job_id=generate_job_id(),
        status=JobStatus.COMPLETED,
        blueprint_format='pdf',
        blueprint_hash='abc123'
    )


@pytest.fixture
def sample_feedback():
    """
    Create a sample feedback dictionary.
    
    Returns:
        Feedback dictionary with valid data
    """
    return create_feedback_dict({
        'feedback': 'wrong',
        'room_id': 'room_001',
        'correction': {
            'bounding_box': [60, 60, 210, 310]
        }
    })


@pytest.fixture
def sample_feedback_list():
    """
    Create a list of sample feedback items.
    
    Returns:
        List of feedback dictionaries
    """
    job_id = generate_job_id()
    return create_feedback_list(3, job_id=job_id)


@pytest.fixture
def mock_dynamodb_table():
    """
    Mock DynamoDB table for feedback operations.
    
    Returns:
        Mock DynamoDB table
    """
    with patch('src.services.feedback_service.boto3') as mock_boto3:
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table
        yield mock_table


@pytest.fixture
def api_event_base():
    """
    Base API Gateway event structure for testing.
    
    Returns:
        Base API Gateway event dictionary
    """
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


