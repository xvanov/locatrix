"""
Unit tests for Stage 2 Intermediate pipeline handler.
"""
import pytest
import json
import os
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

from src.pipeline.stage_2_intermediate import lambda_handler
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
def sample_textract_result():
    """Sample Textract result."""
    return {
        'text_blocks': [
            {
                'id': 'text-1',
                'text': 'Room 101',
                'geometry': {'BoundingBox': {'Left': 0.1, 'Top': 0.2, 'Width': 0.3, 'Height': 0.05}}
            }
        ],
        'layout_blocks': [
            {
                'id': 'layout-1',
                'blockType': 'PAGE',
                'geometry': {'BoundingBox': {'Left': 0.0, 'Top': 0.0, 'Width': 1.0, 'Height': 1.0}}
            }
        ],
        'metadata': {'pages': 1, 'analyzed_at': '2024-01-15T10:30:00Z'}
    }


@pytest.fixture
def sample_sagemaker_response():
    """Sample SageMaker model response."""
    return {
        'detections': [
            {
                'bbox': [50, 50, 200, 300],
                'confidence': 0.92,
                'name_hint': 'Kitchen'
            }
        ]
    }


class TestStage2Intermediate:
    """Test Stage 2 Intermediate pipeline handler."""
    
    def test_stage2_success(
        self,
        mock_aws_services,
        sample_textract_result,
        sample_sagemaker_response
    ):
        """Test successful intermediate stage processing."""
        # Setup environment
        os.environ['JOBS_TABLE_NAME'] = 'test-jobs'
        os.environ['BLUEPRINTS_BUCKET_NAME'] = 'test-blueprints'
        os.environ['CACHE_BUCKET_NAME'] = 'test-cache'
        os.environ['SAGEMAKER_INTERMEDIATE_ENDPOINT_NAME'] = 'test-endpoint'
        os.environ['WEBSOCKET_CONNECTIONS_TABLE_NAME'] = 'test-websocket'
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
                'status': 'pending',
                'blueprint_format': 'png',
                'blueprint_s3_key': 'blueprints/test-job-123/blueprint.png'
            }
        }
        mock_resource.return_value.Table.return_value = mock_table
        
        # Mock S3 client
        mock_client.return_value = mock_s3
        
        # Mock S3 Textract results retrieval
        mock_s3.get_object.return_value = {
            'Body': MagicMock(read=lambda: json.dumps(sample_textract_result).encode('utf-8'))
        }
        
        # Mock S3 put_object for storing intermediate results
        mock_s3.put_object.return_value = {}
        
        # Create event
        event = {'job_id': 'test-job-123'}
        context = MagicMock()
        context.aws_request_id = 'test-request-id'
        
        # Mock SageMaker service
        with patch('src.pipeline.stage_2_intermediate.SageMakerService') as mock_sagemaker_service, \
             patch('src.pipeline.stage_2_intermediate.PreviewService') as mock_preview_service, \
             patch('src.pipeline.stage_2_intermediate.JobService') as mock_job_service:
            
            # Mock PreviewService
            mock_preview_instance = MagicMock()
            mock_preview_instance.get_textract_results.return_value = sample_textract_result
            mock_preview_service.return_value = mock_preview_instance
            
            # Mock JobService
            mock_job_instance = MagicMock()
            from src.models.job import Job, JobStatus
            mock_job = Job(
                job_id='test-job-123',
                status=JobStatus.PENDING,
                blueprint_format='png',
                blueprint_s3_key='blueprints/test-job-123/blueprint.png'
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
                'detection_count': 1
            }
            mock_sagemaker_service.return_value = mock_service_instance
            
            # Mock WebSocket service
            with patch('src.pipeline.stage_2_intermediate.WebSocketService') as mock_websocket_service:
                mock_ws_instance = MagicMock()
                mock_ws_instance.send_progress_update.return_value = 1
                mock_websocket_service.return_value = mock_ws_instance
                
                # Execute handler
                response = lambda_handler(event, context)
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'success'
        assert 'data' in body
        assert body['data']['stage'] == 'intermediate'
        assert 'rooms' in body['data']
        
        # Verify S3 storage was called
        assert mock_s3.put_object.called
    
    def test_stage2_missing_job_id(self, mock_aws_services):
        """Test handling of missing job_id."""
        event = {}
        context = MagicMock()
        context.aws_request_id = 'test-request-id'
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['status'] == 'error'
        assert 'error' in body
    
    def test_stage2_textract_results_not_found(self, mock_aws_services):
        """Test handling of missing Textract results."""
        os.environ['JOBS_TABLE_NAME'] = 'test-jobs'
        os.environ['BLUEPRINTS_BUCKET_NAME'] = 'test-blueprints'
        os.environ['CACHE_BUCKET_NAME'] = 'test-cache'
        
        # Mock PreviewService to return None
        with patch('src.pipeline.stage_2_intermediate.PreviewService') as mock_preview_service, \
             patch('src.pipeline.stage_2_intermediate.JobService') as mock_job_service:
            
            # Mock PreviewService
            mock_preview_instance = MagicMock()
            mock_preview_instance.get_textract_results.return_value = None
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
            
            event = {'job_id': 'test-job-123'}
            context = MagicMock()
            context.aws_request_id = 'test-request-id'
            
            response = lambda_handler(event, context)
        
        assert response['statusCode'] in [404, 500]
        body = json.loads(response['body'])
        assert body['status'] == 'error'

