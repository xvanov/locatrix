"""
Job data models for Location Detection AI service.

This module defines the Job model with status enum and validation logic.
"""
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import uuid

# TTL configuration
JOB_TTL_DAYS = 7


class JobStatus(str, Enum):
    """Job status enumeration."""
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class Job:
    """
    Job model representing a location detection job.
    
    Attributes:
        job_id: Unique job identifier (format: job_{timestamp}_{random})
        status: Current job status
        created_at: ISO 8601 timestamp when job was created
        updated_at: ISO 8601 timestamp when job was last updated
        blueprint_s3_key: S3 key for uploaded blueprint file
        blueprint_format: Format of blueprint file (png, jpg, pdf)
        blueprint_hash: Hash of blueprint file (MD5 or SHA256)
        result_s3_key: S3 key for processing results (None if not completed)
        error: Error details if job failed (None if successful)
    """
    
    def __init__(
        self,
        job_id: Optional[str] = None,
        status: JobStatus = JobStatus.PENDING,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        blueprint_s3_key: Optional[str] = None,
        blueprint_format: Optional[str] = None,
        blueprint_hash: Optional[str] = None,
        result_s3_key: Optional[str] = None,
        error: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        api_version: Optional[str] = None
    ):
        """
        Initialize Job instance.
        
        Args:
            job_id: Unique job identifier (auto-generated if None)
            status: Current job status (default: PENDING)
            created_at: ISO 8601 timestamp (auto-generated if None)
            updated_at: ISO 8601 timestamp (auto-generated if None)
            blueprint_s3_key: S3 key for blueprint file
            blueprint_format: Format of blueprint file
            blueprint_hash: Hash of blueprint file
            result_s3_key: S3 key for results
            error: Error details if failed
            request_id: Request ID for correlation
            correlation_id: Correlation ID for distributed tracing
            api_version: API version used to create the job
        """
        if job_id is None:
            job_id = self._generate_job_id()
        
        self.job_id = job_id
        self.status = status if isinstance(status, JobStatus) else JobStatus(status)
        
        now = datetime.now(timezone.utc).isoformat()
        self.created_at = created_at or now
        self.updated_at = updated_at or now
        
        self.blueprint_s3_key = blueprint_s3_key
        self.blueprint_format = blueprint_format
        self.blueprint_hash = blueprint_hash
        self.result_s3_key = result_s3_key
        self.error = error
        self.request_id = request_id
        self.correlation_id = correlation_id
        self.api_version = api_version
    
    @staticmethod
    def _generate_job_id() -> str:
        """
        Generate a unique job ID in format: job_{timestamp}_{random}.
        
        Returns:
            Job ID string
        """
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        random_part = uuid.uuid4().hex[:8]
        return f"job_{timestamp}_{random_part}"
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Job to dictionary.
        
        Returns:
            Dictionary representation of Job
        """
        result = {
            'job_id': self.job_id,
            'status': self.status.value,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'blueprint_s3_key': self.blueprint_s3_key,
            'blueprint_format': self.blueprint_format,
            'blueprint_hash': self.blueprint_hash,
            'result_s3_key': self.result_s3_key,
            'error': self.error
        }
        
        # Add optional fields if present
        if self.request_id:
            result['request_id'] = self.request_id
        if self.correlation_id:
            result['correlation_id'] = self.correlation_id
        if self.api_version:
            result['api_version'] = self.api_version
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Job':
        """
        Create Job from dictionary.
        
        Args:
            data: Dictionary with job data
            
        Returns:
            Job instance
        """
        return cls(
            job_id=data.get('job_id'),
            status=data.get('status', JobStatus.PENDING),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
            blueprint_s3_key=data.get('blueprint_s3_key'),
            blueprint_format=data.get('blueprint_format'),
            blueprint_hash=data.get('blueprint_hash'),
            result_s3_key=data.get('result_s3_key'),
            error=data.get('error'),
            request_id=data.get('request_id'),
            correlation_id=data.get('correlation_id'),
            api_version=data.get('api_version')
        )
    
    def to_dynamodb_item(self) -> Dict[str, Any]:
        """
        Convert Job to DynamoDB item format.
        
        Includes TTL attribute (expires_at) for automatic cleanup.
        
        Returns:
            Dictionary in DynamoDB item format
        """
        item = self.to_dict()
        
        # Add TTL attribute (7 days from creation)
        if self.created_at:
            created_dt = datetime.fromisoformat(self.created_at.replace('Z', '+00:00'))
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            expires_dt = created_dt + timedelta(days=JOB_TTL_DAYS)
            item['expires_at'] = int(expires_dt.timestamp())
        
        return item
    
    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> 'Job':
        """
        Create Job from DynamoDB item.
        
        Args:
            item: DynamoDB item dictionary
            
        Returns:
            Job instance
        """
        # Remove TTL attribute if present
        data = {k: v for k, v in item.items() if k != 'expires_at'}
        return cls.from_dict(data)
    
    def update_status(self, new_status: JobStatus, error: Optional[Dict[str, Any]] = None):
        """
        Update job status and timestamp.
        
        Args:
            new_status: New job status
            error: Error details if status is FAILED (default: None)
        """
        self.status = new_status if isinstance(new_status, JobStatus) else JobStatus(new_status)
        self.updated_at = datetime.now(timezone.utc).isoformat()
        
        if error:
            self.error = error
    
    def can_be_cancelled(self) -> bool:
        """
        Check if job can be cancelled.
        
        Returns:
            True if job can be cancelled, False otherwise
        """
        return self.status in [JobStatus.PENDING, JobStatus.PROCESSING]
    
    def validate(self) -> bool:
        """
        Validate job data.
        
        Returns:
            True if job is valid, False otherwise
            
        Raises:
            ValueError: If validation fails
        """
        if not self.job_id:
            raise ValueError("job_id is required")
        
        if not self.job_id.startswith('job_'):
            raise ValueError("job_id must start with 'job_'")
        
        if self.blueprint_format and self.blueprint_format.lower() not in ['png', 'jpg', 'pdf']:
            raise ValueError("blueprint_format must be one of: png, jpg, pdf")
        
        if self.status == JobStatus.FAILED and not self.error:
            raise ValueError("error is required when status is FAILED")
        
        return True

