"""
Unit tests for job service.
"""
import pytest
import hashlib
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO
from botocore.exceptions import ClientError

from src.services.job_service import JobService
from src.models.job import Job, JobStatus
from src.utils.errors import JobNotFoundError, JobAlreadyCompletedError


@pytest.fixture
def mock_aws_services():
    """Mock AWS services."""
    with patch('src.services.job_service.boto3') as mock_boto3:
        mock_dynamodb = MagicMock()
        mock_s3 = MagicMock()
        mock_table = MagicMock()
        
        mock_boto3.resource.return_value = mock_dynamodb
        mock_boto3.client.return_value = mock_s3
        mock_dynamodb.Table.return_value = mock_table
        
        yield {
            'dynamodb': mock_dynamodb,
            's3': mock_s3,
            'table': mock_table
        }


@pytest.fixture
def job_service(mock_aws_services):
    """Create JobService instance with mocked AWS services."""
    with patch.dict('os.environ', {
        'JOBS_TABLE_NAME': 'test-jobs',
        'BLUEPRINTS_BUCKET_NAME': 'test-blueprints'
    }):
        return JobService(
            jobs_table_name='test-jobs',
            blueprints_bucket_name='test-blueprints'
        )


class TestCreateJob:
    """Test create_job method."""
    
    def test_create_job_success(self, job_service, mock_aws_services):
        """Test successful job creation."""
        file_content = b'test file content'
        file_obj = BytesIO(file_content)
        blueprint_hash = hashlib.md5(file_content).hexdigest()
        
        job = job_service.create_job(
            blueprint_file=file_obj,
            blueprint_format='pdf',
            filename='test.pdf'
        )
        
        assert job.job_id.startswith('job_')
        assert job.status == JobStatus.PENDING
        assert job.blueprint_format == 'pdf'
        assert job.blueprint_hash == blueprint_hash
        assert 'blueprints/' in job.blueprint_s3_key
        assert job.job_id in job.blueprint_s3_key
        
        # Verify S3 upload was called
        mock_aws_services['s3'].put_object.assert_called_once()
        
        # Verify DynamoDB put_item was called
        mock_aws_services['table'].put_item.assert_called_once()
    
    def test_create_job_invalid_format(self, job_service):
        """Test job creation with invalid format."""
        file_obj = BytesIO(b'test content')
        
        with pytest.raises(ValueError, match="Invalid blueprint format"):
            job_service.create_job(
                blueprint_file=file_obj,
                blueprint_format='gif'
            )


class TestGetJob:
    """Test get_job method."""
    
    def test_get_job_success(self, job_service, mock_aws_services):
        """Test successful job retrieval."""
        mock_item = {
            'job_id': 'job_123',
            'status': 'pending',
            'created_at': '2024-01-15T10:30:00Z',
            'updated_at': '2024-01-15T10:30:00Z',
            'expires_at': 1234567890
        }
        
        mock_aws_services['table'].get_item.return_value = {
            'Item': mock_item
        }
        
        job = job_service.get_job('job_123')
        
        assert job.job_id == 'job_123'
        assert job.status == JobStatus.PENDING
        mock_aws_services['table'].get_item.assert_called_once_with(
            Key={'job_id': 'job_123'}
        )
    
    def test_get_job_not_found(self, job_service, mock_aws_services):
        """Test job not found."""
        mock_aws_services['table'].get_item.return_value = {}
        
        with pytest.raises(JobNotFoundError):
            job_service.get_job('job_123')


class TestCancelJob:
    """Test cancel_job method."""
    
    def test_cancel_job_success(self, job_service, mock_aws_services):
        """Test successful job cancellation."""
        mock_item = {
            'job_id': 'job_123',
            'status': 'pending',
            'created_at': '2024-01-15T10:30:00Z',
            'updated_at': '2024-01-15T10:30:00Z'
        }
        
        mock_aws_services['table'].get_item.return_value = {
            'Item': mock_item
        }
        
        job = job_service.cancel_job('job_123')
        
        assert job.status == JobStatus.CANCELLED
        mock_aws_services['table'].update_item.assert_called_once()
    
    def test_cancel_job_already_completed(self, job_service, mock_aws_services):
        """Test cancelling already completed job."""
        mock_item = {
            'job_id': 'job_123',
            'status': 'completed',
            'created_at': '2024-01-15T10:30:00Z',
            'updated_at': '2024-01-15T10:30:00Z'
        }
        
        mock_aws_services['table'].get_item.return_value = {
            'Item': mock_item
        }
        
        with pytest.raises(JobAlreadyCompletedError):
            job_service.cancel_job('job_123')

