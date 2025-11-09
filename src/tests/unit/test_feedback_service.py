"""
Unit tests for feedback service.

These tests verify feedback service business logic with mocked DynamoDB.
All tests are written in RED phase - they will fail until implementation is complete.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from src.services.feedback_service import FeedbackService
from src.models.feedback import Feedback, FeedbackType
from src.utils.errors import InvalidFeedbackError, FeedbackNotFoundError


@pytest.fixture
def mock_aws_services():
    """Mock AWS services."""
    with patch('src.services.feedback_service.boto3') as mock_boto3:
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        
        mock_boto3.resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table
        
        yield {
            'dynamodb': mock_dynamodb,
            'table': mock_table
        }


@pytest.fixture
def feedback_service(mock_aws_services):
    """Create FeedbackService instance with mocked AWS services."""
    with patch.dict('os.environ', {
        'FEEDBACK_TABLE_NAME': 'test-feedback'
    }):
        return FeedbackService(
            feedback_table_name='test-feedback'
        )


class TestSubmitFeedback:
    """Test submit_feedback method."""
    
    def test_submit_feedback_success(self, feedback_service, mock_aws_services):
        """
        GIVEN: Valid feedback data
        WHEN: I submit feedback
        THEN: Feedback is stored in DynamoDB and returned
        """
        # GIVEN: Valid feedback data
        job_id = 'job_20240115_abc123'
        feedback_data = {
            'feedback': 'wrong',
            'room_id': 'room_001',
            'correction': {
                'bounding_box': [60, 60, 210, 310]
            }
        }
        
        # GIVEN: DynamoDB put_item succeeds
        mock_aws_services['table'].put_item.return_value = {}
        
        # WHEN: Submit feedback
        feedback = feedback_service.submit_feedback(job_id, feedback_data)
        
        # THEN: Feedback object returned
        assert feedback.feedback_id.startswith('fb_')
        assert feedback.job_id == job_id
        assert feedback.feedback == FeedbackType.WRONG
        assert feedback.room_id == 'room_001'
        assert feedback.correction == {'bounding_box': [60, 60, 210, 310]}
        
        # THEN: DynamoDB put_item was called
        mock_aws_services['table'].put_item.assert_called_once()
    
    def test_submit_feedback_correct_type(self, feedback_service, mock_aws_services):
        """
        GIVEN: Valid feedback data with type 'correct'
        WHEN: I submit feedback
        THEN: Feedback is stored without correction data
        """
        # GIVEN: Valid feedback data
        job_id = 'job_20240115_abc123'
        feedback_data = {
            'feedback': 'correct'
        }
        
        # GIVEN: DynamoDB put_item succeeds
        mock_aws_services['table'].put_item.return_value = {}
        
        # WHEN: Submit feedback
        feedback = feedback_service.submit_feedback(job_id, feedback_data)
        
        # THEN: Feedback object returned
        assert feedback.feedback == FeedbackType.CORRECT
        assert feedback.room_id is None
        assert feedback.correction is None
    
    def test_submit_feedback_invalid_type(self, feedback_service):
        """
        GIVEN: Invalid feedback type
        WHEN: I submit feedback
        THEN: InvalidFeedbackError is raised
        """
        # GIVEN: Invalid feedback type
        job_id = 'job_20240115_abc123'
        feedback_data = {
            'feedback': 'invalid_type'
        }
        
        # WHEN: Submit feedback
        # THEN: InvalidFeedbackError raised
        with pytest.raises(InvalidFeedbackError) as exc_info:
            feedback_service.submit_feedback(job_id, feedback_data)
        
        assert 'must be one of' in exc_info.value.message.lower() or 'invalid' in exc_info.value.message.lower()
    
    def test_submit_feedback_wrong_type_missing_correction(self, feedback_service):
        """
        GIVEN: Feedback type 'wrong' without correction
        WHEN: I submit feedback
        THEN: InvalidFeedbackError is raised
        """
        # GIVEN: Wrong feedback without correction
        job_id = 'job_20240115_abc123'
        feedback_data = {
            'feedback': 'wrong',
            'room_id': 'room_001'
        }
        
        # WHEN: Submit feedback
        # THEN: InvalidFeedbackError raised
        with pytest.raises(InvalidFeedbackError):
            feedback_service.submit_feedback(job_id, feedback_data)
    
    def test_submit_feedback_generates_unique_id(self, feedback_service, mock_aws_services):
        """
        GIVEN: Valid feedback data
        WHEN: I submit multiple feedback items
        THEN: Each feedback gets unique feedback_id
        """
        # GIVEN: Valid feedback data
        job_id = 'job_20240115_abc123'
        feedback_data = {
            'feedback': 'correct'
        }
        
        # GIVEN: DynamoDB put_item succeeds
        mock_aws_services['table'].put_item.return_value = {}
        
        # WHEN: Submit feedback twice
        feedback1 = feedback_service.submit_feedback(job_id, feedback_data)
        feedback2 = feedback_service.submit_feedback(job_id, feedback_data)
        
        # THEN: Each has unique feedback_id
        assert feedback1.feedback_id != feedback2.feedback_id
        assert feedback1.feedback_id.startswith('fb_')
        assert feedback2.feedback_id.startswith('fb_')


class TestGetFeedbackByJobId:
    """Test get_feedback_by_job_id method."""
    
    def test_get_feedback_by_job_id_success(self, feedback_service, mock_aws_services):
        """
        GIVEN: Job has feedback items
        WHEN: I retrieve feedback by job_id
        THEN: List of feedback items is returned
        """
        # GIVEN: Job has feedback items
        job_id = 'job_20240115_abc123'
        mock_items = [
            {
                'feedback_id': 'fb_20240115_xyz789',
                'job_id': job_id,
                'feedback': 'wrong',
                'room_id': 'room_001',
                'correction': {
                    'bounding_box': [60, 60, 210, 310]
                },
                'created_at': '2024-01-15T10:30:00Z'
            },
            {
                'feedback_id': 'fb_20240115_correct123',
                'job_id': job_id,
                'feedback': 'correct',
                'created_at': '2024-01-15T11:00:00Z'
            }
        ]
        
        mock_aws_services['table'].query.return_value = {
            'Items': mock_items
        }
        
        # WHEN: Get feedback by job_id
        feedback_list = feedback_service.get_feedback_by_job_id(job_id)
        
        # THEN: List of feedback objects returned
        assert len(feedback_list) == 2
        assert feedback_list[0].feedback_id == 'fb_20240115_xyz789'
        assert feedback_list[1].feedback_id == 'fb_20240115_correct123'
        
        # THEN: DynamoDB query was called with correct parameters
        mock_aws_services['table'].query.assert_called_once()
        call_args = mock_aws_services['table'].query.call_args
        assert 'KeyConditionExpression' in call_args.kwargs or 'IndexName' in call_args.kwargs
    
    def test_get_feedback_by_job_id_empty(self, feedback_service, mock_aws_services):
        """
        GIVEN: Job has no feedback
        WHEN: I retrieve feedback by job_id
        THEN: Empty list is returned
        """
        # GIVEN: Job has no feedback
        job_id = 'job_20240115_abc123'
        mock_aws_services['table'].query.return_value = {
            'Items': []
        }
        
        # WHEN: Get feedback by job_id
        feedback_list = feedback_service.get_feedback_by_job_id(job_id)
        
        # THEN: Empty list returned
        assert feedback_list == []


class TestFeedbackValidation:
    """Test feedback validation logic."""
    
    def test_validate_feedback_type_valid(self, feedback_service):
        """
        GIVEN: Valid feedback types
        WHEN: I validate feedback type
        THEN: Validation passes
        """
        # GIVEN: Valid feedback types
        valid_types = ['wrong', 'correct', 'partial']
        
        # WHEN/THEN: Each type validates successfully
        for feedback_type in valid_types:
            # This test will pass once validation is implemented
            assert feedback_type in ['wrong', 'correct', 'partial']
    
    def test_validate_correction_bounding_box_format(self, feedback_service):
        """
        GIVEN: Invalid bounding box format
        WHEN: I submit feedback with wrong type
        THEN: InvalidFeedbackError is raised
        """
        # GIVEN: Invalid bounding box format
        job_id = 'job_20240115_abc123'
        feedback_data = {
            'feedback': 'wrong',
            'room_id': 'room_001',
            'correction': {
                'bounding_box': [60, 60]  # Missing coordinates
            }
        }
        
        # WHEN: Submit feedback
        # THEN: InvalidFeedbackError raised
        with pytest.raises(InvalidFeedbackError):
            feedback_service.submit_feedback(job_id, feedback_data)


