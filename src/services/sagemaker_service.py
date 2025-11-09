"""
SageMaker service for model inference.

This module provides integration with AWS SageMaker Runtime API
for invoking machine learning models for room detection.
"""
import os
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError

# Handle imports for both Lambda (src/ directory) and local testing (project root)
try:
    from utils.errors import ServiceUnavailableError, LocationDetectionError
    from utils.retry import retry_aws_call
    from utils.logging import get_logger
except ImportError:
    # Fallback for local testing from project root
    from src.utils.errors import ServiceUnavailableError, LocationDetectionError
    from src.utils.retry import retry_aws_call
    from src.utils.logging import get_logger


logger = get_logger(__name__)


class SageMakerService:
    """
    Service for invoking SageMaker model endpoints.
    
    Handles model inference using SageMaker Runtime API
    for room detection with input preprocessing and output post-processing.
    """
    
    def __init__(self, region_name: Optional[str] = None):
        """
        Initialize SageMakerService.
        
        Args:
            region_name: AWS region name (default: from env var or us-east-1)
        """
        self.region_name = region_name or os.environ.get('AWS_REGION', 'us-east-1')
        # Support LocalStack endpoint URL (Note: SageMaker not fully supported by LocalStack)
        endpoint_url = os.environ.get('AWS_ENDPOINT_URL')
        sagemaker_kwargs = {'region_name': self.region_name}
        if endpoint_url:
            sagemaker_kwargs['endpoint_url'] = endpoint_url
        self.sagemaker_runtime = boto3.client('sagemaker-runtime', **sagemaker_kwargs)
    
    def invoke_endpoint(
        self,
        endpoint_name: str,
        input_data: Dict[str, Any],
        model_version: str = '1.0.0',
        content_type: str = 'application/json'
    ) -> Dict[str, Any]:
        """
        Invoke SageMaker endpoint for room detection.
        
        Args:
            endpoint_name: Name of the SageMaker endpoint
            input_data: Preprocessed blueprint data in model format
            model_version: Model version to use (default: '1.0.0')
            content_type: Content type of input data (default: 'application/json')
            
        Returns:
            Dict containing room detection results
            
        Raises:
            ServiceUnavailableError: If SageMaker service is unavailable
            LocationDetectionError: If model invocation fails
        """
        logger.info(
            f"Invoking SageMaker endpoint: {endpoint_name}",
            context={
                'endpoint_name': endpoint_name,
                'model_version': model_version,
                'content_type': content_type
            }
        )
        
        def invoke():
            try:
                # Convert input data to JSON string
                input_body = json.dumps(input_data)
                
                response = self.sagemaker_runtime.invoke_endpoint(
                    EndpointName=endpoint_name,
                    ContentType=content_type,
                    Body=input_body.encode('utf-8')
                )
                
                # Parse response body
                response_body = response['Body'].read().decode('utf-8')
                result = json.loads(response_body)
                
                return result
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                # Handle service unavailability
                if error_code in ['ServiceUnavailable', 'Throttling', 'ThrottlingException']:
                    raise ServiceUnavailableError('SageMaker', retry_after=5)
                # Handle model errors
                if error_code in ['ModelError', 'ValidationError']:
                    raise LocationDetectionError(
                        code='SAGEMAKER_MODEL_ERROR',
                        message=f"Model error: {e.response.get('Error', {}).get('Message', str(e))}",
                        details={'endpoint_name': endpoint_name, 'error_code': error_code},
                        status_code=500
                    )
                # Re-raise other errors
                raise
        
        try:
            result = retry_aws_call(invoke)
            
            logger.info(
                f"SageMaker endpoint invocation completed: {endpoint_name}",
                context={
                    'endpoint_name': endpoint_name,
                    'model_version': model_version,
                    'result_keys': list(result.keys()) if isinstance(result, dict) else []
                }
            )
            
            return result
            
        except ServiceUnavailableError:
            logger.error(
                f"SageMaker service unavailable for endpoint: {endpoint_name}",
                exc_info=True,
                context={'endpoint_name': endpoint_name, 'service': 'SageMaker'}
            )
            raise
        except LocationDetectionError:
            # Re-raise LocationDetectionError as-is
            raise
        except Exception as e:
            logger.error(
                f"SageMaker endpoint invocation failed: {endpoint_name}",
                exc_info=True,
                context={'endpoint_name': endpoint_name}
            )
            raise LocationDetectionError(
                code='SAGEMAKER_INVOCATION_FAILED',
                message=f"Failed to invoke SageMaker endpoint: {str(e)}",
                details={'endpoint_name': endpoint_name},
                status_code=500
            )
    
    def preprocess_input(
        self,
        textract_result: Dict[str, Any],
        blueprint_image_data: Optional[bytes] = None,
        image_format: Optional[str] = None,
        target_width: Optional[int] = None,
        target_height: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Preprocess input data for model format.
        
        This method converts Textract results and blueprint image data
        into the format expected by the SageMaker model.
        
        Args:
            textract_result: Textract analysis result with text_blocks and layout_blocks
            blueprint_image_data: Optional blueprint image bytes (for image preprocessing)
            image_format: Image format (png, jpg, pdf) for preprocessing
            target_width: Target width for image resize (default: None, no resize)
            target_height: Target height for image resize (default: None, no resize)
            
        Returns:
            Preprocessed input data in model format
            
        Raises:
            LocationDetectionError: If input validation fails
        """
        # Validate Textract result structure first
        if not isinstance(textract_result, dict):
            raise LocationDetectionError(
                code='INVALID_INPUT',
                message='Textract result must be a dictionary',
                details={'type': type(textract_result).__name__},
                status_code=400
            )
        
        logger.info(
            "Preprocessing input data for SageMaker model",
            context={
                'text_blocks_count': len(textract_result.get('text_blocks', [])),
                'layout_blocks_count': len(textract_result.get('layout_blocks', [])),
                'has_image_data': blueprint_image_data is not None
            }
        )
        
        # Extract text blocks and layout blocks
        text_blocks = textract_result.get('text_blocks', [])
        layout_blocks = textract_result.get('layout_blocks', [])
        
        # Validate text blocks and layout blocks are lists
        if not isinstance(text_blocks, list):
            raise LocationDetectionError(
                code='INVALID_INPUT',
                message='text_blocks must be a list',
                details={'type': type(text_blocks).__name__},
                status_code=400
            )
        
        if not isinstance(layout_blocks, list):
            raise LocationDetectionError(
                code='INVALID_INPUT',
                message='layout_blocks must be a list',
                details={'type': type(layout_blocks).__name__},
                status_code=400
            )
        
        # Convert to model input format
        model_input = {
            'text_blocks': text_blocks,
            'layout_blocks': layout_blocks,
            'metadata': textract_result.get('metadata', {})
        }
        
        # If blueprint image data is provided, preprocess it
        if blueprint_image_data is not None:
            # Validate image data
            if not isinstance(blueprint_image_data, bytes):
                raise LocationDetectionError(
                    code='INVALID_INPUT',
                    message='blueprint_image_data must be bytes',
                    details={'type': type(blueprint_image_data).__name__},
                    status_code=400
                )
            
            if len(blueprint_image_data) == 0:
                raise LocationDetectionError(
                    code='INVALID_INPUT',
                    message='blueprint_image_data cannot be empty',
                    details={},
                    status_code=400
                )
            
            # Preprocess image (resize, normalize, format conversion)
            preprocessed_image = self._preprocess_image(
                blueprint_image_data,
                image_format=image_format,
                target_width=target_width,
                target_height=target_height
            )
            
            # Add preprocessed image to model input
            model_input['image_data'] = preprocessed_image
            model_input['image_metadata'] = {
                'original_size': len(blueprint_image_data),
                'preprocessed_size': len(preprocessed_image) if isinstance(preprocessed_image, bytes) else 0,
                'format': image_format,
                'target_width': target_width,
                'target_height': target_height
            }
        
        logger.info(
            "Input preprocessing completed",
            context={
                'text_blocks_count': len(text_blocks),
                'layout_blocks_count': len(layout_blocks),
                'has_image_data': blueprint_image_data is not None
            }
        )
        
        return model_input
    
    def _preprocess_image(
        self,
        image_data: bytes,
        image_format: Optional[str] = None,
        target_width: Optional[int] = None,
        target_height: Optional[int] = None
    ) -> bytes:
        """
        Preprocess blueprint image for model input.
        
        Performs resize, normalization, and format conversion as needed.
        
        Args:
            image_data: Raw image bytes
            image_format: Image format (png, jpg, pdf)
            target_width: Target width for resize (default: None, no resize)
            target_height: Target height for resize (default: None, no resize)
            
        Returns:
            Preprocessed image bytes
        """
        try:
            # Try to import PIL/Pillow for image processing
            try:
                from PIL import Image
                import io
                has_pil = True
            except ImportError:
                has_pil = False
                logger.warning(
                    "PIL/Pillow not available, skipping image preprocessing",
                    context={'image_format': image_format}
                )
            
            if not has_pil:
                # If PIL not available, return original image data
                # In production, PIL should be in requirements
                return image_data
            
            # Load image from bytes
            image = Image.open(io.BytesIO(image_data))
            
            # Get original dimensions
            original_width, original_height = image.size
            
            # Resize if target dimensions provided
            if target_width is not None and target_height is not None:
                # Resize maintaining aspect ratio if needed
                # For now, resize to exact dimensions (can be enhanced)
                image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
                logger.debug(
                    f"Resized image from {original_width}x{original_height} to {target_width}x{target_height}",
                    context={
                        'original_width': original_width,
                        'original_height': original_height,
                        'target_width': target_width,
                        'target_height': target_height
                    }
                )
            
            # Normalize image (convert to RGB if needed)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Convert to bytes
            output = io.BytesIO()
            
            # Save in appropriate format
            if image_format == 'png':
                image.save(output, format='PNG')
            elif image_format == 'jpg' or image_format == 'jpeg':
                image.save(output, format='JPEG', quality=95)
            else:
                # Default to PNG
                image.save(output, format='PNG')
            
            preprocessed_bytes = output.getvalue()
            
            logger.info(
                "Image preprocessing completed",
                context={
                    'original_size': len(image_data),
                    'preprocessed_size': len(preprocessed_bytes),
                    'format': image_format,
                    'dimensions': image.size
                }
            )
            
            return preprocessed_bytes
            
        except Exception as e:
            logger.warning(
                f"Image preprocessing failed, using original image: {str(e)}",
                context={'image_format': image_format}
            )
            # Return original image data if preprocessing fails
            return image_data
    
    def postprocess_output(
        self,
        model_response: Dict[str, Any],
        output_format: str = 'mvp',  # 'mvp' for bounding boxes, 'growth' for precise vertices
        confidence_threshold: float = 0.7,
        image_width: Optional[int] = None,
        image_height: Optional[int] = None,
        filter_overlaps: bool = True
    ) -> Dict[str, Any]:
        """
        Post-process model output to extract room detection results.
        
        This method parses the model response and extracts room boundaries
        in the format specified by the PRD output schema, with confidence
        filtering and boundary validation.
        
        Args:
            model_response: Raw model response from SageMaker endpoint
            output_format: Output format ('mvp' for bounding boxes, 'growth' for precise vertices)
            confidence_threshold: Minimum confidence threshold for filtering (default: 0.7)
            image_width: Image width for boundary validation (default: None, no validation)
            image_height: Image height for boundary validation (default: None, no validation)
            filter_overlaps: Whether to filter overlapping boundaries (default: True)
            
        Returns:
            Post-processed room detection results matching PRD output schema
        """
        logger.info(
            "Post-processing SageMaker model output",
            context={
                'output_format': output_format,
                'confidence_threshold': confidence_threshold,
                'filter_overlaps': filter_overlaps
            }
        )
        
        # Extract room detections from model response
        # Model response format will depend on the actual model implementation
        # For now, we'll assume a standard format with detections
        rooms = []
        
        # Parse model response
        # Expected format: {'detections': [{'bbox': [...], 'confidence': 0.9, ...}, ...]}
        detections = model_response.get('detections', [])
        
        for idx, detection in enumerate(detections):
            # Extract bounding box and confidence
            bbox = detection.get('bbox', [])
            confidence = detection.get('confidence', 0.0)
            
            # Validate confidence threshold
            if confidence < confidence_threshold:
                logger.debug(
                    f"Skipping detection {idx} due to low confidence: {confidence} < {confidence_threshold}",
                    context={'detection_idx': idx, 'confidence': confidence, 'threshold': confidence_threshold}
                )
                continue
            
            # Validate bounding box format
            if not isinstance(bbox, list) or len(bbox) < 4:
                logger.warning(
                    f"Invalid bounding box format for detection {idx}: {bbox}",
                    context={'detection_idx': idx, 'bbox': bbox}
                )
                continue
            
            # Validate bounding box values are numbers
            try:
                bbox = [float(x) for x in bbox[:4]]
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid bounding box values for detection {idx}: {bbox}",
                    context={'detection_idx': idx, 'bbox': bbox}
                )
                continue
            
            # Validate bounding box coordinates (x_min < x_max, y_min < y_max)
            x_min, y_min, x_max, y_max = bbox
            if x_min >= x_max or y_min >= y_max:
                logger.warning(
                    f"Invalid bounding box coordinates for detection {idx}: {bbox}",
                    context={'detection_idx': idx, 'bbox': bbox}
                )
                continue
            
            # Validate boundaries against image constraints if provided
            if image_width is not None and image_height is not None:
                if x_min < 0 or y_min < 0 or x_max > image_width or y_max > image_height:
                    logger.warning(
                        f"Boundary out of image bounds for detection {idx}: {bbox} (image: {image_width}x{image_height})",
                        context={
                            'detection_idx': idx,
                            'bbox': bbox,
                            'image_width': image_width,
                            'image_height': image_height
                        }
                    )
                    continue
            
            # For MVP: use bounding boxes
            if output_format == 'mvp':
                room = {
                    'id': f"room_{idx + 1:03d}",
                    'bounding_box': bbox,
                    'polygon': [
                        [bbox[0], bbox[1]],  # top-left
                        [bbox[2], bbox[1]],  # top-right
                        [bbox[2], bbox[3]],  # bottom-right
                        [bbox[0], bbox[3]]   # bottom-left
                    ],
                    'name_hint': detection.get('name_hint', ''),
                    'confidence': confidence
                }
                rooms.append(room)
            
            # For Growth: use precise vertices if available
            elif output_format == 'growth':
                vertices = detection.get('vertices', [])
                if vertices and len(vertices) >= 3:
                    # Validate vertices format
                    try:
                        validated_vertices = []
                        for vertex in vertices:
                            if isinstance(vertex, (list, tuple)) and len(vertex) >= 2:
                                validated_vertices.append([float(vertex[0]), float(vertex[1])])
                            else:
                                raise ValueError(f"Invalid vertex format: {vertex}")
                        
                        # Validate vertices are within image bounds if provided
                        if image_width is not None and image_height is not None:
                            for vertex in validated_vertices:
                                if vertex[0] < 0 or vertex[0] > image_width or vertex[1] < 0 or vertex[1] > image_height:
                                    raise ValueError(f"Vertex out of bounds: {vertex}")
                        
                        room = {
                            'id': f"room_{idx + 1:03d}",
                            'bounding_box': bbox,
                            'polygon': validated_vertices,
                            'name_hint': detection.get('name_hint', ''),
                            'confidence': confidence
                        }
                        rooms.append(room)
                    except (ValueError, TypeError) as e:
                        logger.warning(
                            f"Invalid vertices for detection {idx}: {e}",
                            context={'detection_idx': idx, 'vertices': vertices}
                        )
                        # Fallback to bounding box
                        room = {
                            'id': f"room_{idx + 1:03d}",
                            'bounding_box': bbox,
                            'polygon': [
                                [bbox[0], bbox[1]],
                                [bbox[2], bbox[1]],
                                [bbox[2], bbox[3]],
                                [bbox[0], bbox[3]]
                            ],
                            'name_hint': detection.get('name_hint', ''),
                            'confidence': confidence
                        }
                        rooms.append(room)
                elif len(bbox) >= 4:
                    # Fallback to bounding box if vertices not available
                    room = {
                        'id': f"room_{idx + 1:03d}",
                        'bounding_box': bbox,
                        'polygon': [
                            [bbox[0], bbox[1]],
                            [bbox[2], bbox[1]],
                            [bbox[2], bbox[3]],
                            [bbox[0], bbox[3]]
                        ],
                        'name_hint': detection.get('name_hint', ''),
                        'confidence': confidence
                    }
                    rooms.append(room)
        
        # Filter overlapping boundaries if requested
        if filter_overlaps and len(rooms) > 1:
            rooms = self._filter_overlapping_boundaries(rooms)
        
        result = {
            'rooms': rooms,
            'detection_count': len(rooms),
            'output_format': output_format,
            'confidence_threshold': confidence_threshold,
            'filtered_count': len(detections) - len(rooms)
        }
        
        logger.info(
            "Output post-processing completed",
            context={
                'rooms_detected': len(rooms),
                'detections_total': len(detections),
                'filtered_count': len(detections) - len(rooms),
                'output_format': output_format
            }
        )
        
        return result
    
    def _filter_overlapping_boundaries(self, rooms: list) -> list:
        """
        Filter overlapping room boundaries, keeping the one with higher confidence.
        
        Args:
            rooms: List of room detection results
            
        Returns:
            Filtered list of rooms without significant overlaps
        """
        if not rooms:
            return rooms
        
        # Sort by confidence (highest first)
        sorted_rooms = sorted(rooms, key=lambda r: r.get('confidence', 0.0), reverse=True)
        filtered_rooms = []
        
        for room in sorted_rooms:
            bbox = room.get('bounding_box', [])
            if len(bbox) < 4:
                continue
            
            x_min, y_min, x_max, y_max = bbox
            room_area = (x_max - x_min) * (y_max - y_min)
            
            # Check for overlap with existing rooms
            has_significant_overlap = False
            for existing_room in filtered_rooms:
                existing_bbox = existing_room.get('bounding_box', [])
                if len(existing_bbox) < 4:
                    continue
                
                ex_min, ey_min, ex_max, ey_max = existing_bbox
                
                # Calculate intersection
                inter_x_min = max(x_min, ex_min)
                inter_y_min = max(y_min, ey_min)
                inter_x_max = min(x_max, ex_max)
                inter_y_max = min(y_max, ey_max)
                
                if inter_x_min < inter_x_max and inter_y_min < inter_y_max:
                    # Calculate intersection area
                    inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)
                    
                    # Calculate IoU (Intersection over Union)
                    existing_area = (ex_max - ex_min) * (ey_max - ey_min)
                    union_area = room_area + existing_area - inter_area
                    
                    if union_area > 0:
                        iou = inter_area / union_area
                        
                        # If IoU > 0.5, consider it a significant overlap
                        if iou > 0.5:
                            has_significant_overlap = True
                            logger.debug(
                                f"Filtering room {room.get('id')} due to overlap with {existing_room.get('id')} (IoU: {iou:.2f})",
                                context={
                                    'room_id': room.get('id'),
                                    'existing_room_id': existing_room.get('id'),
                                    'iou': iou
                                }
                            )
                            break
            
            if not has_significant_overlap:
                filtered_rooms.append(room)
        
        return filtered_rooms

