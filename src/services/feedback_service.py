"""
Feedback service for managing user feedback on job results.

This module provides business logic for feedback submission and retrieval
with DynamoDB integration.
"""
import os
from typing import List, Dict, Any
import boto3
from botocore.exceptions import ClientError

# Handle imports for both Lambda (src/ directory) and local testing (project root)
try:
    from models.feedback import Feedback, FeedbackType
    from utils.errors import InvalidFeedbackError, ServiceUnavailableError
    from utils.retry import retry_aws_call
    from utils.logging import get_logger
except ImportError:
    # Fallback for local testing from project root
    from src.models.feedback import Feedback, FeedbackType
    from src.utils.errors import InvalidFeedbackError, ServiceUnavailableError
    from src.utils.retry import retry_aws_call
    from src.utils.logging import get_logger


logger = get_logger(__name__)


class FeedbackService:
    """
    Service for managing feedback lifecycle.
    
    Handles feedback submission and retrieval using DynamoDB.
    """
    
    def __init__(
        self,
        feedback_table_name: str = None
    ):
        """
        Initialize FeedbackService.
        
        Args:
            feedback_table_name: DynamoDB table name for feedback (default: from env var)
        """
        self.feedback_table_name = feedback_table_name or os.environ.get('FEEDBACK_TABLE_NAME')
        
        if not self.feedback_table_name:
            raise ValueError("FEEDBACK_TABLE_NAME environment variable is required")
        
        self.dynamodb = boto3.resource('dynamodb')
        self.feedback_table = self.dynamodb.Table(self.feedback_table_name)
    
    def submit_feedback(self, job_id: str, feedback_data: Dict[str, Any]) -> Feedback:
        """
        Submit feedback for a job.
        
        Args:
            job_id: Job identifier
            feedback_data: Dictionary with feedback data (feedback, room_id, correction)
            
        Returns:
            Created Feedback instance
            
        Raises:
            InvalidFeedbackError: If feedback data is invalid
            ClientError: If AWS service call fails
        """
        # Validate feedback type
        feedback_type_str = feedback_data.get('feedback')
        if feedback_type_str not in ['wrong', 'correct', 'partial']:
            raise InvalidFeedbackError(
                f"Feedback type must be one of: wrong, correct, partial",
                details={'received_type': feedback_type_str}
            )
        
        feedback_type = FeedbackType(feedback_type_str)
        
        # Validate wrong feedback has correction
        if feedback_type == FeedbackType.WRONG:
            correction = feedback_data.get('correction')
            if not correction:
                raise InvalidFeedbackError(
                    "Correction is required when feedback type is 'wrong'"
                )
            
            # Validate bounding box format
            bounding_box = correction.get('bounding_box')
            if not isinstance(bounding_box, list) or len(bounding_box) != 4:
                raise InvalidFeedbackError(
                    "Correction bounding_box must be an array of 4 numbers"
                )
            
            # Validate all elements are numbers
            if not all(isinstance(x, (int, float)) for x in bounding_box):
                raise InvalidFeedbackError(
                    "Correction bounding_box must contain only numbers"
                )
        
        # Create feedback instance
        feedback = Feedback(
            job_id=job_id,
            feedback=feedback_type,
            room_id=feedback_data.get('room_id'),
            correction=feedback_data.get('correction')
        )
        
        # Validate feedback
        feedback.validate()
        
        logger.info(
            f"Submitting feedback: {feedback.feedback_id}",
            context={'feedback_id': feedback.feedback_id, 'job_id': job_id, 'table': self.feedback_table_name}
        )
        
        # Save to DynamoDB
        def put_feedback():
            try:
                self.feedback_table.put_item(Item=feedback.to_dynamodb_item())
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code in ['ServiceUnavailable', 'ResourceNotFoundException']:
                    raise ServiceUnavailableError('DynamoDB', retry_after=5)
                raise
        
        try:
            retry_aws_call(put_feedback)
        except ServiceUnavailableError as e:
            logger.error(
                f"DynamoDB service unavailable for feedback {feedback.feedback_id}",
                exc_info=True,
                context={'feedback_id': feedback.feedback_id, 'service': 'DynamoDB'}
            )
            raise
        
        logger.info(
            f"Feedback submitted successfully: {feedback.feedback_id}",
            context={'feedback_id': feedback.feedback_id, 'job_id': job_id}
        )
        
        return feedback
    
    def get_feedback_by_job_id(self, job_id: str) -> List[Feedback]:
        """
        Retrieve all feedback for a job by job_id.
        
        Args:
            job_id: Job identifier
            
        Returns:
            List of Feedback instances (empty list if none found)
            
        Raises:
            ClientError: If AWS service call fails
        """
        logger.info(
            f"Retrieving feedback for job: {job_id}",
            context={'job_id': job_id, 'table': self.feedback_table_name}
        )
        
        def query_feedback():
            response = self.feedback_table.query(
                IndexName='job_id-index',
                KeyConditionExpression='job_id = :job_id',
                ExpressionAttributeValues={
                    ':job_id': job_id
                }
            )
            return response.get('Items', [])
        
        items = retry_aws_call(query_feedback)
        
        feedback_list = [Feedback.from_dynamodb_item(item) for item in items]
        
        logger.info(
            f"Retrieved {len(feedback_list)} feedback items for job: {job_id}",
            context={'job_id': job_id, 'count': len(feedback_list)}
        )
        
        return feedback_list

