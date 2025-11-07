"""
Job service for managing location detection jobs.

This module provides business logic for job creation, retrieval, and cancellation
with DynamoDB and S3 integration.
"""
import os
import hashlib
from typing import Optional, BinaryIO
import boto3
from botocore.exceptions import ClientError

# Handle imports for both Lambda (src/ directory) and local testing (project root)
try:
    from models.job import Job, JobStatus
    from utils.errors import JobNotFoundError, JobAlreadyCompletedError
    from utils.retry import retry_aws_call
    from utils.logging import get_logger
except ImportError:
    # Fallback for local testing from project root
    from src.models.job import Job, JobStatus
    from src.utils.errors import JobNotFoundError, JobAlreadyCompletedError
    from src.utils.retry import retry_aws_call
    from src.utils.logging import get_logger


logger = get_logger(__name__)


class JobService:
    """
    Service for managing job lifecycle.
    
    Handles job creation, retrieval, cancellation, and status tracking
    using DynamoDB and S3.
    """
    
    def __init__(
        self,
        jobs_table_name: Optional[str] = None,
        blueprints_bucket_name: Optional[str] = None
    ):
        """
        Initialize JobService.
        
        Args:
            jobs_table_name: DynamoDB table name for jobs (default: from env var)
            blueprints_bucket_name: S3 bucket name for blueprints (default: from env var)
        """
        self.jobs_table_name = jobs_table_name or os.environ.get('JOBS_TABLE_NAME')
        self.blueprints_bucket_name = blueprints_bucket_name or os.environ.get('BLUEPRINTS_BUCKET_NAME')
        
        if not self.jobs_table_name:
            raise ValueError("JOBS_TABLE_NAME environment variable is required")
        if not self.blueprints_bucket_name:
            raise ValueError("BLUEPRINTS_BUCKET_NAME environment variable is required")
        
        self.dynamodb = boto3.resource('dynamodb')
        self.s3 = boto3.client('s3')
        self.jobs_table = self.dynamodb.Table(self.jobs_table_name)
    
    def create_job(
        self,
        blueprint_file: BinaryIO,
        blueprint_format: str,
        filename: Optional[str] = None
    ) -> Job:
        """
        Create a new job with blueprint file upload.
        
        Args:
            blueprint_file: File-like object containing blueprint data
            blueprint_format: Format of blueprint file (png, jpg, pdf)
            filename: Original filename (default: None)
            
        Returns:
            Created Job instance
            
        Raises:
            ValueError: If blueprint_format is invalid
            ClientError: If AWS service call fails
        """
        # Validate format
        blueprint_format = blueprint_format.lower()
        if blueprint_format not in ['png', 'jpg', 'pdf']:
            raise ValueError(f"Invalid blueprint format: {blueprint_format}. Must be png, jpg, or pdf")
        
        # Read file content
        blueprint_file.seek(0)
        file_content = blueprint_file.read()
        blueprint_file.seek(0)
        
        # Calculate blueprint hash (MD5)
        blueprint_hash = hashlib.md5(file_content).hexdigest()
        
        # Create job
        job = Job(
            status=JobStatus.PENDING,
            blueprint_format=blueprint_format,
            blueprint_hash=blueprint_hash
        )
        
        # Generate S3 key: blueprints/{job_id}/{filename}
        if filename is None:
            filename = f"blueprint.{blueprint_format}"
        s3_key = f"blueprints/{job.job_id}/{filename}"
        job.blueprint_s3_key = s3_key
        
        # Upload to S3 first (before creating DynamoDB record)
        # This ensures we don't create orphaned DynamoDB records if S3 upload fails
        logger.info(
            f"Uploading blueprint to S3: {s3_key}",
            context={'job_id': job.job_id, 'bucket': self.blueprints_bucket_name}
        )
        
        def upload_file():
            self.s3.put_object(
                Bucket=self.blueprints_bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType=self._get_content_type(blueprint_format)
            )
        
        try:
            retry_aws_call(upload_file)
        except Exception as e:
            # S3 upload failed - don't create DynamoDB record
            logger.error(
                f"S3 upload failed for job {job.job_id}, aborting job creation",
                exc_info=True,
                context={'job_id': job.job_id, 's3_key': s3_key}
            )
            raise
        
        # Save job to DynamoDB (only if S3 upload succeeded)
        logger.info(
            f"Creating job in DynamoDB: {job.job_id}",
            context={'job_id': job.job_id, 'table': self.jobs_table_name}
        )
        
        def put_job():
            self.jobs_table.put_item(Item=job.to_dynamodb_item())
        
        try:
            retry_aws_call(put_job)
        except Exception as e:
            # DynamoDB creation failed after S3 upload succeeded
            # Clean up S3 object to prevent orphaned files
            logger.error(
                f"DynamoDB creation failed for job {job.job_id}, cleaning up S3 object",
                exc_info=True,
                context={'job_id': job.job_id, 's3_key': s3_key}
            )
            try:
                self.s3.delete_object(Bucket=self.blueprints_bucket_name, Key=s3_key)
                logger.info(
                    f"Cleaned up S3 object after DynamoDB failure: {s3_key}",
                    context={'job_id': job.job_id, 's3_key': s3_key}
                )
            except Exception as cleanup_error:
                # Log cleanup failure but don't mask original error
                logger.error(
                    f"Failed to clean up S3 object after DynamoDB failure: {s3_key}",
                    exc_info=True,
                    context={'job_id': job.job_id, 's3_key': s3_key, 'cleanup_error': str(cleanup_error)}
                )
            raise
        
        logger.info(
            f"Job created successfully: {job.job_id}",
            context={'job_id': job.job_id}
        )
        
        return job
    
    def get_job(self, job_id: str) -> Job:
        """
        Retrieve a job by job_id.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job instance
            
        Raises:
            JobNotFoundError: If job not found
            ClientError: If AWS service call fails
        """
        logger.info(
            f"Retrieving job: {job_id}",
            context={'job_id': job_id, 'table': self.jobs_table_name}
        )
        
        def get_item():
            response = self.jobs_table.get_item(Key={'job_id': job_id})
            return response.get('Item')
        
        item = retry_aws_call(get_item)
        
        if not item:
            raise JobNotFoundError(job_id)
        
        job = Job.from_dynamodb_item(item)
        logger.info(
            f"Job retrieved: {job_id}",
            context={'job_id': job_id, 'status': job.status.value}
        )
        
        return job
    
    def cancel_job(self, job_id: str) -> Job:
        """
        Cancel a job by job_id.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Updated Job instance
            
        Raises:
            JobNotFoundError: If job not found
            JobAlreadyCompletedError: If job cannot be cancelled
            ClientError: If AWS service call fails
        """
        # Get job first
        job = self.get_job(job_id)
        
        # Explicit check for already-cancelled jobs
        if job.status == JobStatus.CANCELLED:
            raise JobAlreadyCompletedError(job_id, job.status.value)
        
        # Check if job can be cancelled
        if not job.can_be_cancelled():
            raise JobAlreadyCompletedError(job_id, job.status.value)
        
        # Update status to cancelled
        job.update_status(JobStatus.CANCELLED)
        
        logger.info(
            f"Cancelling job: {job_id}",
            context={'job_id': job_id}
        )
        
        # Update DynamoDB
        def update_item():
            self.jobs_table.update_item(
                Key={'job_id': job_id},
                UpdateExpression='SET #status = :status, updated_at = :updated_at',
                ExpressionAttributeNames={
                    '#status': 'status'
                },
                ExpressionAttributeValues={
                    ':status': JobStatus.CANCELLED.value,
                    ':updated_at': job.updated_at
                }
            )
        
        retry_aws_call(update_item)
        
        logger.info(
            f"Job cancelled: {job_id}",
            context={'job_id': job_id}
        )
        
        return job
    
    @staticmethod
    def _get_content_type(format: str) -> str:
        """
        Get MIME content type for blueprint format.
        
        Args:
            format: Blueprint format (png, jpg, pdf)
            
        Returns:
            MIME content type string
        """
        content_types = {
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'pdf': 'application/pdf'
        }
        return content_types.get(format.lower(), 'application/octet-stream')

