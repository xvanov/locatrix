"""
Unit tests for feedback model.

These tests verify feedback model validation and serialization.
All tests are written in RED phase - they will fail until implementation is complete.
"""
import pytest
from datetime import datetime, timezone

from src.models.feedback import Feedback, FeedbackType


class TestFeedback:
    """Test Feedback model."""
    
    def test_feedback_creation(self):
        """
        GIVEN: Valid feedback data
        WHEN: I create a Feedback instance
        THEN: Feedback object is created with correct attributes
        """
        # GIVEN: Valid feedback data
        feedback = Feedback(
            feedback_id='fb_20240115_xyz789',
            job_id='job_20240115_abc123',
            feedback=FeedbackType.WRONG,
            room_id='room_001',
            correction={
                'bounding_box': [60, 60, 210, 310]
            }
        )
        
        # THEN: Feedback object created correctly
        assert feedback.feedback_id == 'fb_20240115_xyz789'
        assert feedback.job_id == 'job_20240115_abc123'
        assert feedback.feedback == FeedbackType.WRONG
        assert feedback.room_id == 'room_001'
        assert feedback.correction == {'bounding_box': [60, 60, 210, 310]}
    
    def test_feedback_id_generation(self):
        """
        GIVEN: No feedback_id provided
        WHEN: I create a Feedback instance
        THEN: Feedback_id is auto-generated in format fb_{timestamp}_{random}
        """
        # GIVEN: No feedback_id
        feedback = Feedback(
            job_id='job_20240115_abc123',
            feedback=FeedbackType.CORRECT
        )
        
        # THEN: Feedback_id auto-generated
        assert feedback.feedback_id.startswith('fb_')
        assert len(feedback.feedback_id) > 10
    
    def test_feedback_to_dict(self):
        """
        GIVEN: A Feedback instance
        WHEN: I convert to dictionary
        THEN: Dictionary contains all feedback fields
        """
        # GIVEN: Feedback instance
        feedback = Feedback(
            feedback_id='fb_20240115_xyz789',
            job_id='job_20240115_abc123',
            feedback=FeedbackType.WRONG,
            room_id='room_001',
            correction={
                'bounding_box': [60, 60, 210, 310]
            }
        )
        
        # WHEN: Convert to dictionary
        feedback_dict = feedback.to_dict()
        
        # THEN: Dictionary contains all fields
        assert feedback_dict['feedback_id'] == 'fb_20240115_xyz789'
        assert feedback_dict['job_id'] == 'job_20240115_abc123'
        assert feedback_dict['feedback'] == 'wrong'
        assert feedback_dict['room_id'] == 'room_001'
        assert feedback_dict['correction'] == {'bounding_box': [60, 60, 210, 310]}
    
    def test_feedback_from_dict(self):
        """
        GIVEN: A dictionary with feedback data
        WHEN: I create Feedback from dictionary
        THEN: Feedback object is created correctly
        """
        # GIVEN: Dictionary with feedback data
        feedback_dict = {
            'feedback_id': 'fb_20240115_xyz789',
            'job_id': 'job_20240115_abc123',
            'feedback': 'wrong',
            'room_id': 'room_001',
            'correction': {
                'bounding_box': [60, 60, 210, 310]
            },
            'created_at': '2024-01-15T10:30:00Z'
        }
        
        # WHEN: Create from dictionary
        feedback = Feedback.from_dict(feedback_dict)
        
        # THEN: Feedback object created correctly
        assert feedback.feedback_id == 'fb_20240115_xyz789'
        assert feedback.job_id == 'job_20240115_abc123'
        assert feedback.feedback == FeedbackType.WRONG
        assert feedback.room_id == 'room_001'
    
    def test_feedback_to_dynamodb_item(self):
        """
        GIVEN: A Feedback instance
        WHEN: I convert to DynamoDB item
        THEN: DynamoDB item format is correct
        """
        # GIVEN: Feedback instance
        feedback = Feedback(
            feedback_id='fb_20240115_xyz789',
            job_id='job_20240115_abc123',
            feedback=FeedbackType.WRONG,
            created_at='2024-01-15T10:30:00Z'
        )
        
        # WHEN: Convert to DynamoDB item
        item = feedback.to_dynamodb_item()
        
        # THEN: DynamoDB item format correct
        assert item['feedback_id'] == 'fb_20240115_xyz789'
        assert item['job_id'] == 'job_20240115_abc123'
        assert item['feedback'] == 'wrong'
    
    def test_feedback_from_dynamodb_item(self):
        """
        GIVEN: A DynamoDB item
        WHEN: I create Feedback from DynamoDB item
        THEN: Feedback object is created correctly
        """
        # GIVEN: DynamoDB item
        item = {
            'feedback_id': 'fb_20240115_xyz789',
            'job_id': 'job_20240115_abc123',
            'feedback': 'wrong',
            'room_id': 'room_001',
            'correction': {
                'bounding_box': [60, 60, 210, 310]
            },
            'created_at': '2024-01-15T10:30:00Z'
        }
        
        # WHEN: Create from DynamoDB item
        feedback = Feedback.from_dynamodb_item(item)
        
        # THEN: Feedback object created correctly
        assert feedback.feedback_id == 'fb_20240115_xyz789'
        assert feedback.job_id == 'job_20240115_abc123'
        assert feedback.feedback == FeedbackType.WRONG
    
    def test_feedback_validate_valid(self):
        """
        GIVEN: Valid feedback data
        WHEN: I validate feedback
        THEN: Validation passes
        """
        # GIVEN: Valid feedback
        feedback = Feedback(
            feedback_id='fb_20240115_xyz789',
            job_id='job_20240115_abc123',
            feedback=FeedbackType.CORRECT
        )
        
        # WHEN: Validate
        # THEN: Validation passes
        assert feedback.validate() is True
    
    def test_feedback_validate_invalid_feedback_id(self):
        """
        GIVEN: Invalid feedback_id format
        WHEN: I validate feedback
        THEN: ValueError is raised
        """
        # GIVEN: Invalid feedback_id
        feedback = Feedback(
            feedback_id='invalid',
            job_id='job_20240115_abc123',
            feedback=FeedbackType.CORRECT
        )
        
        # WHEN: Validate
        # THEN: ValueError raised
        with pytest.raises(ValueError, match="must start with 'fb_'"):
            feedback.validate()
    
    def test_feedback_validate_invalid_feedback_type(self):
        """
        GIVEN: Invalid feedback type
        WHEN: I create Feedback from dictionary
        THEN: ValueError is raised
        """
        # GIVEN: Invalid feedback type
        feedback_dict = {
            'feedback_id': 'fb_20240115_xyz789',
            'job_id': 'job_20240115_abc123',
            'feedback': 'invalid_type'
        }
        
        # WHEN: Create from dictionary
        # THEN: ValueError raised
        with pytest.raises(ValueError):
            Feedback.from_dict(feedback_dict)
    
    def test_feedback_correct_type_no_correction(self):
        """
        GIVEN: Feedback type 'correct'
        WHEN: I create Feedback
        THEN: Correction can be None
        """
        # GIVEN: Correct feedback without correction
        feedback = Feedback(
            feedback_id='fb_20240115_xyz789',
            job_id='job_20240115_abc123',
            feedback=FeedbackType.CORRECT,
            correction=None
        )
        
        # THEN: Feedback created successfully
        assert feedback.feedback == FeedbackType.CORRECT
        assert feedback.correction is None
    
    def test_feedback_wrong_type_requires_correction(self):
        """
        GIVEN: Feedback type 'wrong'
        WHEN: I validate feedback without correction
        THEN: ValueError is raised
        """
        # GIVEN: Wrong feedback without correction
        feedback = Feedback(
            feedback_id='fb_20240115_xyz789',
            job_id='job_20240115_abc123',
            feedback=FeedbackType.WRONG,
            room_id='room_001',
            correction=None
        )
        
        # WHEN: Validate
        # THEN: ValueError raised
        with pytest.raises(ValueError, match="correction"):
            feedback.validate()


