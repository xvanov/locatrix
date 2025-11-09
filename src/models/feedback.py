"""
Feedback data models for Location Detection AI service.

This module defines the Feedback model with type enum and validation logic.
"""
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import uuid
from decimal import Decimal


class FeedbackType(str, Enum):
    """Feedback type enumeration."""
    WRONG = 'wrong'
    CORRECT = 'correct'
    PARTIAL = 'partial'


def _convert_decimal(obj):
    """Convert Decimal objects to int or float for JSON serialization."""
    if isinstance(obj, Decimal):
        # Convert to int if it's a whole number, otherwise float
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_decimal(item) for item in obj]
    return obj


class Feedback:
    """
    Feedback model representing user feedback on job results.
    
    Attributes:
        feedback_id: Unique feedback identifier (format: fb_{timestamp}_{random})
        job_id: Job identifier this feedback is for
        feedback: Feedback type (wrong, correct, partial)
        room_id: Optional room identifier
        correction: Optional correction data with bounding box
        created_at: ISO 8601 timestamp when feedback was created
    """
    
    def __init__(
        self,
        job_id: str,
        feedback: FeedbackType,
        feedback_id: Optional[str] = None,
        room_id: Optional[str] = None,
        correction: Optional[Dict[str, Any]] = None,
        created_at: Optional[str] = None
    ):
        """
        Initialize Feedback instance.
        
        Args:
            job_id: Job identifier this feedback is for
            feedback: Feedback type (wrong, correct, partial)
            feedback_id: Unique feedback identifier (auto-generated if None)
            room_id: Optional room identifier
            correction: Optional correction data with bounding box
            created_at: ISO 8601 timestamp (auto-generated if None)
        """
        if feedback_id is None:
            feedback_id = self._generate_feedback_id()
        
        self.feedback_id = feedback_id
        self.job_id = job_id
        self.feedback = feedback if isinstance(feedback, FeedbackType) else FeedbackType(feedback)
        self.room_id = room_id
        self.correction = correction
        
        now = datetime.now(timezone.utc).isoformat()
        self.created_at = created_at or now
    
    @staticmethod
    def _generate_feedback_id() -> str:
        """
        Generate a unique feedback ID in format: fb_{timestamp}_{random}.
        
        Returns:
            Feedback ID string
        """
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        random_part = uuid.uuid4().hex[:8]
        return f"fb_{timestamp}_{random_part}"
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Feedback to dictionary.
        
        Returns:
            Dictionary representation of Feedback
        """
        result = {
            'feedback_id': self.feedback_id,
            'job_id': self.job_id,
            'feedback': self.feedback.value,
            'room_id': self.room_id,
            'correction': self.correction,
            'created_at': self.created_at
        }
        # Convert Decimal objects to int/float for JSON serialization
        result = _convert_decimal(result)
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Feedback':
        """
        Create Feedback from dictionary.
        
        Args:
            data: Dictionary with feedback data
            
        Returns:
            Feedback instance
            
        Raises:
            ValueError: If feedback type is invalid
        """
        feedback_type_str = data.get('feedback')
        if feedback_type_str not in ['wrong', 'correct', 'partial']:
            raise ValueError(f"Invalid feedback type: {feedback_type_str}. Must be one of: wrong, correct, partial")
        
        return cls(
            feedback_id=data.get('feedback_id'),
            job_id=data.get('job_id'),
            feedback=FeedbackType(feedback_type_str),
            room_id=data.get('room_id'),
            correction=data.get('correction'),
            created_at=data.get('created_at')
        )
    
    def to_dynamodb_item(self) -> Dict[str, Any]:
        """
        Convert Feedback to DynamoDB item format.
        
        Returns:
            Dictionary in DynamoDB item format
        """
        return self.to_dict()
    
    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> 'Feedback':
        """
        Create Feedback from DynamoDB item.
        
        Args:
            item: DynamoDB item dictionary
            
        Returns:
            Feedback instance
        """
        # Convert DynamoDB format to regular dict format
        # DynamoDB returns items with type annotations (S, N, M, L, etc.)
        # boto3's resource API handles this automatically, but we need to handle Decimal conversion
        converted_item = _convert_decimal(item)
        return cls.from_dict(converted_item)
    
    def validate(self) -> bool:
        """
        Validate feedback data.
        
        Returns:
            True if feedback is valid
            
        Raises:
            ValueError: If validation fails
        """
        if not self.feedback_id:
            raise ValueError("feedback_id is required")
        
        if not self.feedback_id.startswith('fb_'):
            raise ValueError("feedback_id must start with 'fb_'")
        
        if self.feedback not in [FeedbackType.WRONG, FeedbackType.CORRECT, FeedbackType.PARTIAL]:
            raise ValueError("feedback must be one of: wrong, correct, partial")
        
        # Wrong feedback must have correction
        if self.feedback == FeedbackType.WRONG and self.correction is None:
            raise ValueError("correction is required when feedback type is 'wrong'")
        
        return True

