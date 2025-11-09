"""
Unit tests for TextractService.
"""
import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

from src.services.textract_service import TextractService
from src.utils.errors import ServiceUnavailableError, LocationDetectionError


@pytest.fixture
def mock_textract_client():
    """Mock Textract client."""
    with patch('src.services.textract_service.boto3') as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        yield mock_client


@pytest.fixture
def textract_service(mock_textract_client):
    """Create TextractService instance with mocked client."""
    return TextractService()


@pytest.fixture
def sample_textract_response():
    """Sample Textract AnalyzeDocument response."""
    return {
        'Blocks': [
            {
                'Id': 'block-1',
                'BlockType': 'PAGE',
                'Geometry': {
                    'BoundingBox': {
                        'Left': 0.0,
                        'Top': 0.0,
                        'Width': 1.0,
                        'Height': 1.0
                    }
                }
            },
            {
                'Id': 'block-2',
                'BlockType': 'LINE',
                'Text': 'Room 101',
                'Geometry': {
                    'BoundingBox': {
                        'Left': 0.1,
                        'Top': 0.2,
                        'Width': 0.3,
                        'Height': 0.05
                    }
                }
            },
            {
                'Id': 'block-3',
                'BlockType': 'WORD',
                'Text': 'Kitchen',
                'Geometry': {
                    'BoundingBox': {
                        'Left': 0.5,
                        'Top': 0.3,
                        'Width': 0.1,
                        'Height': 0.03
                    }
                }
            },
            {
                'Id': 'block-4',
                'BlockType': 'TABLE',
                'Geometry': {
                    'BoundingBox': {
                        'Left': 0.2,
                        'Top': 0.4,
                        'Width': 0.4,
                        'Height': 0.3
                    }
                }
            }
        ],
        'DocumentMetadata': {
            'Pages': 1
        },
        'ResponseMetadata': {
            'HTTPHeaders': {
                'date': '2024-01-15T10:30:00Z'
            }
        }
    }


class TestAnalyzeDocument:
    """Test analyze_document method."""
    
    def test_analyze_document_success(self, textract_service, mock_textract_client, sample_textract_response):
        """Test successful document analysis."""
        mock_textract_client.analyze_document.return_value = sample_textract_response
        
        result = textract_service.analyze_document('test-bucket', 'test-key.pdf')
        
        assert 'text_blocks' in result
        assert 'layout_blocks' in result
        assert 'metadata' in result
        assert len(result['text_blocks']) == 2  # LINE and WORD blocks
        assert len(result['layout_blocks']) == 2  # PAGE and TABLE blocks
        assert result['metadata']['pages'] == 1
        
        # Verify Textract was called correctly
        mock_textract_client.analyze_document.assert_called_once()
        call_args = mock_textract_client.analyze_document.call_args
        assert call_args[1]['Document']['S3Object']['Bucket'] == 'test-bucket'
        assert call_args[1]['Document']['S3Object']['Key'] == 'test-key.pdf'
        assert 'TABLES' in call_args[1]['FeatureTypes']
        assert 'FORMS' in call_args[1]['FeatureTypes']
    
    def test_analyze_document_service_unavailable(self, textract_service, mock_textract_client):
        """Test handling of service unavailable error."""
        error = ClientError(
            {'Error': {'Code': 'ServiceUnavailable'}},
            'AnalyzeDocument'
        )
        mock_textract_client.analyze_document.side_effect = error
        
        with pytest.raises(ServiceUnavailableError):
            textract_service.analyze_document('test-bucket', 'test-key.pdf')
    
    def test_analyze_document_throttling(self, textract_service, mock_textract_client):
        """Test handling of throttling error."""
        error = ClientError(
            {'Error': {'Code': 'Throttling'}},
            'AnalyzeDocument'
        )
        mock_textract_client.analyze_document.side_effect = error
        
        # Should retry and eventually raise ServiceUnavailableError
        with pytest.raises(ServiceUnavailableError):
            textract_service.analyze_document('test-bucket', 'test-key.pdf')
    
    def test_analyze_document_other_error(self, textract_service, mock_textract_client):
        """Test handling of other errors."""
        error = ClientError(
            {'Error': {'Code': 'InvalidParameterException', 'Message': 'Invalid document'}},
            'AnalyzeDocument'
        )
        mock_textract_client.analyze_document.side_effect = error
        
        with pytest.raises(LocationDetectionError) as exc_info:
            textract_service.analyze_document('test-bucket', 'test-key.pdf')
        
        assert exc_info.value.code == 'TEXTRACT_ANALYSIS_FAILED'
        assert exc_info.value.status_code == 500
    
    def test_analyze_document_extracts_text_blocks(self, textract_service, mock_textract_client, sample_textract_response):
        """Test that text blocks are extracted correctly."""
        mock_textract_client.analyze_document.return_value = sample_textract_response
        
        result = textract_service.analyze_document('test-bucket', 'test-key.pdf')
        
        # Should extract LINE and WORD blocks as text blocks
        text_blocks = result['text_blocks']
        assert len(text_blocks) == 2
        
        # Check first text block (LINE)
        assert text_blocks[0]['id'] == 'block-2'
        assert text_blocks[0]['text'] == 'Room 101'
        assert 'geometry' in text_blocks[0]
    
    def test_analyze_document_extracts_layout_blocks(self, textract_service, mock_textract_client, sample_textract_response):
        """Test that layout blocks are extracted correctly."""
        mock_textract_client.analyze_document.return_value = sample_textract_response
        
        result = textract_service.analyze_document('test-bucket', 'test-key.pdf')
        
        # Should extract PAGE and TABLE blocks as layout blocks
        layout_blocks = result['layout_blocks']
        assert len(layout_blocks) == 2
        
        # Check layout blocks
        block_types = [b['blockType'] for b in layout_blocks]
        assert 'PAGE' in block_types
        assert 'TABLE' in block_types

