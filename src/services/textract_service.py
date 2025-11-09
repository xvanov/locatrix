"""
Textract service for document analysis.

This module provides integration with AWS Textract AnalyzeDocument API
for extracting text and layout information from blueprint images.
"""
import os
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


class TextractService:
    """
    Service for analyzing documents using AWS Textract.
    
    Handles document analysis using Textract AnalyzeDocument API
    for extracting text and layout information from blueprint images.
    """
    
    def __init__(self, region_name: Optional[str] = None):
        """
        Initialize TextractService.
        
        Args:
            region_name: AWS region name (default: from env var or us-east-1)
        """
        self.region_name = region_name or os.environ.get('AWS_REGION', 'us-east-1')
        # Support LocalStack endpoint URL (Note: Textract not fully supported by LocalStack)
        endpoint_url = os.environ.get('AWS_ENDPOINT_URL')
        textract_kwargs = {'region_name': self.region_name}
        if endpoint_url:
            textract_kwargs['endpoint_url'] = endpoint_url
        self.textract_client = boto3.client('textract', **textract_kwargs)
    
    def analyze_document(self, s3_bucket: str, s3_key: str) -> Dict[str, Any]:
        """
        Analyze blueprint document using Textract AnalyzeDocument API.
        
        Args:
            s3_bucket: S3 bucket name containing the document
            s3_key: S3 key of the document
            
        Returns:
            Dict containing text blocks, layout blocks, and metadata
            
        Raises:
            ServiceUnavailableError: If Textract service is unavailable
            LocationDetectionError: If document analysis fails
        """
        logger.info(
            f"Analyzing document with Textract: s3://{s3_bucket}/{s3_key}",
            context={'s3_bucket': s3_bucket, 's3_key': s3_key}
        )
        
        def analyze():
            try:
                response = self.textract_client.analyze_document(
                    Document={
                        'S3Object': {
                            'Bucket': s3_bucket,
                            'Name': s3_key  # Textract uses 'Name' instead of 'Key'
                        }
                    },
                    FeatureTypes=['TABLES', 'FORMS']
                )
                return response
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                # Handle service unavailability
                if error_code in ['ServiceUnavailable', 'Throttling', 'ThrottlingException']:
                    raise ServiceUnavailableError('Textract', retry_after=5)
                # Re-raise other errors
                raise
        
        try:
            response = retry_aws_call(analyze)
            
            # Extract text blocks and layout blocks from response
            blocks = response.get('Blocks', [])
            
            # Separate text blocks and layout blocks
            text_blocks = []
            layout_blocks = []
            
            for block in blocks:
                block_type = block.get('BlockType', '')
                if block_type in ['WORD', 'LINE']:
                    text_blocks.append({
                        'id': block.get('Id', ''),
                        'text': block.get('Text', ''),
                        'geometry': block.get('Geometry', {})
                    })
                elif block_type in ['PAGE', 'TABLE', 'CELL', 'SELECTION_ELEMENT']:
                    layout_blocks.append({
                        'id': block.get('Id', ''),
                        'blockType': block_type,
                        'geometry': block.get('Geometry', {})
                    })
            
            # Extract metadata
            document_metadata = response.get('DocumentMetadata', {})
            pages = document_metadata.get('Pages', 1)
            
            # Get timestamp from response metadata
            response_metadata = response.get('ResponseMetadata', {})
            http_headers = response_metadata.get('HTTPHeaders', {})
            analyzed_at = http_headers.get('date', datetime.now(timezone.utc).isoformat())
            
            result = {
                'text_blocks': text_blocks,
                'layout_blocks': layout_blocks,
                'metadata': {
                    'pages': pages,
                    'analyzed_at': analyzed_at
                }
            }
            
            logger.info(
                f"Textract analysis completed: {len(text_blocks)} text blocks, {len(layout_blocks)} layout blocks",
                context={'s3_bucket': s3_bucket, 's3_key': s3_key, 'pages': pages}
            )
            
            return result
            
        except ServiceUnavailableError:
            logger.error(
                f"Textract service unavailable for document: s3://{s3_bucket}/{s3_key}",
                exc_info=True,
                context={'s3_bucket': s3_bucket, 's3_key': s3_key, 'service': 'Textract'}
            )
            raise
        except Exception as e:
            logger.error(
                f"Textract analysis failed for document: s3://{s3_bucket}/{s3_key}",
                exc_info=True,
                context={'s3_bucket': s3_bucket, 's3_key': s3_key}
            )
            raise LocationDetectionError(
                code='TEXTRACT_ANALYSIS_FAILED',
                message=f"Failed to analyze document: {str(e)}",
                details={'s3_bucket': s3_bucket, 's3_key': s3_key},
                status_code=500
            )

