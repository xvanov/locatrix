"""
Unit tests for Stage 3 Final pipeline handler.
"""
import pytest
import json
import os
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

from src.pipeline.stage_3_final import lambda_handler
from src.utils.errors import JobNotFoundError, LocationDetectionError


@pytest.fixture
def mock_aws_services():
    """Mock AWS services for testing."""
    with patch('boto3.client') as mock_client, \
         patch('boto3.resource') as mock_resource:
        
        # Mock DynamoDB
        mock_dynamodb = MagicMock()
        mock_resource.return_value = mock_dynamodb
        
        # Mock S3
        mock_s3 = MagicMock()
        mock_client.return_value = mock_s3
        
        yield {
            'dynamodb': mock_dynamodb,
            's3': mock_s3,
            'client': mock_client,
            'resource': mock_resource
        }


@pytest.fixture
def sample_intermediate_result():
    """Sample intermediate result."""
    return {
        'job_id': 'test-job-123',
        'stage': 'intermediate',
        'rooms': [
            {
                'id': 'room_001',
                'bounding_box': [50, 50, 200, 300],
                'confidence': 0.92,
                'name_hint': 'Kitchen'
            }
        ]
    }


@pytest.fixture
def sample_textract_result():
    """Sample Textract result."""
    return {
        'text_blocks': [],
        'layout_blocks': [],
        'metadata': {'pages': 1}
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
                'vertices': [[50, 50], [200, 50], [200, 300], [50, 300]]
            }
        ]
    }


class TestStage3Final:
    """Test Stage 3 Final pipeline handler."""
    
    def test_stage3_success(
        self,
        mock_aws_services,
        sample_intermediate_result,
        sample_textract_result,
        sample_sagemaker_response
    ):
        """Test successful final stage processing."""
        # Setup environment
        os.environ['JOBS_TABLE_NAME'] = 'test-jobs'
        os.environ['BLUEPRINTS_BUCKET_NAME'] = 'test-blueprints'
        os.environ['CACHE_BUCKET_NAME'] = 'test-cache'
        os.environ['SAGEMAKER_FINAL_ENDPOINT_NAME'] = 'test-endpoint'
        os.environ['WEBSOCKET_CONNECTIONS_TABLE_NAME'] = 'test-websocket'
        os.environ['OUTPUT_FORMAT'] = 'mvp'
        os.environ['CONFIDENCE_THRESHOLD'] = '0.7'
        
        # Setup mocks
        mock_resource = mock_aws_services['resource']
        mock_client = mock_aws_services['client']
        mock_s3 = mock_aws_services['s3']
        
        # Mock DynamoDB job retrieval
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            'Item': {
                'job_id': 'test-job-123',
                'status': 'pending'
            }
        }
        mock_table.update_item.return_value = {}
        mock_resource.return_value.Table.return_value = mock_table
        
        # Mock S3 client
        mock_client.return_value = mock_s3
        
        # Mock S3 get_object for intermediate and Textract results
        def get_object_side_effect(Bucket, Key):
            if 'intermediate' in Key:
                return {
                    'Body': MagicMock(read=lambda: json.dumps(sample_intermediate_result).encode('utf-8'))
                }
            elif 'textract' in Key:
                return {
                    'Body': MagicMock(read=lambda: json.dumps(sample_textract_result).encode('utf-8'))
                }
            raise ClientError({'Error': {'Code': 'NoSuchKey'}}, 'GetObject')
        
        mock_s3.get_object.side_effect = get_object_side_effect
        mock_s3.put_object.return_value = {}
        
        # Create event
        event = {'job_id': 'test-job-123'}
        context = MagicMock()
        context.aws_request_id = 'test-request-id'
        
        # Mock services
        with patch('src.pipeline.stage_3_final.SageMakerService') as mock_sagemaker_service, \
             patch('src.pipeline.stage_3_final.PreviewService') as mock_preview_service, \
             patch('src.pipeline.stage_3_final.JobService') as mock_job_service:
            
            # Mock PreviewService
            mock_preview_instance = MagicMock()
            mock_preview_instance.get_textract_results.return_value = sample_textract_result
            mock_preview_service.return_value = mock_preview_instance
            
            # Mock JobService
            mock_job_instance = MagicMock()
            from src.models.job import Job, JobStatus
            mock_job = Job(
                job_id='test-job-123',
                status=JobStatus.PENDING
            )
            mock_job_instance.get_job.return_value = mock_job
            mock_job_service.return_value = mock_job_instance
            
            # Mock SageMaker service
            mock_service_instance = MagicMock()
            mock_service_instance.preprocess_input.return_value = {'text_blocks': [], 'layout_blocks': []}
            mock_service_instance.invoke_endpoint.return_value = sample_sagemaker_response
            mock_service_instance.postprocess_output.return_value = {
                'rooms': [
                    {
                        'id': 'room_001',
                        'bounding_box': [50, 50, 200, 300],
                        'confidence': 0.92,
                        'name_hint': 'Kitchen'
                    }
                ],
                'detection_count': 1,
                'filtered_count': 0
            }
            mock_sagemaker_service.return_value = mock_service_instance
            
            # Mock WebSocket service
            with patch('src.pipeline.stage_3_final.WebSocketService') as mock_websocket_service:
                mock_ws_instance = MagicMock()
                mock_ws_instance.send_job_complete.return_value = 1
                mock_websocket_service.return_value = mock_ws_instance
                
                # Execute handler
                response = lambda_handler(event, context)
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'success'
        assert 'data' in body
        assert body['data']['stage'] == 'final'
        assert 'rooms' in body['data']
        
        # Verify S3 storage was called
        assert mock_s3.put_object.called
        
        # Verify DynamoDB update was called
        assert mock_table.update_item.called
    
    def test_stage3_missing_job_id(self, mock_aws_services):
        """Test handling of missing job_id."""
        event = {}
        context = MagicMock()
        context.aws_request_id = 'test-request-id'
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['status'] == 'error'
        assert 'error' in body
    
    def test_stage3_intermediate_results_not_found(self, mock_aws_services):
        """Test handling of missing intermediate results."""
        os.environ['JOBS_TABLE_NAME'] = 'test-jobs'
        os.environ['BLUEPRINTS_BUCKET_NAME'] = 'test-blueprints'
        os.environ['CACHE_BUCKET_NAME'] = 'test-cache'
        
        mock_client = mock_aws_services['client']
        mock_s3 = mock_aws_services['s3']
        mock_client.return_value = mock_s3
        
        # Mock S3 to return None (no intermediate results)
        mock_s3.get_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey'}},
            'GetObject'
        )
        
        # Mock services
        with patch('src.pipeline.stage_3_final.JobService') as mock_job_service:
            # Mock JobService
            mock_job_instance = MagicMock()
            from src.models.job import Job, JobStatus
            mock_job = Job(
                job_id='test-job-123',
                status=JobStatus.PENDING
            )
            mock_job_instance.get_job.return_value = mock_job
            mock_job_service.return_value = mock_job_instance
            
            event = {'job_id': 'test-job-123'}
            context = MagicMock()
            context.aws_request_id = 'test-request-id'
            
            response = lambda_handler(event, context)
        
        assert response['statusCode'] in [404, 500]
        body = json.loads(response['body'])
        assert body['status'] == 'error'

