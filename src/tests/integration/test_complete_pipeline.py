"""
Integration tests for complete pipeline execution.

This module provides integration tests for the complete multi-stage pipeline:
preview → intermediate → final, including Step Functions orchestration.
"""
import pytest
import json
import os
from unittest.mock import patch, MagicMock, Mock
from botocore.exceptions import ClientError

from src.services.job_service import JobService
from src.services.sagemaker_service import SageMakerService
from src.services.preview_service import PreviewService
from src.pipeline.stage_2_intermediate import lambda_handler as stage2_handler
from src.pipeline.stage_3_final import lambda_handler as stage3_handler
from src.utils.errors import JobNotFoundError, LocationDetectionError


@pytest.fixture
def mock_aws_services():
    """Mock AWS services for testing."""
    with patch('src.services.job_service.boto3') as mock_boto3, \
         patch('src.services.sagemaker_service.boto3') as mock_sagemaker_boto3, \
         patch('src.services.preview_service.boto3') as mock_preview_boto3, \
         patch('src.pipeline.stage_2_intermediate.boto3') as mock_stage2_boto3, \
         patch('src.pipeline.stage_3_final.boto3') as mock_stage3_boto3:
        
        # Mock DynamoDB
        mock_dynamodb = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb
        mock_boto3.client.return_value = MagicMock()
        
        # Mock S3
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        
        # Mock SageMaker Runtime
        mock_sagemaker_runtime = MagicMock()
        mock_sagemaker_boto3.client.return_value = mock_sagemaker_runtime
        
        # Mock Step Functions
        mock_stepfunctions = MagicMock()
        mock_boto3.client.return_value = mock_stepfunctions
        
        yield {
            'dynamodb': mock_dynamodb,
            's3': mock_s3,
            'sagemaker_runtime': mock_sagemaker_runtime,
            'stepfunctions': mock_stepfunctions
        }


@pytest.fixture
def sample_job():
    """Sample job for testing."""
    from src.models.job import Job, JobStatus
    return Job(
        job_id='test-job-123',
        status=JobStatus.PENDING,
        blueprint_format='png',
        blueprint_s3_key='blueprints/test-job-123/blueprint.png',
        blueprint_hash='test-hash-123'
    )


@pytest.fixture
def sample_textract_result():
    """Sample Textract result."""
    return {
        'text_blocks': [
            {
                'id': 'text-1',
                'text': 'Room 101',
                'geometry': {
                    'BoundingBox': {
                        'Left': 0.1,
                        'Top': 0.2,
                        'Width': 0.3,
                        'Height': 0.05
                    }
                }
            }
        ],
        'layout_blocks': [
            {
                'id': 'layout-1',
                'blockType': 'PAGE',
                'geometry': {
                    'BoundingBox': {
                        'Left': 0.0,
                        'Top': 0.0,
                        'Width': 1.0,
                        'Height': 1.0
                    }
                }
            }
        ],
        'metadata': {
            'pages': 1,
            'analyzed_at': '2024-01-15T10:30:00Z'
        }
    }


@pytest.fixture
def sample_sagemaker_response():
    """Sample SageMaker model response."""
    return {
        'detections': [
            {
                'bbox': [50, 50, 200, 300],
                'confidence': 0.92,
                'name_hint': 'Kitchen',
                'vertices': [
                    [50, 50],
                    [200, 50],
                    [200, 300],
                    [50, 300]
                ]
            },
            {
                'bbox': [250, 100, 400, 350],
                'confidence': 0.88,
                'name_hint': 'Living Room',
                'vertices': [
                    [250, 100],
                    [400, 100],
                    [400, 350],
                    [250, 350]
                ]
            }
        ]
    }


class TestCompletePipeline:
    """Test complete pipeline execution."""
    
    def test_stage2_intermediate_processing(
        self,
        mock_aws_services,
        sample_job,
        sample_textract_result,
        sample_sagemaker_response
    ):
        """Test intermediate pipeline stage processing."""
        # Setup mocks
        mock_dynamodb = mock_aws_services['dynamodb']
        mock_s3 = mock_aws_services['s3']
        mock_sagemaker = mock_aws_services['sagemaker_runtime']
        
        # Mock DynamoDB job retrieval
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            'Item': {
                'job_id': sample_job.job_id,
                'status': sample_job.status.value,
                'blueprint_format': sample_job.blueprint_format,
                'blueprint_s3_key': sample_job.blueprint_s3_key,
                'blueprint_hash': sample_job.blueprint_hash
            }
        }
        mock_dynamodb.Table.return_value = mock_table
        
        # Mock S3 Textract results retrieval
        mock_s3.get_object.return_value = {
            'Body': MagicMock(read=lambda: json.dumps(sample_textract_result).encode('utf-8'))
        }
        
        # Mock SageMaker endpoint invocation
        mock_sagemaker.invoke_endpoint.return_value = {
            'Body': MagicMock(read=lambda: json.dumps(sample_sagemaker_response).encode('utf-8'))
        }
        
        # Mock S3 put_object for storing intermediate results
        mock_s3.put_object.return_value = {}
        
        # Set environment variables
        os.environ['JOBS_TABLE_NAME'] = 'test-jobs'
        os.environ['CACHE_BUCKET_NAME'] = 'test-cache'
        os.environ['SAGEMAKER_INTERMEDIATE_ENDPOINT_NAME'] = 'test-endpoint'
        os.environ['WEBSOCKET_CONNECTIONS_TABLE_NAME'] = 'test-websocket'
        
        # Create event
        event = {
            'job_id': sample_job.job_id
        }
        
        # Create mock context
        context = MagicMock()
        context.aws_request_id = 'test-request-id'
        
        # Execute handler
        response = stage2_handler(event, context)
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'success'
        assert 'data' in body
        assert body['data']['stage'] == 'intermediate'
        assert 'rooms' in body['data']
        assert len(body['data']['rooms']) == 2
        
        # Verify SageMaker was called
        mock_sagemaker.invoke_endpoint.assert_called_once()
        
        # Verify S3 storage
        assert mock_s3.put_object.called
    
    def test_stage3_final_processing(
        self,
        mock_aws_services,
        sample_job,
        sample_textract_result,
        sample_sagemaker_response
    ):
        """Test final pipeline stage processing."""
        # Setup mocks
        mock_dynamodb = mock_aws_services['dynamodb']
        mock_s3 = mock_aws_services['s3']
        mock_sagemaker = mock_aws_services['sagemaker_runtime']
        
        # Mock DynamoDB job retrieval
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            'Item': {
                'job_id': sample_job.job_id,
                'status': sample_job.status.value,
                'blueprint_format': sample_job.blueprint_format,
                'blueprint_s3_key': sample_job.blueprint_s3_key,
                'blueprint_hash': sample_job.blueprint_hash
            }
        }
        mock_dynamodb.Table.return_value = mock_table
        
        # Mock intermediate results from S3
        intermediate_result = {
            'job_id': sample_job.job_id,
            'stage': 'intermediate',
            'rooms': [
                {
                    'id': 'room_001',
                    'bounding_box': [50, 50, 200, 300],
                    'confidence': 0.92
                }
            ]
        }
        mock_s3.get_object.return_value = {
            'Body': MagicMock(read=lambda: json.dumps(intermediate_result).encode('utf-8'))
        }
        
        # Mock Textract results
        def get_object_side_effect(Bucket, Key):
            if 'textract' in Key:
                return {
                    'Body': MagicMock(read=lambda: json.dumps(sample_textract_result).encode('utf-8'))
                }
            elif 'intermediate' in Key:
                return {
                    'Body': MagicMock(read=lambda: json.dumps(intermediate_result).encode('utf-8'))
                }
            raise ClientError({'Error': {'Code': 'NoSuchKey'}}, 'GetObject')
        
        mock_s3.get_object.side_effect = get_object_side_effect
        
        # Mock SageMaker endpoint invocation
        mock_sagemaker.invoke_endpoint.return_value = {
            'Body': MagicMock(read=lambda: json.dumps(sample_sagemaker_response).encode('utf-8'))
        }
        
        # Mock S3 put_object for storing final results
        mock_s3.put_object.return_value = {}
        
        # Mock DynamoDB update_item
        mock_table.update_item.return_value = {}
        
        # Set environment variables
        os.environ['JOBS_TABLE_NAME'] = 'test-jobs'
        os.environ['CACHE_BUCKET_NAME'] = 'test-cache'
        os.environ['SAGEMAKER_FINAL_ENDPOINT_NAME'] = 'test-endpoint'
        os.environ['WEBSOCKET_CONNECTIONS_TABLE_NAME'] = 'test-websocket'
        os.environ['OUTPUT_FORMAT'] = 'mvp'
        os.environ['CONFIDENCE_THRESHOLD'] = '0.7'
        
        # Create event
        event = {
            'job_id': sample_job.job_id
        }
        
        # Create mock context
        context = MagicMock()
        context.aws_request_id = 'test-request-id'
        
        # Execute handler
        response = stage3_handler(event, context)
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'success'
        assert 'data' in body
        assert body['data']['stage'] == 'final'
        assert 'rooms' in body['data']
        assert len(body['data']['rooms']) == 2
        
        # Verify SageMaker was called
        mock_sagemaker.invoke_endpoint.assert_called_once()
        
        # Verify S3 storage
        assert mock_s3.put_object.called
        
        # Verify DynamoDB update
        assert mock_table.update_item.called
    
    def test_job_service_start_pipeline_execution(
        self,
        mock_aws_services,
        sample_job
    ):
        """Test job service can trigger Step Functions state machine."""
        # Setup mocks
        mock_dynamodb = mock_aws_services['dynamodb']
        mock_stepfunctions = mock_aws_services['stepfunctions']
        
        # Mock DynamoDB job retrieval
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            'Item': {
                'job_id': sample_job.job_id,
                'status': sample_job.status.value,
                'blueprint_format': sample_job.blueprint_format,
                'blueprint_s3_key': sample_job.blueprint_s3_key,
                'blueprint_hash': sample_job.blueprint_hash
            }
        }
        mock_table.update_item.return_value = {}
        mock_dynamodb.Table.return_value = mock_table
        
        # Mock Step Functions start_execution
        mock_stepfunctions.start_execution.return_value = {
            'executionArn': 'arn:aws:states:us-east-1:123456789012:execution:test-state-machine:test-execution'
        }
        
        # Set environment variables
        os.environ['JOBS_TABLE_NAME'] = 'test-jobs'
        os.environ['BLUEPRINTS_BUCKET_NAME'] = 'test-blueprints'
        os.environ['STEP_FUNCTIONS_STATE_MACHINE_ARN'] = 'arn:aws:states:us-east-1:123456789012:stateMachine:test-state-machine'
        
        # Create job service
        job_service = JobService()
        
        # Start pipeline execution
        execution_arn = job_service.start_pipeline_execution(sample_job.job_id)
        
        # Verify execution ARN
        assert execution_arn.startswith('arn:aws:states:')
        
        # Verify Step Functions was called
        mock_stepfunctions.start_execution.assert_called_once()
        call_args = mock_stepfunctions.start_execution.call_args
        assert call_args[1]['stateMachineArn'] == os.environ['STEP_FUNCTIONS_STATE_MACHINE_ARN']
        assert 'job_id' in json.loads(call_args[1]['input'])
        
        # Verify job was updated with execution ARN
        assert mock_table.update_item.called
    
    def test_pipeline_error_handling(
        self,
        mock_aws_services,
        sample_job
    ):
        """Test pipeline error handling."""
        # Setup mocks
        mock_dynamodb = mock_aws_services['dynamodb']
        
        # Mock DynamoDB job retrieval to raise error
        mock_table = MagicMock()
        mock_table.get_item.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException'}},
            'GetItem'
        )
        mock_dynamodb.Table.return_value = mock_table
        
        # Set environment variables
        os.environ['JOBS_TABLE_NAME'] = 'test-jobs'
        os.environ['CACHE_BUCKET_NAME'] = 'test-cache'
        os.environ['SAGEMAKER_INTERMEDIATE_ENDPOINT_NAME'] = 'test-endpoint'
        os.environ['WEBSOCKET_CONNECTIONS_TABLE_NAME'] = 'test-websocket'
        
        # Create event
        event = {
            'job_id': sample_job.job_id
        }
        
        # Create mock context
        context = MagicMock()
        context.aws_request_id = 'test-request-id'
        
        # Execute handler
        response = stage2_handler(event, context)
        
        # Verify error response
        assert response['statusCode'] in [404, 500]
        body = json.loads(response['body'])
        assert body['status'] == 'error'
        assert 'error' in body
    
    def test_processing_time_under_30_seconds(
        self,
        mock_aws_services,
        sample_job,
        sample_textract_result,
        sample_sagemaker_response
    ):
        """Test that processing time stays under 30 seconds."""
        import time
        
        # Setup mocks (same as test_stage2_intermediate_processing)
        mock_dynamodb = mock_aws_services['dynamodb']
        mock_s3 = mock_aws_services['s3']
        mock_sagemaker = mock_aws_services['sagemaker_runtime']
        
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            'Item': {
                'job_id': sample_job.job_id,
                'status': sample_job.status.value,
                'blueprint_format': sample_job.blueprint_format,
                'blueprint_s3_key': sample_job.blueprint_s3_key,
                'blueprint_hash': sample_job.blueprint_hash
            }
        }
        mock_dynamodb.Table.return_value = mock_table
        
        mock_s3.get_object.return_value = {
            'Body': MagicMock(read=lambda: json.dumps(sample_textract_result).encode('utf-8'))
        }
        
        mock_sagemaker.invoke_endpoint.return_value = {
            'Body': MagicMock(read=lambda: json.dumps(sample_sagemaker_response).encode('utf-8'))
        }
        
        mock_s3.put_object.return_value = {}
        
        os.environ['JOBS_TABLE_NAME'] = 'test-jobs'
        os.environ['CACHE_BUCKET_NAME'] = 'test-cache'
        os.environ['SAGEMAKER_INTERMEDIATE_ENDPOINT_NAME'] = 'test-endpoint'
        os.environ['WEBSOCKET_CONNECTIONS_TABLE_NAME'] = 'test-websocket'
        
        event = {'job_id': sample_job.job_id}
        context = MagicMock()
        context.aws_request_id = 'test-request-id'
        
        # Execute and measure time
        start_time = time.time()
        response = stage2_handler(event, context)
        elapsed_time = time.time() - start_time
        
        # Verify processing time is under 30 seconds
        assert elapsed_time < 30.0, f"Processing took {elapsed_time} seconds, expected < 30 seconds"
        
        # Verify response includes timing metrics
        body = json.loads(response['body'])
        if 'data' in body and 'processing_time_seconds' in body['data']:
            assert body['data']['processing_time_seconds'] < 30.0

