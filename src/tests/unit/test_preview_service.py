"""
Unit tests for PreviewService.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError

from src.services.preview_service import PreviewService
from src.utils.errors import ServiceUnavailableError


@pytest.fixture
def mock_aws_services():
    """Mock AWS services."""
    with patch('src.services.preview_service.boto3') as mock_boto3:
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
def preview_service(mock_aws_services):
    """Create PreviewService instance with mocked AWS services."""
    with patch.dict('os.environ', {
        'PREVIEW_CACHE_TABLE_NAME': 'test-preview-cache',
        'CACHE_BUCKET_NAME': 'test-cache'
    }):
        return PreviewService(
            preview_cache_table_name='test-preview-cache',
            cache_bucket_name='test-cache'
        )


@pytest.fixture
def sample_preview_result():
    """Sample preview result."""
    return {
        'job_id': 'job_123',
        'stage': 'preview',
        'rooms': [
            {
                'id': 'room_001',
                'bounding_box': [50, 50, 200, 300],
                'name_hint': 'Kitchen',
                'confidence': 0.75
            }
        ],
        'processing_time_seconds': 3.2,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }


class TestGetCachedPreview:
    """Test get_cached_preview method."""
    
    def test_get_cached_preview_success(self, preview_service, mock_aws_services, sample_preview_result):
        """Test successful cache retrieval."""
        blueprint_hash = 'abc123'
        model_version = '1.0.0'
        cache_key = f"preview:{blueprint_hash}:{model_version}"
        
        # Mock DynamoDB get_item response
        mock_aws_services['table'].get_item.return_value = {
            'Item': {
                'blueprint_hash': cache_key,
                'job_id': sample_preview_result['job_id'],
                'stage': sample_preview_result['stage'],
                'rooms': sample_preview_result['rooms'],
                'processing_time_seconds': sample_preview_result['processing_time_seconds'],
                'timestamp': sample_preview_result['timestamp']
            }
        }
        
        result = preview_service.get_cached_preview(blueprint_hash, model_version)
        
        assert result is not None
        assert result['job_id'] == sample_preview_result['job_id']
        assert result['stage'] == 'preview'
        assert len(result['rooms']) == 1
        
        # Verify DynamoDB was called correctly
        mock_aws_services['table'].get_item.assert_called_once()
        call_args = mock_aws_services['table'].get_item.call_args
        assert call_args[1]['Key']['blueprint_hash'] == cache_key
    
    def test_get_cached_preview_not_found(self, preview_service, mock_aws_services):
        """Test cache miss."""
        mock_aws_services['table'].get_item.return_value = {}
        
        result = preview_service.get_cached_preview('abc123', '1.0.0')
        
        assert result is None
    
    def test_get_cached_preview_service_unavailable(self, preview_service, mock_aws_services):
        """Test handling of service unavailable error."""
        error = ClientError(
            {'Error': {'Code': 'ServiceUnavailable'}},
            'GetItem'
        )
        mock_aws_services['table'].get_item.side_effect = error
        
        # Should return None gracefully
        result = preview_service.get_cached_preview('abc123', '1.0.0')
        assert result is None


class TestStorePreviewCache:
    """Test store_preview_cache method."""
    
    def test_store_preview_cache_success(self, preview_service, mock_aws_services, sample_preview_result):
        """Test successful cache storage."""
        blueprint_hash = 'abc123'
        model_version = '1.0.0'
        
        preview_service.store_preview_cache(blueprint_hash, sample_preview_result, model_version)
        
        # Verify DynamoDB put_item was called
        mock_aws_services['table'].put_item.assert_called_once()
        call_args = mock_aws_services['table'].put_item.call_args
        item = call_args[1]['Item']
        
        assert item['blueprint_hash'] == f"preview:{blueprint_hash}:{model_version}"
        assert item['job_id'] == sample_preview_result['job_id']
        assert item['stage'] == 'preview'
        assert item['rooms'] == sample_preview_result['rooms']
        assert 'expires_at' in item
        assert item['expires_at'] > int(datetime.now(timezone.utc).timestamp())
    
    def test_store_preview_cache_service_unavailable(self, preview_service, mock_aws_services, sample_preview_result):
        """Test handling of service unavailable error."""
        error = ClientError(
            {'Error': {'Code': 'ServiceUnavailable'}},
            'PutItem'
        )
        mock_aws_services['table'].put_item.side_effect = error
        
        # Should not raise exception (graceful degradation)
        preview_service.store_preview_cache('abc123', sample_preview_result, '1.0.0')


class TestStoreTextractResults:
    """Test store_textract_results method."""
    
    def test_store_textract_results_success(self, preview_service, mock_aws_services):
        """Test successful Textract results storage."""
        job_id = 'job_123'
        textract_result = {
            'text_blocks': [{'id': '1', 'text': 'Room'}],
            'layout_blocks': [{'id': '2', 'blockType': 'TABLE'}],
            'metadata': {'pages': 1}
        }
        
        preview_service.store_textract_results(job_id, textract_result)
        
        # Verify S3 put_object was called
        mock_aws_services['s3'].put_object.assert_called_once()
        call_args = mock_aws_services['s3'].put_object.call_args
        
        assert call_args[1]['Bucket'] == 'test-cache'
        assert call_args[1]['Key'] == f"cache/textract/{job_id}/analysis.json"
        assert call_args[1]['ContentType'] == 'application/json'
        
        # Verify stored content includes job_id and stored_at
        import json
        stored_content = json.loads(call_args[1]['Body'])
        assert stored_content['job_id'] == job_id
        assert 'stored_at' in stored_content
        assert stored_content['text_blocks'] == textract_result['text_blocks']
    
    def test_store_textract_results_service_unavailable(self, preview_service, mock_aws_services):
        """Test handling of service unavailable error."""
        error = ClientError(
            {'Error': {'Code': 'ServiceUnavailable'}},
            'PutObject'
        )
        mock_aws_services['s3'].put_object.side_effect = error
        
        # Should return empty string (graceful degradation)
        result = preview_service.store_textract_results('job_123', {})
        assert result == ''


class TestGetTextractResults:
    """Test get_textract_results method."""
    
    def test_get_textract_results_success(self, preview_service, mock_aws_services):
        """Test successful Textract results retrieval."""
        job_id = 'job_123'
        textract_result = {
            'job_id': job_id,
            'text_blocks': [{'id': '1', 'text': 'Room'}],
            'layout_blocks': [{'id': '2', 'blockType': 'TABLE'}],
            'metadata': {'pages': 1},
            'stored_at': datetime.now(timezone.utc).isoformat()
        }
        
        import json
        mock_aws_services['s3'].get_object.return_value = {
            'Body': MagicMock(read=lambda: json.dumps(textract_result).encode('utf-8'))
        }
        
        result = preview_service.get_textract_results(job_id)
        
        assert result is not None
        assert result['job_id'] == job_id
        assert 'text_blocks' in result
        assert 'layout_blocks' in result
    
    def test_get_textract_results_not_found(self, preview_service, mock_aws_services):
        """Test retrieval when results not found."""
        error = ClientError(
            {'Error': {'Code': 'NoSuchKey'}},
            'GetObject'
        )
        mock_aws_services['s3'].get_object.side_effect = error
        
        result = preview_service.get_textract_results('job_123')
        assert result is None
    
    def test_get_textract_results_service_unavailable(self, preview_service, mock_aws_services):
        """Test handling of service unavailable error."""
        error = ClientError(
            {'Error': {'Code': 'ServiceUnavailable'}},
            'GetObject'
        )
        mock_aws_services['s3'].get_object.side_effect = error
        
        # Should return None gracefully
        result = preview_service.get_textract_results('job_123')
        assert result is None

