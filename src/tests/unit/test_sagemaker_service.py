"""
Unit tests for SageMakerService.
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

from src.services.sagemaker_service import SageMakerService
from src.utils.errors import ServiceUnavailableError, LocationDetectionError


@pytest.fixture
def mock_sagemaker_runtime_client():
    """Mock SageMaker Runtime client."""
    with patch('src.services.sagemaker_service.boto3') as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        yield mock_client


@pytest.fixture
def sagemaker_service(mock_sagemaker_runtime_client):
    """Create SageMakerService instance with mocked client."""
    return SageMakerService()


@pytest.fixture
def sample_textract_result():
    """Sample Textract analysis result."""
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
def sample_model_response():
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


class TestInvokeEndpoint:
    """Test invoke_endpoint method."""
    
    def test_invoke_endpoint_success(self, sagemaker_service, mock_sagemaker_runtime_client, sample_model_response):
        """Test successful endpoint invocation."""
        # Mock response
        mock_response = {
            'Body': MagicMock()
        }
        mock_response['Body'].read.return_value = json.dumps(sample_model_response).encode('utf-8')
        mock_sagemaker_runtime_client.invoke_endpoint.return_value = mock_response
        
        input_data = {'text_blocks': [], 'layout_blocks': []}
        result = sagemaker_service.invoke_endpoint('test-endpoint', input_data)
        
        assert 'detections' in result
        assert len(result['detections']) == 2
        
        # Verify SageMaker was called correctly
        mock_sagemaker_runtime_client.invoke_endpoint.assert_called_once()
        call_args = mock_sagemaker_runtime_client.invoke_endpoint.call_args
        assert call_args[1]['EndpointName'] == 'test-endpoint'
        assert call_args[1]['ContentType'] == 'application/json'
        assert isinstance(call_args[1]['Body'], bytes)
    
    def test_invoke_endpoint_service_unavailable(self, sagemaker_service, mock_sagemaker_runtime_client):
        """Test handling of service unavailable error."""
        error = ClientError(
            {'Error': {'Code': 'ServiceUnavailable'}},
            'InvokeEndpoint'
        )
        mock_sagemaker_runtime_client.invoke_endpoint.side_effect = error
        
        input_data = {'text_blocks': [], 'layout_blocks': []}
        with pytest.raises(ServiceUnavailableError):
            sagemaker_service.invoke_endpoint('test-endpoint', input_data)
    
    def test_invoke_endpoint_throttling(self, sagemaker_service, mock_sagemaker_runtime_client):
        """Test handling of throttling error."""
        error = ClientError(
            {'Error': {'Code': 'Throttling'}},
            'InvokeEndpoint'
        )
        mock_sagemaker_runtime_client.invoke_endpoint.side_effect = error
        
        input_data = {'text_blocks': [], 'layout_blocks': []}
        # Should retry and eventually raise ServiceUnavailableError
        with pytest.raises(ServiceUnavailableError):
            sagemaker_service.invoke_endpoint('test-endpoint', input_data)
    
    def test_invoke_endpoint_model_error(self, sagemaker_service, mock_sagemaker_runtime_client):
        """Test handling of model error."""
        error = ClientError(
            {'Error': {'Code': 'ModelError', 'Message': 'Model inference failed'}},
            'InvokeEndpoint'
        )
        mock_sagemaker_runtime_client.invoke_endpoint.side_effect = error
        
        input_data = {'text_blocks': [], 'layout_blocks': []}
        with pytest.raises(LocationDetectionError) as exc_info:
            sagemaker_service.invoke_endpoint('test-endpoint', input_data)
        
        assert exc_info.value.code == 'SAGEMAKER_MODEL_ERROR'
        assert exc_info.value.status_code == 500
    
    def test_invoke_endpoint_validation_error(self, sagemaker_service, mock_sagemaker_runtime_client):
        """Test handling of validation error."""
        error = ClientError(
            {'Error': {'Code': 'ValidationError', 'Message': 'Invalid input format'}},
            'InvokeEndpoint'
        )
        mock_sagemaker_runtime_client.invoke_endpoint.side_effect = error
        
        input_data = {'text_blocks': [], 'layout_blocks': []}
        with pytest.raises(LocationDetectionError) as exc_info:
            sagemaker_service.invoke_endpoint('test-endpoint', input_data)
        
        assert exc_info.value.code == 'SAGEMAKER_MODEL_ERROR'
        assert exc_info.value.status_code == 500
    
    def test_invoke_endpoint_other_error(self, sagemaker_service, mock_sagemaker_runtime_client):
        """Test handling of other errors."""
        error = ClientError(
            {'Error': {'Code': 'InternalError', 'Message': 'Internal server error'}},
            'InvokeEndpoint'
        )
        mock_sagemaker_runtime_client.invoke_endpoint.side_effect = error
        
        input_data = {'text_blocks': [], 'layout_blocks': []}
        with pytest.raises(LocationDetectionError) as exc_info:
            sagemaker_service.invoke_endpoint('test-endpoint', input_data)
        
        assert exc_info.value.code == 'SAGEMAKER_INVOCATION_FAILED'
        assert exc_info.value.status_code == 500
    
    def test_invoke_endpoint_with_model_version(self, sagemaker_service, mock_sagemaker_runtime_client, sample_model_response):
        """Test endpoint invocation with custom model version."""
        mock_response = {
            'Body': MagicMock()
        }
        mock_response['Body'].read.return_value = json.dumps(sample_model_response).encode('utf-8')
        mock_sagemaker_runtime_client.invoke_endpoint.return_value = mock_response
        
        input_data = {'text_blocks': [], 'layout_blocks': []}
        result = sagemaker_service.invoke_endpoint('test-endpoint', input_data, model_version='2.0.0')
        
        assert 'detections' in result
        # Verify model version is logged (not directly used in API call, but tracked)


class TestPreprocessInput:
    """Test preprocess_input method."""
    
    def test_preprocess_input_success(self, sagemaker_service, sample_textract_result):
        """Test successful input preprocessing."""
        result = sagemaker_service.preprocess_input(sample_textract_result)
        
        assert 'text_blocks' in result
        assert 'layout_blocks' in result
        assert 'metadata' in result
        assert len(result['text_blocks']) == 1
        assert len(result['layout_blocks']) == 1
        assert result['metadata']['pages'] == 1
    
    def test_preprocess_input_with_image_data(self, sagemaker_service, sample_textract_result):
        """Test input preprocessing with image data."""
        image_data = b'fake_image_data'
        result = sagemaker_service.preprocess_input(sample_textract_result, blueprint_image_data=image_data)
        
        assert 'image_data' in result
        assert 'image_metadata' in result
        assert result['image_metadata']['original_size'] == len(image_data)
    
    def test_preprocess_input_empty_textract_result(self, sagemaker_service):
        """Test input preprocessing with empty Textract result."""
        empty_result = {
            'text_blocks': [],
            'layout_blocks': [],
            'metadata': {}
        }
        result = sagemaker_service.preprocess_input(empty_result)
        
        assert 'text_blocks' in result
        assert 'layout_blocks' in result
        assert len(result['text_blocks']) == 0
        assert len(result['layout_blocks']) == 0
    
    def test_preprocess_input_validation(self, sagemaker_service):
        """Test input validation in preprocessing."""
        from src.utils.errors import LocationDetectionError
        
        # Test invalid Textract result (not a dict)
        with pytest.raises(LocationDetectionError) as exc_info:
            sagemaker_service.preprocess_input("not a dict")
        
        assert exc_info.value.code == 'INVALID_INPUT'
        
        # Test invalid image data (not bytes)
        with pytest.raises(LocationDetectionError) as exc_info:
            sagemaker_service.preprocess_input(
                {'text_blocks': [], 'layout_blocks': []},
                blueprint_image_data="not bytes"
            )
        
        assert exc_info.value.code == 'INVALID_INPUT'
        
        # Test empty image data
        with pytest.raises(LocationDetectionError) as exc_info:
            sagemaker_service.preprocess_input(
                {'text_blocks': [], 'layout_blocks': []},
                blueprint_image_data=b''
            )
        
        assert exc_info.value.code == 'INVALID_INPUT'


class TestPostprocessOutput:
    """Test postprocess_output method."""
    
    def test_postprocess_output_mvp_format(self, sagemaker_service, sample_model_response):
        """Test output post-processing with MVP format (bounding boxes)."""
        result = sagemaker_service.postprocess_output(sample_model_response, output_format='mvp')
        
        assert 'rooms' in result
        assert 'detection_count' in result
        assert 'output_format' in result
        assert result['output_format'] == 'mvp'
        assert len(result['rooms']) == 2
        
        # Check first room
        room1 = result['rooms'][0]
        assert room1['id'] == 'room_001'
        assert 'bounding_box' in room1
        assert 'polygon' in room1
        assert len(room1['bounding_box']) == 4
        assert len(room1['polygon']) == 4
        assert room1['confidence'] == 0.92
        assert room1['name_hint'] == 'Kitchen'
    
    def test_postprocess_output_growth_format(self, sagemaker_service, sample_model_response):
        """Test output post-processing with Growth format (precise vertices)."""
        result = sagemaker_service.postprocess_output(sample_model_response, output_format='growth')
        
        assert 'rooms' in result
        assert 'detection_count' in result
        assert 'output_format' in result
        assert result['output_format'] == 'growth'
        assert len(result['rooms']) == 2
        
        # Check first room (should use vertices)
        room1 = result['rooms'][0]
        assert room1['id'] == 'room_001'
        assert 'bounding_box' in room1
        assert 'polygon' in room1
        assert len(room1['polygon']) == 4  # Should use vertices from model response
        assert room1['confidence'] == 0.92
    
    def test_postprocess_output_growth_fallback_to_bbox(self, sagemaker_service):
        """Test Growth format falls back to bounding box if vertices not available."""
        model_response = {
            'detections': [
                {
                    'bbox': [50, 50, 200, 300],
                    'confidence': 0.92,
                    'name_hint': 'Kitchen'
                    # No vertices field
                }
            ]
        }
        
        result = sagemaker_service.postprocess_output(model_response, output_format='growth')
        
        assert len(result['rooms']) == 1
        room = result['rooms'][0]
        # Should fallback to bounding box polygon
        assert len(room['polygon']) == 4
        assert room['polygon'][0] == [50, 50]
    
    def test_postprocess_output_empty_detections(self, sagemaker_service):
        """Test output post-processing with empty detections."""
        model_response = {'detections': []}
        
        result = sagemaker_service.postprocess_output(model_response, output_format='mvp')
        
        assert 'rooms' in result
        assert len(result['rooms']) == 0
        assert result['detection_count'] == 0
    
    def test_postprocess_output_invalid_bbox(self, sagemaker_service):
        """Test output post-processing with invalid bounding box."""
        model_response = {
            'detections': [
                {
                    'bbox': [50, 50],  # Too few values
                    'confidence': 0.92,
                    'name_hint': 'Kitchen'
                }
            ]
        }
        
        result = sagemaker_service.postprocess_output(model_response, output_format='mvp')
        
        # Should skip invalid detections
        assert len(result['rooms']) == 0
    
    def test_postprocess_output_confidence_filtering(self, sagemaker_service, sample_model_response):
        """Test confidence threshold filtering."""
        # Add a low confidence detection
        sample_model_response['detections'].append({
            'bbox': [500, 500, 600, 600],
            'confidence': 0.5,  # Below threshold
            'name_hint': 'Low Confidence Room'
        })
        
        result = sagemaker_service.postprocess_output(
            sample_model_response,
            output_format='mvp',
            confidence_threshold=0.7
        )
        
        # Should filter out low confidence detection
        assert len(result['rooms']) == 2  # Only the two high confidence rooms
        assert all(room['confidence'] >= 0.7 for room in result['rooms'])
        assert result['filtered_count'] >= 1
    
    def test_postprocess_output_boundary_validation(self, sagemaker_service):
        """Test boundary validation against image constraints."""
        model_response = {
            'detections': [
                {
                    'bbox': [50, 50, 200, 300],
                    'confidence': 0.92,
                    'name_hint': 'Valid Room'
                },
                {
                    'bbox': [-10, 50, 200, 300],  # Out of bounds (negative x)
                    'confidence': 0.88,
                    'name_hint': 'Invalid Room'
                },
                {
                    'bbox': [50, 50, 1100, 300],  # Out of bounds (x_max > width)
                    'confidence': 0.85,
                    'name_hint': 'Invalid Room 2'
                }
            ]
        }
        
        result = sagemaker_service.postprocess_output(
            model_response,
            output_format='mvp',
            image_width=1000,
            image_height=1000
        )
        
        # Should only include valid room
        assert len(result['rooms']) == 1
        assert result['rooms'][0]['name_hint'] == 'Valid Room'
    
    def test_postprocess_output_overlap_filtering(self, sagemaker_service):
        """Test overlap filtering."""
        model_response = {
            'detections': [
                {
                    'bbox': [50, 50, 200, 300],
                    'confidence': 0.95,  # Higher confidence
                    'name_hint': 'Room 1'
                },
                {
                    'bbox': [60, 60, 210, 310],  # Overlapping with Room 1 (IoU > 0.5)
                    'confidence': 0.80,  # Lower confidence
                    'name_hint': 'Room 2'
                },
                {
                    'bbox': [300, 300, 500, 500],  # Not overlapping
                    'confidence': 0.88,
                    'name_hint': 'Room 3'
                }
            ]
        }
        
        result = sagemaker_service.postprocess_output(
            model_response,
            output_format='mvp',
            filter_overlaps=True
        )
        
        # Should filter out overlapping room (Room 2), keep Room 1 and Room 3
        assert len(result['rooms']) == 2
        room_names = [room['name_hint'] for room in result['rooms']]
        assert 'Room 1' in room_names
        assert 'Room 3' in room_names
        assert 'Room 2' not in room_names
    
    def test_postprocess_output_invalid_coordinates(self, sagemaker_service):
        """Test validation of invalid bounding box coordinates."""
        model_response = {
            'detections': [
                {
                    'bbox': [200, 50, 50, 300],  # x_min > x_max (invalid)
                    'confidence': 0.92,
                    'name_hint': 'Invalid Room'
                },
                {
                    'bbox': [50, 300, 200, 50],  # y_min > y_max (invalid)
                    'confidence': 0.88,
                    'name_hint': 'Invalid Room 2'
                }
            ]
        }
        
        result = sagemaker_service.postprocess_output(model_response, output_format='mvp')
        
        # Should skip invalid detections
        assert len(result['rooms']) == 0
    
    def test_postprocess_output_vertices_validation(self, sagemaker_service):
        """Test vertices validation for Growth format."""
        model_response = {
            'detections': [
                {
                    'bbox': [50, 50, 200, 300],
                    'confidence': 0.92,
                    'name_hint': 'Valid Room',
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
                    'name_hint': 'Invalid Room',
                    'vertices': [
                        [-10, 100],  # Out of bounds
                        [400, 100],
                        [400, 350],
                        [250, 350]
                    ]
                }
            ]
        }
        
        result = sagemaker_service.postprocess_output(
            model_response,
            output_format='growth',
            image_width=1000,
            image_height=1000
        )
        
        # Should filter out invalid vertices, fallback to bounding box for invalid one
        assert len(result['rooms']) == 2
        # First room should have vertices
        assert len(result['rooms'][0]['polygon']) == 4
        # Second room should fallback to bounding box polygon
        assert len(result['rooms'][1]['polygon']) == 4

