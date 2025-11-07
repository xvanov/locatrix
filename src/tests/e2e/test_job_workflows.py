"""
End-to-end tests for job management API.

These tests run against a deployed AWS environment and verify:
- Job creation with file upload
- Job retrieval
- Job cancellation
- Error handling
- DynamoDB and S3 integration

Prerequisites:
- AWS SAM CLI installed
- AWS credentials configured
- Stack deployed to AWS
- API Gateway endpoint URL available
"""
import pytest
import requests
import base64
import json
import os
import time
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError


# Get API endpoint from environment or SAM outputs
API_ENDPOINT = os.environ.get('API_ENDPOINT', '')
if not API_ENDPOINT:
    # Try to get from SAM stack outputs
    try:
        import subprocess
        result = subprocess.run(
            ['sam', 'list', 'stack-outputs', '--stack-name', 'location-detection-api', '--region', 'us-east-1', '--output', 'json'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            import json as json_module
            outputs = json_module.loads(result.stdout)
            for output in outputs.get('StackOutputs', []):
                if output.get('OutputKey') == 'ApiUrl':
                    API_ENDPOINT = output.get('OutputValue', '')
                    break
    except Exception:
        pass

# Fallback to default if still not set
if not API_ENDPOINT:
    API_ENDPOINT = os.environ.get('API_ENDPOINT', 'https://jznoy1ogvj.execute-api.us-east-1.amazonaws.com')

# Get AWS resources from environment
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')
JOBS_TABLE_NAME = os.environ.get('JOBS_TABLE_NAME', f'{ENVIRONMENT}-jobs')
BLUEPRINTS_BUCKET_NAME = os.environ.get('BLUEPRINTS_BUCKET_NAME', f'location-detection-{ENVIRONMENT}-blueprints')

# AWS clients
dynamodb = boto3.client('dynamodb')
s3 = boto3.client('s3')


def create_test_file(format: str = 'pdf', size_kb: int = 10) -> bytes:
    """Create a test file for upload."""
    if format == 'pdf':
        # Simple PDF header + content
        content = b'%PDF-1.4\n' + b'x' * (size_kb * 1024)
    elif format == 'png':
        # Simple PNG header + content
        content = b'\x89PNG\r\n\x1a\n' + b'x' * (size_kb * 1024)
    elif format == 'jpg':
        # Simple JPG header + content
        content = b'\xff\xd8\xff\xe0' + b'x' * (size_kb * 1024)
    else:
        content = b'x' * (size_kb * 1024)
    return content


class TestJobCreation:
    """Test job creation endpoint."""
    
    def test_create_job_with_pdf(self):
        """Test creating a job with PDF file."""
        file_content = create_test_file('pdf', size_kb=10)
        encoded_file = base64.b64encode(file_content).decode('utf-8')
        
        payload = {
            'blueprint': {
                'file': encoded_file,
                'format': 'pdf',
                'filename': 'test-blueprint.pdf'
            }
        }
        
        response = requests.post(
            f'{API_ENDPOINT}/api/v1/jobs',
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data['status'] == 'success'
        assert 'job_id' in data['data']
        assert data['data']['status'] == 'pending'
        assert data['data']['blueprint_format'] == 'pdf'
        
        return data['data']['job_id']
    
    def test_create_job_with_png(self):
        """Test creating a job with PNG file."""
        file_content = create_test_file('png', size_kb=5)
        encoded_file = base64.b64encode(file_content).decode('utf-8')
        
        payload = {
            'blueprint': {
                'file': encoded_file,
                'format': 'png',
                'filename': 'test-blueprint.png'
            }
        }
        
        response = requests.post(
            f'{API_ENDPOINT}/api/v1/jobs',
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data['data']['blueprint_format'] == 'png'
        
        return data['data']['job_id']
    
    def test_create_job_verify_dynamodb(self):
        """Test that job is stored in DynamoDB."""
        job_id = self.test_create_job_with_pdf()
        
        # Wait a moment for DynamoDB to be consistent
        time.sleep(1)
        
        # Query DynamoDB directly
        response = dynamodb.get_item(
            TableName=JOBS_TABLE_NAME,
            Key={'job_id': {'S': job_id}}
        )
        
        assert 'Item' in response, f"Job {job_id} not found in DynamoDB"
        item = response['Item']
        assert item['job_id']['S'] == job_id
        assert item['status']['S'] == 'pending'
        assert 'blueprint_s3_key' in item
        assert 'blueprint_hash' in item
        
        return job_id
    
    def test_create_job_verify_s3(self):
        """Test that blueprint file is uploaded to S3."""
        job_id = self.test_create_job_with_pdf()
        
        # Wait a moment for S3 upload
        time.sleep(1)
        
        # Get job from DynamoDB to get S3 key
        response = dynamodb.get_item(
            TableName=JOBS_TABLE_NAME,
            Key={'job_id': {'S': job_id}}
        )
        s3_key = response['Item']['blueprint_s3_key']['S']
        
        # Verify file exists in S3
        try:
            s3.head_object(Bucket=BLUEPRINTS_BUCKET_NAME, Key=s3_key)
        except ClientError as e:
            pytest.fail(f"File not found in S3: {s3_key}. Error: {e}")
        
        # Verify S3 key format: blueprints/{job_id}/{filename}
        assert s3_key.startswith('blueprints/')
        assert job_id in s3_key
        
        return job_id


class TestJobRetrieval:
    """Test job retrieval endpoint."""
    
    def test_get_job_success(self):
        """Test retrieving a job successfully."""
        # Create a job first
        file_content = create_test_file('pdf', size_kb=10)
        encoded_file = base64.b64encode(file_content).decode('utf-8')
        
        create_response = requests.post(
            f'{API_ENDPOINT}/api/v1/jobs',
            json={
                'blueprint': {
                    'file': encoded_file,
                    'format': 'pdf',
                    'filename': 'test.pdf'
                }
            },
            headers={'Content-Type': 'application/json'}
        )
        job_id = create_response.json()['data']['job_id']
        
        # Retrieve the job
        response = requests.get(f'{API_ENDPOINT}/api/v1/jobs/{job_id}')
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['data']['job_id'] == job_id
        assert data['data']['status'] == 'pending'
    
    def test_get_job_not_found(self):
        """Test retrieving a non-existent job."""
        response = requests.get(f'{API_ENDPOINT}/api/v1/jobs/job_nonexistent_123')
        
        assert response.status_code == 404
        data = response.json()
        assert data['status'] == 'error'
        assert data['error']['code'] == 'JOB_NOT_FOUND'


class TestJobCancellation:
    """Test job cancellation endpoint."""
    
    def test_cancel_job_success(self):
        """Test cancelling a job successfully."""
        # Create a job first
        file_content = create_test_file('pdf', size_kb=10)
        encoded_file = base64.b64encode(file_content).decode('utf-8')
        
        create_response = requests.post(
            f'{API_ENDPOINT}/api/v1/jobs',
            json={
                'blueprint': {
                    'file': encoded_file,
                    'format': 'pdf',
                    'filename': 'test.pdf'
                }
            },
            headers={'Content-Type': 'application/json'}
        )
        job_id = create_response.json()['data']['job_id']
        
        # Cancel the job
        response = requests.delete(f'{API_ENDPOINT}/api/v1/jobs/{job_id}')
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['data']['status'] == 'cancelled'
        
        # Verify in DynamoDB
        time.sleep(1)
        db_response = dynamodb.get_item(
            TableName=JOBS_TABLE_NAME,
            Key={'job_id': {'S': job_id}}
        )
        assert db_response['Item']['status']['S'] == 'cancelled'
    
    def test_cancel_job_not_found(self):
        """Test cancelling a non-existent job."""
        response = requests.delete(f'{API_ENDPOINT}/api/v1/jobs/job_nonexistent_123')
        
        assert response.status_code == 404
        data = response.json()
        assert data['status'] == 'error'
        assert data['error']['code'] == 'JOB_NOT_FOUND'


class TestErrorHandling:
    """Test error handling."""
    
    def test_invalid_file_format(self):
        """Test creating job with invalid file format."""
        file_content = create_test_file('pdf', size_kb=10)
        encoded_file = base64.b64encode(file_content).decode('utf-8')
        
        payload = {
            'blueprint': {
                'file': encoded_file,
                'format': 'gif',  # Invalid format
                'filename': 'test.gif'
            }
        }
        
        response = requests.post(
            f'{API_ENDPOINT}/api/v1/jobs',
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data['status'] == 'error'
        assert data['error']['code'] == 'INVALID_FILE_FORMAT'
    
    def test_file_too_large(self):
        """Test creating job with file too large."""
        # Create a file larger than 50MB
        # Note: API Gateway HTTP API has a 10MB payload limit, so files >10MB
        # will be rejected with 413 before reaching Lambda. This is acceptable behavior.
        large_file = b'x' * (51 * 1024 * 1024)
        encoded_file = base64.b64encode(large_file).decode('utf-8')
        
        payload = {
            'blueprint': {
                'file': encoded_file,
                'format': 'pdf',
                'filename': 'large.pdf'
            }
        }
        
        response = requests.post(
            f'{API_ENDPOINT}/api/v1/jobs',
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        
        # API Gateway rejects payloads >10MB with 413, which is acceptable
        # Our Lambda validates at 50MB, but API Gateway protects us from oversized requests
        assert response.status_code in [400, 413], f"Expected 400 or 413, got {response.status_code}: {response.text}"
        
        # If it's 413, API Gateway rejected it (no JSON body)
        # If it's 400, Lambda validated and rejected it
        if response.status_code == 400:
            data = response.json()
            assert data['status'] == 'error'
            assert data['error']['code'] == 'FILE_TOO_LARGE'


class TestJobLifecycle:
    """Test complete job lifecycle."""
    
    def test_complete_job_lifecycle(self):
        """Test complete job lifecycle: create → retrieve → cancel."""
        # 1. Create job
        file_content = create_test_file('pdf', size_kb=10)
        encoded_file = base64.b64encode(file_content).decode('utf-8')
        
        create_response = requests.post(
            f'{API_ENDPOINT}/api/v1/jobs',
            json={
                'blueprint': {
                    'file': encoded_file,
                    'format': 'pdf',
                    'filename': 'lifecycle-test.pdf'
                }
            },
            headers={'Content-Type': 'application/json'}
        )
        
        assert create_response.status_code == 201
        job_id = create_response.json()['data']['job_id']
        
        # 2. Retrieve job
        get_response = requests.get(f'{API_ENDPOINT}/api/v1/jobs/{job_id}')
        assert get_response.status_code == 200
        assert get_response.json()['data']['status'] == 'pending'
        
        # 3. Cancel job
        cancel_response = requests.delete(f'{API_ENDPOINT}/api/v1/jobs/{job_id}')
        assert cancel_response.status_code == 200
        assert cancel_response.json()['data']['status'] == 'cancelled'
        
        # 4. Verify cancellation persisted
        time.sleep(1)
        final_response = requests.get(f'{API_ENDPOINT}/api/v1/jobs/{job_id}')
        assert final_response.json()['data']['status'] == 'cancelled'
        
        # 5. Verify cannot cancel again (should fail or return cancelled status)
        # This depends on implementation - may return 400 or 200 with cancelled status


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v', '--tb=short'])

