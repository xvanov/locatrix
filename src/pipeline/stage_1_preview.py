"""
Preview pipeline Lambda handler for Stage 1 preview processing.

This module provides the Lambda handler for the preview pipeline stage,
which processes blueprints using Textract and returns fast room detection results.
"""
import json
import os
import time
from typing import Dict, Any
from datetime import datetime, timezone

# Handle imports for both Lambda (src/ directory) and local testing (project root)
try:
    from services.job_service import JobService
    from services.textract_service import TextractService
    from services.preview_service import PreviewService
    from utils.room_detection import detect_rooms
    from utils.errors import JobNotFoundError, LocationDetectionError, ServiceUnavailableError
    from utils.logging import get_logger
except ImportError:
    # Fallback for local testing from project root
    from src.services.job_service import JobService
    from src.services.textract_service import TextractService
    from src.services.preview_service import PreviewService
    from src.utils.room_detection import detect_rooms
    from src.utils.errors import JobNotFoundError, LocationDetectionError, ServiceUnavailableError
    from src.utils.logging import get_logger


logger = get_logger(__name__)

# Model version for preview pipeline
MODEL_VERSION = '1.0.0'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for preview pipeline stage.
    
    Processes blueprint using Textract and returns fast room detection results.
    
    Args:
        event: Lambda event with job_id and optional blueprint_s3_key
        context: Lambda context object
        
    Returns:
        Preview result dictionary with rooms and timing metrics
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
            f"Starting preview pipeline for job: {job_id}",
            context={'job_id': job_id}
        )
        
        # Get job information
        job_service = JobService()
        job = job_service.get_job(job_id)
        
        if not job.blueprint_s3_key:
            raise LocationDetectionError(
                code='INVALID_JOB',
                message='Job does not have blueprint S3 key',
                details={'job_id': job_id},
                status_code=400
            )
        
        # Extract S3 bucket and key
        blueprint_s3_key = job.blueprint_s3_key
        blueprints_bucket_name = os.environ.get('BLUEPRINTS_BUCKET_NAME')
        
        if not blueprints_bucket_name:
            raise LocationDetectionError(
                code='CONFIGURATION_ERROR',
                message='BLUEPRINTS_BUCKET_NAME environment variable is required',
                details={},
                status_code=500
            )
        
        # Check cache first
        preview_service = PreviewService()
        cached_preview = None
        if job.blueprint_hash:
            cached_preview = preview_service.get_cached_preview(
                job.blueprint_hash,
                MODEL_VERSION
            )
        
        if cached_preview:
            logger.info(
                f"Returning cached preview for job: {job_id}",
                context={'job_id': job_id}
            )
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'status': 'success',
                    'data': cached_preview
                })
            }
        
        # Process preview pipeline
        textract_start_time = time.time()
        
        # Analyze document with Textract
        textract_service = TextractService()
        textract_result = textract_service.analyze_document(
            s3_bucket=blueprints_bucket_name,
            s3_key=blueprint_s3_key
        )
        
        textract_time = time.time() - textract_start_time
        
        # Store Textract results in S3 for subsequent stages
        textract_s3_key = preview_service.store_textract_results(job_id, textract_result)
        
        # Detect rooms using fast algorithm
        room_detection_start_time = time.time()
        rooms = detect_rooms(textract_result)
        room_detection_time = time.time() - room_detection_start_time
        
        # Calculate total processing time
        total_time = time.time() - start_time
        
        # Build preview result
        preview_result = {
            'job_id': job_id,
            'stage': 'preview',
            'rooms': rooms,
            'processing_time_seconds': round(total_time, 2),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'timing_metrics': {
                'textract_analysis_seconds': round(textract_time, 2),
                'room_detection_seconds': round(room_detection_time, 2),
                'total_seconds': round(total_time, 2)
            }
        }
        
        # Store in cache (ensure it completes before returning)
        if job.blueprint_hash:
            try:
                logger.info(
                    f"Storing preview cache for job: {job_id}",
                    context={
                        'job_id': job_id,
                        'blueprint_hash': job.blueprint_hash,
                        'model_version': MODEL_VERSION
                    }
                )
                cache_stored = preview_service.store_preview_cache(
                    job.blueprint_hash,
                    preview_result,
                    MODEL_VERSION
                )
                if not cache_stored:
                    logger.error(
                        f"Preview cache storage returned failure indicator for job: {job_id}",
                        context={'job_id': job_id, 'blueprint_hash': job.blueprint_hash}
                    )
                    return {
                        'statusCode': 503,
                        'body': json.dumps({
                            'status': 'error',
                            'error': {
                                'code': 'PREVIEW_CACHE_STORE_FAILED',
                                'message': 'Failed to store preview results in cache',
                                'details': {
                                    'job_id': job_id,
                                    'blueprint_hash': job.blueprint_hash,
                                    'service': 'DynamoDB'
                                }
                            }
                        })
                    }
                logger.info(
                    f"Preview cache stored successfully for job: {job_id}",
                    context={'job_id': job_id, 'blueprint_hash': job.blueprint_hash}
                )
            except ServiceUnavailableError as e:
                error_details = getattr(e, 'details', {}) or {}
                service_name = error_details.get('service_name', 'DynamoDB')
                retry_after = error_details.get('retry_after')
                logger.error(
                    f"Preview cache storage failed for job: {job_id}",
                    exc_info=True,
                    context={
                        'job_id': job_id,
                        'blueprint_hash': job.blueprint_hash,
                        'service': service_name
                    }
                )
                return {
                    'statusCode': 503,
                    'body': json.dumps({
                        'status': 'error',
                        'error': {
                            'code': 'PREVIEW_CACHE_STORE_FAILED',
                            'message': 'Failed to store preview results in cache',
                            'details': {
                                'job_id': job_id,
                                'blueprint_hash': job.blueprint_hash,
                                'service': service_name,
                                'retry_after': retry_after
                            }
                        }
                    })
                }
            except Exception as e:
                logger.error(
                    f"Unexpected error storing preview cache for job: {job_id}",
                    exc_info=True,
                    context={'job_id': job_id, 'blueprint_hash': job.blueprint_hash}
                )
                return {
                    'statusCode': 500,
                    'body': json.dumps({
                        'status': 'error',
                        'error': {
                            'code': 'PREVIEW_CACHE_STORE_FAILED',
                            'message': 'Unexpected error storing preview results in cache',
                            'details': {
                                'job_id': job_id,
                                'blueprint_hash': job.blueprint_hash
                            }
                        }
                    })
                }
        else:
            logger.warning(
                f"Job {job_id} has no blueprint_hash, skipping cache storage",
                context={'job_id': job_id}
            )
        
        # Log processing time
        logger.info(
            f"Preview pipeline completed for job: {job_id}",
            context={
                'job_id': job_id,
                'processing_time_seconds': total_time,
                'textract_time': textract_time,
                'room_detection_time': room_detection_time,
                'rooms_detected': len(rooms)
            }
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'success',
                'data': preview_result
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
            f"Preview pipeline error: {str(e)}",
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
            f"Unexpected error in preview pipeline: {str(e)}",
            exc_info=True
        )
        # Return partial results if available (graceful degradation)
        # For now, return error
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'error',
                'error': {
                    'code': 'INTERNAL_ERROR',
                    'message': 'An internal error occurred during preview processing'
                }
            })
        }

