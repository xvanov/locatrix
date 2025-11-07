"""
Unit tests for job model.
"""
import pytest
from datetime import datetime, timezone

from src.models.job import Job, JobStatus


class TestJob:
    """Test Job model."""
    
    def test_job_creation(self):
        """Test job creation."""
        job = Job(
            job_id='job_123',
            status=JobStatus.PENDING,
            blueprint_format='pdf'
        )
        
        assert job.job_id == 'job_123'
        assert job.status == JobStatus.PENDING
        assert job.blueprint_format == 'pdf'
    
    def test_job_id_generation(self):
        """Test automatic job ID generation."""
        job = Job()
        assert job.job_id.startswith('job_')
        assert len(job.job_id) > 10
    
    def test_job_to_dict(self):
        """Test job to dictionary conversion."""
        job = Job(
            job_id='job_123',
            status=JobStatus.PENDING,
            blueprint_format='pdf'
        )
        
        job_dict = job.to_dict()
        assert job_dict['job_id'] == 'job_123'
        assert job_dict['status'] == 'pending'
        assert job_dict['blueprint_format'] == 'pdf'
    
    def test_job_from_dict(self):
        """Test job from dictionary creation."""
        job_dict = {
            'job_id': 'job_123',
            'status': 'pending',
            'blueprint_format': 'pdf',
            'created_at': '2024-01-15T10:30:00Z',
            'updated_at': '2024-01-15T10:30:00Z'
        }
        
        job = Job.from_dict(job_dict)
        assert job.job_id == 'job_123'
        assert job.status == JobStatus.PENDING
        assert job.blueprint_format == 'pdf'
    
    def test_job_to_dynamodb_item(self):
        """Test job to DynamoDB item conversion."""
        job = Job(
            job_id='job_123',
            status=JobStatus.PENDING,
            created_at='2024-01-15T10:30:00Z'
        )
        
        item = job.to_dynamodb_item()
        assert item['job_id'] == 'job_123'
        assert 'expires_at' in item
        assert isinstance(item['expires_at'], int)
    
    def test_job_from_dynamodb_item(self):
        """Test job from DynamoDB item creation."""
        item = {
            'job_id': 'job_123',
            'status': 'pending',
            'expires_at': 1234567890,
            'created_at': '2024-01-15T10:30:00Z'
        }
        
        job = Job.from_dynamodb_item(item)
        assert job.job_id == 'job_123'
        assert 'expires_at' not in job.to_dict()
    
    def test_update_status(self):
        """Test updating job status."""
        job = Job(job_id='job_123', status=JobStatus.PENDING)
        job.update_status(JobStatus.PROCESSING)
        
        assert job.status == JobStatus.PROCESSING
        assert job.updated_at != job.created_at
    
    def test_can_be_cancelled(self):
        """Test can_be_cancelled method."""
        pending_job = Job(job_id='job_1', status=JobStatus.PENDING)
        processing_job = Job(job_id='job_2', status=JobStatus.PROCESSING)
        completed_job = Job(job_id='job_3', status=JobStatus.COMPLETED)
        
        assert pending_job.can_be_cancelled() is True
        assert processing_job.can_be_cancelled() is True
        assert completed_job.can_be_cancelled() is False
    
    def test_validate_job(self):
        """Test job validation."""
        valid_job = Job(
            job_id='job_123',
            status=JobStatus.PENDING,
            blueprint_format='pdf'
        )
        assert valid_job.validate() is True
    
    def test_validate_invalid_job_id(self):
        """Test validation with invalid job ID."""
        invalid_job = Job(job_id='invalid', status=JobStatus.PENDING)
        
        with pytest.raises(ValueError, match="must start with 'job_'"):
            invalid_job.validate()
    
    def test_validate_invalid_format(self):
        """Test validation with invalid format."""
        invalid_job = Job(
            job_id='job_123',
            status=JobStatus.PENDING,
            blueprint_format='gif'
        )
        
        with pytest.raises(ValueError, match="must be one of"):
            invalid_job.validate()

