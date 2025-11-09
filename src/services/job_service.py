"""
Job service for managing location detection jobs.

This module provides business logic for job creation, retrieval, and cancellation
with DynamoDB and S3 integration, including thread-safe operations and enhanced error handling.
"""
import os
import json
import time
import hashlib
from typing import Optional, BinaryIO
import boto3
from botocore.exceptions import ClientError

# Handle imports for both Lambda (src/ directory) and local testing (project root)
try:
    from models.job import Job, JobStatus
    from utils.errors import JobNotFoundError, JobAlreadyCompletedError, ServiceUnavailableError, LocationDetectionError
    from utils.retry import retry_aws_call
    from utils.logging import get_logger
except ImportError:
    # Fallback for local testing from project root
    from src.models.job import Job, JobStatus
    from src.utils.errors import JobNotFoundError, JobAlreadyCompletedError, ServiceUnavailableError, LocationDetectionError
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
        
        # Support LocalStack endpoint URL
        endpoint_url = os.environ.get('AWS_ENDPOINT_URL')
        dynamodb_kwargs = {}
        s3_kwargs = {}
        if endpoint_url:
            dynamodb_kwargs['endpoint_url'] = endpoint_url
            s3_kwargs['endpoint_url'] = endpoint_url
        
        self.dynamodb = boto3.resource('dynamodb', **dynamodb_kwargs)
        self.s3 = boto3.client('s3', **s3_kwargs)
        self.jobs_table = self.dynamodb.Table(self.jobs_table_name)
    
    def create_job(
        self,
        blueprint_file: BinaryIO,
        blueprint_format: str,
        filename: Optional[str] = None,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        api_version: Optional[str] = None
    ) -> Job:
        """
        Create a new job with blueprint file upload.
        
        Args:
            blueprint_file: File-like object containing blueprint data
            blueprint_format: Format of blueprint file (png, jpg, pdf)
            filename: Original filename (default: None)
            request_id: Request ID for correlation (default: None)
            correlation_id: Correlation ID for distributed tracing (default: None)
            api_version: API version used to create the job (default: None)
            
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
        
        # Create job with new fields
        job = Job(
            status=JobStatus.PENDING,
            blueprint_format=blueprint_format,
            blueprint_hash=blueprint_hash,
            request_id=request_id,
            correlation_id=correlation_id,
            api_version=api_version
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
            try:
                self.s3.put_object(
                    Bucket=self.blueprints_bucket_name,
                    Key=s3_key,
                    Body=file_content,
                    ContentType=self._get_content_type(blueprint_format)
                )
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                # Handle service unavailability
                if error_code in ['ServiceUnavailable', 'SlowDown']:
                    raise ServiceUnavailableError('S3', retry_after=5)
                # Re-raise other errors
                raise
        
        try:
            retry_aws_call(upload_file)
        except ServiceUnavailableError as e:
            # S3 service unavailable - don't create DynamoDB record
            logger.error(
                f"S3 service unavailable for job {job.job_id}, aborting job creation",
                exc_info=True,
                context={'job_id': job.job_id, 's3_key': s3_key, 'service': 'S3'}
            )
            raise
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
            try:
                self.jobs_table.put_item(Item=job.to_dynamodb_item())
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                # Handle throttling and service unavailability
                if error_code in ['ProvisionedThroughputExceededException', 'ThrottlingException']:
                    # Retry logic will handle this, but we can add specific handling if needed
                    raise
                elif error_code in ['ServiceUnavailable', 'ResourceNotFoundException']:
                    raise ServiceUnavailableError('DynamoDB', retry_after=5)
                # Re-raise other errors
                raise
        
        try:
            retry_aws_call(put_job)
        except ServiceUnavailableError as e:
            # DynamoDB service unavailable after S3 upload succeeded
            # Clean up S3 object to prevent orphaned files
            logger.error(
                f"DynamoDB service unavailable for job {job.job_id}, cleaning up S3 object",
                exc_info=True,
                context={'job_id': job.job_id, 's3_key': s3_key, 'service': 'DynamoDB'}
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
        Cancel a job by job_id with optimistic locking for concurrent requests.
        
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
        
        # Store original status and updated_at for optimistic locking
        original_status = job.status.value
        original_updated_at = job.updated_at
        
        # Update status to cancelled
        job.update_status(JobStatus.CANCELLED)
        
        logger.info(
            f"Cancelling job: {job_id}",
            context={'job_id': job_id}
        )
        
        # Update DynamoDB with optimistic locking (conditional update)
        # This prevents concurrent updates from overwriting each other
        def update_item():
            try:
                self.jobs_table.update_item(
                    Key={'job_id': job_id},
                    UpdateExpression='SET #status = :status, updated_at = :updated_at',
                    ConditionExpression='#status = :original_status AND updated_at = :original_updated_at',
                    ExpressionAttributeNames={
                        '#status': 'status'
                    },
                    ExpressionAttributeValues={
                        ':status': JobStatus.CANCELLED.value,
                        ':updated_at': job.updated_at,
                        ':original_status': original_status,
                        ':original_updated_at': original_updated_at
                    }
                )
            except ClientError as e:
                # Check if it's a conditional check failure (concurrent update)
                if e.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
                    # Re-fetch the job to get current state
                    updated_job = self.get_job(job_id)
                    # Check if it was already cancelled by another request
                    if updated_job.status == JobStatus.CANCELLED:
                        logger.info(
                            f"Job {job_id} was already cancelled by another request",
                            context={'job_id': job_id}
                        )
                        return updated_job
                    # Otherwise, status changed - raise error
                    raise JobAlreadyCompletedError(job_id, updated_job.status.value)
                # Re-raise other errors
                raise
        
        try:
            result = retry_aws_call(update_item)
            # If result is a Job instance (from concurrent cancellation), return it
            if isinstance(result, Job):
                return result
        except JobAlreadyCompletedError:
            # Re-fetch to get current state
            updated_job = self.get_job(job_id)
            raise JobAlreadyCompletedError(job_id, updated_job.status.value)
        
        logger.info(
            f"Job cancelled: {job_id}",
            context={'job_id': job_id}
        )
        
        return job
    
    def start_pipeline_execution(
        self,
        job_id: str,
        state_machine_arn: Optional[str] = None
    ) -> str:
        """
        Start Step Functions state machine execution for job processing pipeline.
        
        Args:
            job_id: Job identifier
            state_machine_arn: Step Functions state machine ARN (default: from env var)
            
        Returns:
            Step Functions execution ARN
            
        Raises:
            JobNotFoundError: If job not found
            LocationDetectionError: If Step Functions execution fails
        """
        # Get job to verify it exists
        job = self.get_job(job_id)
        
        # Get state machine ARN from environment or parameter
        if not state_machine_arn:
            state_machine_arn = os.environ.get('STEP_FUNCTIONS_STATE_MACHINE_ARN')
        
        if not state_machine_arn:
            raise LocationDetectionError(
                code='CONFIGURATION_ERROR',
                message='STEP_FUNCTIONS_STATE_MACHINE_ARN environment variable is required',
                details={},
                status_code=500
            )
        
        logger.info(
            f"Starting Step Functions execution for job: {job_id}",
            context={
                'job_id': job_id,
                'state_machine_arn': state_machine_arn
            }
        )
        
        # Create Step Functions client
        endpoint_url = os.environ.get('AWS_ENDPOINT_URL')
        stepfunctions_kwargs = {}
        if endpoint_url:
            stepfunctions_kwargs['endpoint_url'] = endpoint_url
        stepfunctions_client = boto3.client('stepfunctions', **stepfunctions_kwargs)
        
        # Prepare execution input
        execution_input = {
            'job_id': job_id
        }
        
        # Generate unique execution name
        execution_name = f"job-{job_id}-{int(time.time())}"
        
        def start_execution():
            try:
                response = stepfunctions_client.start_execution(
                    stateMachineArn=state_machine_arn,
                    name=execution_name,
                    input=json.dumps(execution_input)
                )
                return response
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code in ['ExecutionAlreadyExists', 'StateMachineDoesNotExist']:
                    raise LocationDetectionError(
                        code='STEP_FUNCTIONS_EXECUTION_FAILED',
                        message=f"Failed to start Step Functions execution: {e.response.get('Error', {}).get('Message', str(e))}",
                        details={
                            'job_id': job_id,
                            'state_machine_arn': state_machine_arn,
                            'error_code': error_code
                        },
                        status_code=500
                    )
                elif error_code in ['ServiceUnavailable', 'Throttling', 'ThrottlingException']:
                    raise ServiceUnavailableError('StepFunctions', retry_after=5)
                raise
        
        try:
            response = retry_aws_call(start_execution)
            execution_arn = response.get('executionArn', '')
            
            logger.info(
                f"Step Functions execution started for job: {job_id}",
                context={
                    'job_id': job_id,
                    'execution_arn': execution_arn,
                    'execution_name': execution_name
                }
            )
            
            # Update job with execution ARN (optional)
            try:
                self.jobs_table.update_item(
                    Key={'job_id': job_id},
                    UpdateExpression='SET step_functions_execution_arn = :execution_arn',
                    ExpressionAttributeValues={
                        ':execution_arn': execution_arn
                    }
                )
            except Exception as e:
                logger.warning(
                    f"Failed to update job with execution ARN: {str(e)}",
                    context={'job_id': job_id, 'execution_arn': execution_arn}
                )
                # Don't fail if we can't update the job record
            
            return execution_arn
            
        except ServiceUnavailableError:
            logger.error(
                f"Step Functions service unavailable for job: {job_id}",
                exc_info=True,
                context={'job_id': job_id, 'service': 'StepFunctions'}
            )
            raise
        except LocationDetectionError:
            # Re-raise LocationDetectionError as-is
            raise
        except Exception as e:
            logger.error(
                f"Failed to start Step Functions execution for job: {job_id}",
                exc_info=True,
                context={'job_id': job_id}
            )
            raise LocationDetectionError(
                code='STEP_FUNCTIONS_EXECUTION_FAILED',
                message=f"Failed to start Step Functions execution: {str(e)}",
                details={'job_id': job_id, 'state_machine_arn': state_machine_arn},
                status_code=500
            )
    
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

