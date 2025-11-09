"""
Unit tests for JobService Step Functions integration.
"""
import pytest
import json
import os
import time
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

from src.services.job_service import JobService
from src.utils.errors import JobNotFoundError, LocationDetectionError, ServiceUnavailableError


@pytest.fixture
def mock_aws_services():
    """Mock AWS services for testing."""
    with patch('boto3.client') as mock_client, \
         patch('boto3.resource') as mock_resource:
        
        # Mock DynamoDB
        mock_dynamodb = MagicMock()
        mock_resource.return_value = mock_dynamodb
        
        # Mock Step Functions
        mock_stepfunctions = MagicMock()
        mock_client.return_value = mock_stepfunctions
        
        yield {
            'dynamodb': mock_dynamodb,
            'stepfunctions': mock_stepfunctions,
            'client': mock_client,
            'resource': mock_resource
        }


@pytest.fixture
def sample_job():
    """Sample job for testing."""
    from src.models.job import Job, JobStatus
    return Job(
        job_id='test-job-123',
        status=JobStatus.PENDING,
        blueprint_format='png',
        blueprint_s3_key='blueprints/test-job-123/blueprint.png'
    )


class TestJobServiceStepFunctions:
    """Test JobService Step Functions integration."""
    
    def test_start_pipeline_execution_success(
        self,
        mock_aws_services,
        sample_job
    ):
        """Test successful Step Functions execution start."""
        os.environ['JOBS_TABLE_NAME'] = 'test-jobs'
        os.environ['BLUEPRINTS_BUCKET_NAME'] = 'test-blueprints'
        os.environ['STEP_FUNCTIONS_STATE_MACHINE_ARN'] = 'arn:aws:states:us-east-1:123456789012:stateMachine:test-state-machine'
        
        mock_resource = mock_aws_services['resource']
        mock_client = mock_aws_services['client']
        mock_stepfunctions = mock_aws_services['stepfunctions']
        mock_client.return_value = mock_stepfunctions
        
        # Mock DynamoDB job retrieval
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            'Item': {
                'job_id': sample_job.job_id,
                'status': sample_job.status.value,
                'blueprint_format': sample_job.blueprint_format,
                'blueprint_s3_key': sample_job.blueprint_s3_key
            }
        }
        mock_table.update_item.return_value = {}
        mock_resource.return_value.Table.return_value = mock_table
        
        # Mock Step Functions start_execution
        execution_arn = 'arn:aws:states:us-east-1:123456789012:execution:test-state-machine:test-execution'
        mock_stepfunctions.start_execution.return_value = {
            'executionArn': execution_arn
        }
        
        # Create job service
        job_service = JobService()
        
        # Start pipeline execution
        result_arn = job_service.start_pipeline_execution(sample_job.job_id)
        
        # Verify execution ARN
        assert result_arn == execution_arn
        
        # Verify Step Functions was called
        mock_stepfunctions.start_execution.assert_called_once()
        call_args = mock_stepfunctions.start_execution.call_args
        assert call_args[1]['stateMachineArn'] == os.environ['STEP_FUNCTIONS_STATE_MACHINE_ARN']
        assert 'job_id' in json.loads(call_args[1]['input'])
        
        # Verify job was updated with execution ARN
        assert mock_table.update_item.called
    
    def test_start_pipeline_execution_missing_arn(self, mock_aws_services, sample_job):
        """Test handling of missing state machine ARN."""
        os.environ['JOBS_TABLE_NAME'] = 'test-jobs'
        os.environ['BLUEPRINTS_BUCKET_NAME'] = 'test-blueprints'
        if 'STEP_FUNCTIONS_STATE_MACHINE_ARN' in os.environ:
            del os.environ['STEP_FUNCTIONS_STATE_MACHINE_ARN']
        
        mock_resource = mock_aws_services['resource']
        
        # Mock DynamoDB job retrieval
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            'Item': {
                'job_id': sample_job.job_id,
                'status': sample_job.status.value
            }
        }
        mock_resource.return_value.Table.return_value = mock_table
        
        # Create job service
        job_service = JobService()
        
        # Should raise LocationDetectionError
        with pytest.raises(LocationDetectionError) as exc_info:
            job_service.start_pipeline_execution(sample_job.job_id)
        
        assert exc_info.value.code == 'CONFIGURATION_ERROR'
    
    def test_start_pipeline_execution_job_not_found(self, mock_aws_services):
        """Test handling of job not found."""
        os.environ['JOBS_TABLE_NAME'] = 'test-jobs'
        os.environ['BLUEPRINTS_BUCKET_NAME'] = 'test-blueprints'
        os.environ['STEP_FUNCTIONS_STATE_MACHINE_ARN'] = 'arn:aws:states:us-east-1:123456789012:stateMachine:test-state-machine'
        
        mock_resource = mock_aws_services['resource']
        
        # Mock DynamoDB job retrieval to return None
        mock_table = MagicMock()
        mock_table.get_item.return_value = {'Item': None}
        mock_resource.return_value.Table.return_value = mock_table
        
        # Create job service
        job_service = JobService()
        
        # Should raise JobNotFoundError
        with pytest.raises(JobNotFoundError):
            job_service.start_pipeline_execution('non-existent-job')
    
    def test_start_pipeline_execution_service_unavailable(self, mock_aws_services, sample_job):
        """Test handling of Step Functions service unavailable."""
        os.environ['JOBS_TABLE_NAME'] = 'test-jobs'
        os.environ['BLUEPRINTS_BUCKET_NAME'] = 'test-blueprints'
        os.environ['STEP_FUNCTIONS_STATE_MACHINE_ARN'] = 'arn:aws:states:us-east-1:123456789012:stateMachine:test-state-machine'
        
        mock_resource = mock_aws_services['resource']
        mock_client = mock_aws_services['client']
        mock_stepfunctions = mock_aws_services['stepfunctions']
        mock_client.return_value = mock_stepfunctions
        
        # Mock DynamoDB job retrieval
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            'Item': {
                'job_id': sample_job.job_id,
                'status': sample_job.status.value
            }
        }
        mock_resource.return_value.Table.return_value = mock_table
        
        # Mock Step Functions to raise service unavailable error
        mock_stepfunctions.start_execution.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable'}},
            'StartExecution'
        )
        
        # Create job service
        job_service = JobService()
        
        # Should raise ServiceUnavailableError (after retries)
        with pytest.raises(ServiceUnavailableError):
            job_service.start_pipeline_execution(sample_job.job_id)

