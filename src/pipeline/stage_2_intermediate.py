"""
Intermediate pipeline Lambda handler for Stage 2 intermediate processing.

This module provides the Lambda handler for the intermediate pipeline stage,
which processes blueprints using SageMaker for refined room detection.
"""
import json
import os
import time
from typing import Dict, Any
from datetime import datetime, timezone

# Handle imports for both Lambda (src/ directory) and local testing (project root)
try:
    from services.job_service import JobService
    from services.sagemaker_service import SageMakerService
    from services.preview_service import PreviewService
    from services.websocket_service import WebSocketService
    from utils.errors import JobNotFoundError, LocationDetectionError, ServiceUnavailableError
    from utils.logging import get_logger
except ImportError:
    # Fallback for local testing from project root
    from src.services.job_service import JobService
    from src.services.sagemaker_service import SageMakerService
    from src.services.preview_service import PreviewService
    from src.services.websocket_service import WebSocketService
    from src.utils.errors import JobNotFoundError, LocationDetectionError, ServiceUnavailableError
    from src.utils.logging import get_logger


logger = get_logger(__name__)

# Model version for intermediate pipeline
MODEL_VERSION = '1.0.0'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for intermediate pipeline stage.
    
    Processes blueprint using SageMaker for refined room detection.
    
    Args:
        event: Lambda event with job_id and optional stage context
        context: Lambda context object
        
    Returns:
        Intermediate result dictionary with rooms and timing metrics
    """
    start_time = time.time()
    request_id = context.aws_request_id if context else None
    logger.set_request_id(request_id)
    
    try:
        # Extract job_id from event
        job_id = event.get('job_id')
        if not job_id:
            raise LocationDetectionError(
                code='INVALID_REQUEST',
                message='job_id is required',
                details={'event': event},
                status_code=400
            )
        
        logger.set_job_id(job_id)
        logger.info(
            f"Starting intermediate pipeline for job: {job_id}",
            context={'job_id': job_id}
        )
        
        # Get job information
        job_service = JobService()
        job = job_service.get_job(job_id)
        
        # Load Textract results from S3 (stored in Story 3.1)
        preview_service = PreviewService()
        textract_result = preview_service.get_textract_results(job_id)
        
        if not textract_result:
            raise LocationDetectionError(
                code='TEXTRACT_RESULTS_NOT_FOUND',
                message='Textract results not found for job',
                details={'job_id': job_id},
                status_code=404
            )
        
        logger.info(
            f"Loaded Textract results for job: {job_id}",
            context={
                'job_id': job_id,
                'text_blocks_count': len(textract_result.get('text_blocks', [])),
                'layout_blocks_count': len(textract_result.get('layout_blocks', []))
            }
        )
        
        # Get SageMaker endpoint name from environment
        sagemaker_endpoint_name = os.environ.get('SAGEMAKER_INTERMEDIATE_ENDPOINT_NAME')
        if not sagemaker_endpoint_name:
            raise LocationDetectionError(
                code='CONFIGURATION_ERROR',
                message='SAGEMAKER_INTERMEDIATE_ENDPOINT_NAME environment variable is required',
                details={},
                status_code=500
            )
        
        # Preprocess input for SageMaker
        sagemaker_service = SageMakerService()
        model_input = sagemaker_service.preprocess_input(textract_result)
        
        # Invoke SageMaker endpoint for intermediate processing
        sagemaker_start_time = time.time()
        model_response = sagemaker_service.invoke_endpoint(
            endpoint_name=sagemaker_endpoint_name,
            input_data=model_input,
            model_version=MODEL_VERSION
        )
        sagemaker_time = time.time() - sagemaker_start_time
        
        # Post-process model output with confidence filtering and validation
        postprocess_start_time = time.time()
        confidence_threshold = float(os.environ.get('CONFIDENCE_THRESHOLD', '0.7'))
        detection_result = sagemaker_service.postprocess_output(
            model_response,
            output_format='mvp',  # MVP uses bounding boxes
            confidence_threshold=confidence_threshold,
            filter_overlaps=True
        )
        postprocess_time = time.time() - postprocess_start_time
        
        # Refine room boundaries based on intermediate results
        rooms = detection_result.get('rooms', [])
        
        # Calculate total processing time
        total_time = time.time() - start_time
        
        # Processing time optimization: Check if we're approaching the 30-second limit
        # If so, optimize subsequent operations
        time_remaining = 30.0 - total_time
        if time_remaining < 5.0:
            logger.warning(
                f"Processing time approaching limit: {total_time:.2f}s remaining: {time_remaining:.2f}s",
                context={
                    'job_id': job_id,
                    'total_time': total_time,
                    'time_remaining': time_remaining
                }
            )
            # Optimize: Skip non-critical operations if time is running out
            # For now, we'll just log - actual optimization would involve
            # reducing processing complexity or skipping optional steps
        
        # Build intermediate result
        intermediate_result = {
            'job_id': job_id,
            'stage': 'intermediate',
            'rooms': rooms,
            'processing_time_seconds': round(total_time, 2),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'timing_metrics': {
                'sagemaker_inference_seconds': round(sagemaker_time, 2),
                'postprocessing_seconds': round(postprocess_time, 2),
                'total_seconds': round(total_time, 2)
            }
        }
        
        # Store intermediate results in S3
        cache_bucket_name = os.environ.get('CACHE_BUCKET_NAME')
        if not cache_bucket_name:
            raise LocationDetectionError(
                code='CONFIGURATION_ERROR',
                message='CACHE_BUCKET_NAME environment variable is required',
                details={},
                status_code=500
            )
        
        s3_key = f"cache/intermediate/{job_id}/stage_2.json"
        logger.info(
            f"Storing intermediate results in S3: {s3_key}",
            context={'job_id': job_id, 's3_key': s3_key}
        )
        
        # Use PreviewService's S3 client to store results
        import boto3
        endpoint_url = os.environ.get('AWS_ENDPOINT_URL')
        s3_kwargs = {}
        if endpoint_url:
            s3_kwargs['endpoint_url'] = endpoint_url
        s3_client = boto3.client('s3', **s3_kwargs)
        
        try:
            s3_client.put_object(
                Bucket=cache_bucket_name,
                Key=s3_key,
                Body=json.dumps(intermediate_result),
                ContentType='application/json'
            )
            logger.info(
                f"Intermediate results stored successfully: {s3_key}",
                context={'job_id': job_id, 's3_key': s3_key}
            )
        except Exception as e:
            logger.error(
                f"Error storing intermediate results: {s3_key}",
                exc_info=True,
                context={'job_id': job_id, 's3_key': s3_key}
            )
            # Don't fail the pipeline if S3 storage fails, but log the error
        
        # Update job status in DynamoDB (optional - job status might be managed by Step Functions)
        # For now, we'll just log that intermediate stage completed
        
        # Send progress update via WebSocket
        websocket_service = WebSocketService()
        try:
            websocket_service.send_progress_update(
                job_id=job_id,
                stage='intermediate',
                progress=66,  # 2/3 of the way through (preview=33%, intermediate=66%, final=100%)
                message='Intermediate processing completed',
                estimated_seconds_remaining=10  # Estimate for final stage
            )
        except Exception as e:
            logger.warning(
                f"Failed to send WebSocket progress update: {str(e)}",
                context={'job_id': job_id}
            )
            # Don't fail the pipeline if WebSocket fails
        
        # Log processing time
        logger.info(
            f"Intermediate pipeline completed for job: {job_id}",
            context={
                'job_id': job_id,
                'processing_time_seconds': total_time,
                'sagemaker_time': sagemaker_time,
                'postprocessing_time': postprocess_time,
                'rooms_detected': len(rooms)
            }
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'success',
                'data': intermediate_result
            })
        }
        
    except JobNotFoundError as e:
        logger.error(
            f"Job not found: {str(e)}",
            exc_info=True
        )
        return {
            'statusCode': 404,
            'body': json.dumps({
                'status': 'error',
                'error': {
                    'code': 'JOB_NOT_FOUND',
                    'message': str(e)
                }
            })
        }
    except LocationDetectionError as e:
        logger.error(
            f"Intermediate pipeline error: {str(e)}",
            exc_info=True
        )
        return {
            'statusCode': e.status_code,
            'body': json.dumps({
                'status': 'error',
                'error': e.to_dict()
            })
        }
    except Exception as e:
        logger.error(
            f"Unexpected error in intermediate pipeline: {str(e)}",
            exc_info=True
        )
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'error',
                'error': {
                    'code': 'INTERNAL_ERROR',
                    'message': 'An internal error occurred during intermediate processing'
                }
            })
        }

