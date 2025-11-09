"""
Final pipeline Lambda handler for Stage 3 final processing.

This module provides the Lambda handler for the final pipeline stage,
which processes blueprints using SageMaker for precise room boundary detection.
"""
import json
import os
import time
from typing import Dict, Any
from datetime import datetime, timezone
import boto3

# Handle imports for both Lambda (src/ directory) and local testing (project root)
try:
    from services.job_service import JobService
    from services.sagemaker_service import SageMakerService
    from services.preview_service import PreviewService
    from services.websocket_service import WebSocketService
    from models.job import JobStatus
    from utils.errors import JobNotFoundError, LocationDetectionError, ServiceUnavailableError
    from utils.retry import retry_aws_call
    from utils.logging import get_logger
except ImportError:
    # Fallback for local testing from project root
    from src.services.job_service import JobService
    from src.services.sagemaker_service import SageMakerService
    from src.services.preview_service import PreviewService
    from src.services.websocket_service import WebSocketService
    from src.models.job import JobStatus
    from src.utils.errors import JobNotFoundError, LocationDetectionError, ServiceUnavailableError
    from src.utils.retry import retry_aws_call
    from src.utils.logging import get_logger


logger = get_logger(__name__)

# Model version for final pipeline
MODEL_VERSION = '1.0.0'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for final pipeline stage.
    
    Processes blueprint using SageMaker for precise room boundary detection.
    
    Args:
        event: Lambda event with job_id and optional stage context
        context: Lambda context object
        
    Returns:
        Final result dictionary with rooms and timing metrics
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
            f"Starting final pipeline for job: {job_id}",
            context={'job_id': job_id}
        )
        
        # Get job information
        job_service = JobService()
        job = job_service.get_job(job_id)
        
        # Load intermediate results from S3
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
            f"Loading intermediate results from S3: {s3_key}",
            context={'job_id': job_id, 's3_key': s3_key}
        )
        
        endpoint_url = os.environ.get('AWS_ENDPOINT_URL')
        s3_kwargs = {}
        if endpoint_url:
            s3_kwargs['endpoint_url'] = endpoint_url
        s3_client = boto3.client('s3', **s3_kwargs)
        
        def get_intermediate_results():
            try:
                response = s3_client.get_object(
                    Bucket=cache_bucket_name,
                    Key=s3_key
                )
                return response['Body'].read().decode('utf-8')
            except s3_client.exceptions.NoSuchKey:
                return None
            except Exception as e:
                error_code = getattr(e, 'response', {}).get('Error', {}).get('Code', '')
                if error_code in ['ServiceUnavailable', 'SlowDown']:
                    raise ServiceUnavailableError('S3', retry_after=5)
                raise
        
        try:
            intermediate_content = retry_aws_call(get_intermediate_results)
            if not intermediate_content:
                raise LocationDetectionError(
                    code='INTERMEDIATE_RESULTS_NOT_FOUND',
                    message='Intermediate results not found for job',
                    details={'job_id': job_id, 's3_key': s3_key},
                    status_code=404
                )
            
            intermediate_result = json.loads(intermediate_content)
            logger.info(
                f"Loaded intermediate results for job: {job_id}",
                context={
                    'job_id': job_id,
                    'rooms_count': len(intermediate_result.get('rooms', []))
                }
            )
        except ServiceUnavailableError:
            logger.error(
                f"S3 service unavailable, cannot load intermediate results: {s3_key}",
                exc_info=True,
                context={'job_id': job_id, 's3_key': s3_key, 'service': 'S3'}
            )
            raise
        except Exception as e:
            logger.error(
                f"Error loading intermediate results: {s3_key}",
                exc_info=True,
                context={'job_id': job_id, 's3_key': s3_key}
            )
            raise LocationDetectionError(
                code='INTERMEDIATE_RESULTS_LOAD_FAILED',
                message=f"Failed to load intermediate results: {str(e)}",
                details={'job_id': job_id, 's3_key': s3_key},
                status_code=500
            )
        
        # Load Textract results for final processing
        preview_service = PreviewService()
        textract_result = preview_service.get_textract_results(job_id)
        
        if not textract_result:
            raise LocationDetectionError(
                code='TEXTRACT_RESULTS_NOT_FOUND',
                message='Textract results not found for job',
                details={'job_id': job_id},
                status_code=404
            )
        
        # Get SageMaker endpoint name from environment
        sagemaker_endpoint_name = os.environ.get('SAGEMAKER_FINAL_ENDPOINT_NAME')
        if not sagemaker_endpoint_name:
            raise LocationDetectionError(
                code='CONFIGURATION_ERROR',
                message='SAGEMAKER_FINAL_ENDPOINT_NAME environment variable is required',
                details={},
                status_code=500
            )
        
        # Preprocess input for SageMaker (using intermediate results and Textract)
        sagemaker_service = SageMakerService()
        model_input = sagemaker_service.preprocess_input(textract_result)
        
        # Add intermediate results to model input for refinement
        model_input['intermediate_results'] = intermediate_result.get('rooms', [])
        
        # Invoke SageMaker endpoint for final processing
        sagemaker_start_time = time.time()
        model_response = sagemaker_service.invoke_endpoint(
            endpoint_name=sagemaker_endpoint_name,
            input_data=model_input,
            model_version=MODEL_VERSION
        )
        sagemaker_time = time.time() - sagemaker_start_time
        
        # Post-process model output (use Growth format for precise vertices if available, else MVP)
        # Confidence filtering and boundary validation are now handled in postprocess_output
        postprocess_start_time = time.time()
        output_format = os.environ.get('OUTPUT_FORMAT', 'mvp')  # 'mvp' or 'growth'
        confidence_threshold = float(os.environ.get('CONFIDENCE_THRESHOLD', '0.7'))
        
        # Get image dimensions from Textract metadata if available for boundary validation
        image_width = None
        image_height = None
        textract_metadata = textract_result.get('metadata', {})
        if 'image_width' in textract_metadata:
            image_width = textract_metadata.get('image_width')
        if 'image_height' in textract_metadata:
            image_height = textract_metadata.get('image_height')
        
        detection_result = sagemaker_service.postprocess_output(
            model_response,
            output_format=output_format,
            confidence_threshold=confidence_threshold,
            image_width=image_width,
            image_height=image_height,
            filter_overlaps=True
        )
        postprocess_time = time.time() - postprocess_start_time
        
        # Extract precise room boundaries (precise vertices for Growth, bounding boxes for MVP)
        # Confidence filtering and overlap detection already done in postprocess_output
        filtered_rooms = detection_result.get('rooms', [])
        
        logger.info(
            f"Post-processing completed: {len(filtered_rooms)} rooms after filtering",
            context={
                'job_id': job_id,
                'confidence_threshold': confidence_threshold,
                'rooms_detected': len(filtered_rooms),
                'filtered_count': detection_result.get('filtered_count', 0)
            }
        )
        
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
        
        # Build final result matching PRD output schema
        final_result = {
            'job_id': job_id,
            'stage': 'final',
            'rooms': filtered_rooms,
            'processing_time_seconds': round(total_time, 2),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'timing_metrics': {
                'sagemaker_inference_seconds': round(sagemaker_time, 2),
                'postprocessing_seconds': round(postprocess_time, 2),
                'total_seconds': round(total_time, 2)
            }
        }
        
        # Store final results in S3
        final_s3_key = f"cache/final/{job_id}/results.json"
        logger.info(
            f"Storing final results in S3: {final_s3_key}",
            context={'job_id': job_id, 's3_key': final_s3_key}
        )
        
        try:
            s3_client.put_object(
                Bucket=cache_bucket_name,
                Key=final_s3_key,
                Body=json.dumps(final_result),
                ContentType='application/json'
            )
            logger.info(
                f"Final results stored successfully: {final_s3_key}",
                context={'job_id': job_id, 's3_key': final_s3_key}
            )
        except Exception as e:
            logger.error(
                f"Error storing final results: {final_s3_key}",
                exc_info=True,
                context={'job_id': job_id, 's3_key': final_s3_key}
            )
            # Don't fail the pipeline if S3 storage fails, but log the error
        
        # Store final results in DynamoDB for fast retrieval
        jobs_table_name = os.environ.get('JOBS_TABLE_NAME')
        if jobs_table_name:
            try:
                dynamodb_kwargs = {}
                if endpoint_url:
                    dynamodb_kwargs['endpoint_url'] = endpoint_url
                dynamodb = boto3.resource('dynamodb', **dynamodb_kwargs)
                jobs_table = dynamodb.Table(jobs_table_name)
                
                def update_job():
                    jobs_table.update_item(
                        Key={'job_id': job_id},
                        UpdateExpression='SET #status = :status, results_s3_key = :results_s3_key, updated_at = :updated_at',
                        ExpressionAttributeNames={
                            '#status': 'status'
                        },
                        ExpressionAttributeValues={
                            ':status': JobStatus.COMPLETED.value,
                            ':results_s3_key': final_s3_key,
                            ':updated_at': datetime.now(timezone.utc).isoformat()
                        }
                    )
                
                retry_aws_call(update_job)
                logger.info(
                    f"Job status updated to completed: {job_id}",
                    context={'job_id': job_id}
                )
            except Exception as e:
                logger.error(
                    f"Error updating job status: {job_id}",
                    exc_info=True,
                    context={'job_id': job_id}
                )
                # Don't fail the pipeline if DynamoDB update fails
        
        # Send final results via WebSocket
        websocket_service = WebSocketService()
        try:
            websocket_service.send_job_complete(
                job_id=job_id,
                results=final_result
            )
        except Exception as e:
            logger.warning(
                f"Failed to send WebSocket completion message: {str(e)}",
                context={'job_id': job_id}
            )
            # Don't fail the pipeline if WebSocket fails
        
        # Log processing time
        logger.info(
            f"Final pipeline completed for job: {job_id}",
            context={
                'job_id': job_id,
                'processing_time_seconds': total_time,
                'sagemaker_time': sagemaker_time,
                'postprocessing_time': postprocess_time,
                'rooms_detected': len(filtered_rooms)
            }
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'success',
                'data': final_result
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
            f"Final pipeline error: {str(e)}",
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
            f"Unexpected error in final pipeline: {str(e)}",
            exc_info=True
        )
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'error',
                'error': {
                    'code': 'INTERNAL_ERROR',
                    'message': 'An internal error occurred during final processing'
                }
            })
        }

