"""
Preview service for managing preview cache and Textract results storage.

This module provides business logic for storing and retrieving preview results
in DynamoDB cache and Textract analysis results in S3.
"""
import os
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
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

# Preview cache TTL: 1 hour
PREVIEW_CACHE_TTL_HOURS = 1


class PreviewService:
    """
    Service for managing preview cache and Textract results storage.
    
    Handles storing preview results in DynamoDB cache and Textract
    analysis results in S3 for subsequent pipeline stages.
    """
    
    def __init__(
        self,
        preview_cache_table_name: Optional[str] = None,
        cache_bucket_name: Optional[str] = None
    ):
        """
        Initialize PreviewService.
        
        Args:
            preview_cache_table_name: DynamoDB table name for preview cache (default: from env var)
            cache_bucket_name: S3 bucket name for cache (default: from env var)
        """
        self.preview_cache_table_name = preview_cache_table_name or os.environ.get('PREVIEW_CACHE_TABLE_NAME')
        self.cache_bucket_name = cache_bucket_name or os.environ.get('CACHE_BUCKET_NAME')
        
        if not self.preview_cache_table_name:
            raise ValueError("PREVIEW_CACHE_TABLE_NAME environment variable is required")
        if not self.cache_bucket_name:
            raise ValueError("CACHE_BUCKET_NAME environment variable is required")
        
        # Support LocalStack endpoint URL
        endpoint_url = os.environ.get('AWS_ENDPOINT_URL')
        dynamodb_kwargs = {}
        s3_kwargs = {}
        if endpoint_url:
            dynamodb_kwargs['endpoint_url'] = endpoint_url
            s3_kwargs['endpoint_url'] = endpoint_url
        
        self.dynamodb = boto3.resource('dynamodb', **dynamodb_kwargs)
        self.s3 = boto3.client('s3', **s3_kwargs)
        self.preview_cache_table = self.dynamodb.Table(self.preview_cache_table_name)
    
    def get_cached_preview(self, blueprint_hash: str, model_version: str = '1.0.0') -> Optional[Dict[str, Any]]:
        """
        Get cached preview result if available.
        
        Args:
            blueprint_hash: Hash of blueprint file
            model_version: Model version used (default: '1.0.0')
            
        Returns:
            Cached preview result or None if not found
        """
        cache_key = f"preview:{blueprint_hash}:{model_version}"
        
        logger.info(
            f"Checking preview cache: {cache_key}",
            context={'cache_key': cache_key}
        )
        
        def get_item():
            try:
                response = self.preview_cache_table.get_item(
                    Key={'blueprint_hash': cache_key}
                )
                return response.get('Item')
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code in ['ServiceUnavailable', 'ResourceNotFoundException']:
                    raise ServiceUnavailableError('DynamoDB', retry_after=5)
                raise
        
        try:
            item = retry_aws_call(get_item)
            
            if item:
                logger.info(
                    f"Cache hit for preview: {cache_key}",
                    context={'cache_key': cache_key}
                )
                # Convert DynamoDB item to preview result format
                return {
                    'job_id': item.get('job_id'),
                    'stage': item.get('stage', 'preview'),
                    'rooms': item.get('rooms', []),
                    'processing_time_seconds': item.get('processing_time_seconds', 0),
                    'timestamp': item.get('timestamp')
                }
            else:
                logger.info(
                    f"Cache miss for preview: {cache_key}",
                    context={'cache_key': cache_key}
                )
                return None
        except ServiceUnavailableError:
            logger.warning(
                f"DynamoDB service unavailable, cache lookup failed: {cache_key}",
                context={'cache_key': cache_key, 'service': 'DynamoDB'}
            )
            return None
        except Exception as e:
            logger.error(
                f"Error retrieving cached preview: {cache_key}",
                exc_info=True,
                context={'cache_key': cache_key}
            )
            return None
    
    def store_preview_cache(
        self,
        blueprint_hash: str,
        preview_result: Dict[str, Any],
        model_version: str = '1.0.0'
    ) -> None:
        """
        Store preview result in DynamoDB cache.
        
        Args:
            blueprint_hash: Hash of blueprint file
            preview_result: Preview result dictionary
            model_version: Model version used (default: '1.0.0')
        """
        cache_key = f"preview:{blueprint_hash}:{model_version}"
        
        # Calculate TTL (1 hour from now)
        expires_at = int((datetime.now(timezone.utc) + timedelta(hours=PREVIEW_CACHE_TTL_HOURS)).timestamp())
        
        item = {
            'blueprint_hash': cache_key,
            'job_id': preview_result.get('job_id'),
            'stage': preview_result.get('stage', 'preview'),
            'rooms': preview_result.get('rooms', []),
            'processing_time_seconds': preview_result.get('processing_time_seconds', 0),
            'timestamp': preview_result.get('timestamp'),
            'model_version': model_version,
            'expires_at': expires_at
        }
        
        logger.info(
            f"Storing preview in cache: {cache_key}",
            context={'cache_key': cache_key, 'job_id': preview_result.get('job_id')}
        )
        
        def put_item():
            try:
                self.preview_cache_table.put_item(Item=item)
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code in ['ServiceUnavailable', 'ResourceNotFoundException']:
                    raise ServiceUnavailableError('DynamoDB', retry_after=5)
                raise
        
        try:
            retry_aws_call(put_item)
            logger.info(
                f"Preview cached successfully: {cache_key}",
                context={'cache_key': cache_key}
            )
            return True
        except ServiceUnavailableError:
            logger.warning(
                f"DynamoDB service unavailable, cache storage failed: {cache_key}",
                context={'cache_key': cache_key, 'service': 'DynamoDB'}
            )
            return False
        except Exception:
            logger.error(
                f"Error storing preview cache: {cache_key}",
                exc_info=True,
                context={'cache_key': cache_key}
            )
            return False
    
    def store_textract_results(
        self,
        job_id: str,
        textract_result: Dict[str, Any]
    ) -> str:
        """
        Store Textract analysis results in S3 for subsequent stages.
        
        Args:
            job_id: Job identifier
            textract_result: Textract analysis result
            
        Returns:
            S3 key where results were stored
        """
        s3_key = f"cache/textract/{job_id}/analysis.json"
        
        logger.info(
            f"Storing Textract results in S3: {s3_key}",
            context={'job_id': job_id, 's3_key': s3_key}
        )
        
        # Add metadata
        result_with_metadata = {
            **textract_result,
            'job_id': job_id,
            'stored_at': datetime.now(timezone.utc).isoformat()
        }
        
        def put_object():
            try:
                self.s3.put_object(
                    Bucket=self.cache_bucket_name,
                    Key=s3_key,
                    Body=json.dumps(result_with_metadata),
                    ContentType='application/json'
                )
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code in ['ServiceUnavailable', 'SlowDown']:
                    raise ServiceUnavailableError('S3', retry_after=5)
                raise
        
        try:
            retry_aws_call(put_object)
            logger.info(
                f"Textract results stored successfully: {s3_key}",
                context={'job_id': job_id, 's3_key': s3_key}
            )
            return s3_key
        except ServiceUnavailableError as e:
            logger.warning(
                f"S3 service unavailable, Textract results storage failed: {s3_key}",
                context={'job_id': job_id, 's3_key': s3_key, 'service': 'S3'}
            )
            # Don't fail preview if S3 storage fails, but return empty key
            return ''
        except Exception as e:
            logger.error(
                f"Error storing Textract results: {s3_key}",
                exc_info=True,
                context={'job_id': job_id, 's3_key': s3_key}
            )
            # Don't fail preview if S3 storage fails, but return empty key
            return ''
    
    def get_textract_results(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve Textract analysis results from S3.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Textract analysis result or None if not found
        """
        s3_key = f"cache/textract/{job_id}/analysis.json"
        
        logger.info(
            f"Retrieving Textract results from S3: {s3_key}",
            context={'job_id': job_id, 's3_key': s3_key}
        )
        
        def get_object():
            try:
                response = self.s3.get_object(
                    Bucket=self.cache_bucket_name,
                    Key=s3_key
                )
                return response['Body'].read().decode('utf-8')
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code == 'NoSuchKey':
                    return None
                if error_code in ['ServiceUnavailable', 'SlowDown']:
                    raise ServiceUnavailableError('S3', retry_after=5)
                raise
        
        try:
            content = retry_aws_call(get_object)
            
            if content:
                result = json.loads(content)
                logger.info(
                    f"Textract results retrieved successfully: {s3_key}",
                    context={'job_id': job_id, 's3_key': s3_key}
                )
                return result
            else:
                logger.info(
                    f"Textract results not found: {s3_key}",
                    context={'job_id': job_id, 's3_key': s3_key}
                )
                return None
        except ServiceUnavailableError:
            logger.warning(
                f"S3 service unavailable, Textract results retrieval failed: {s3_key}",
                context={'job_id': job_id, 's3_key': s3_key, 'service': 'S3'}
            )
            return None
        except Exception as e:
            logger.error(
                f"Error retrieving Textract results: {s3_key}",
                exc_info=True,
                context={'job_id': job_id, 's3_key': s3_key}
            )
            return None

