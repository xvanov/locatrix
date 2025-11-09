"""
WebSocket service for sending real-time progress updates to connected clients.

This module provides functionality for sending messages to WebSocket clients
using the API Gateway Management API, with retry logic and error handling.
"""
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

# Handle imports for both Lambda (src/ directory) and local testing (project root)
try:
    from models.websocket_connection import WebSocketConnection
    from utils.retry import retry_aws_call, is_retryable_error
    from utils.logging import get_logger
except ImportError:
    # Fallback for local testing from project root
    from src.models.websocket_connection import WebSocketConnection
    from src.utils.retry import retry_aws_call, is_retryable_error
    from src.utils.logging import get_logger


logger = get_logger(__name__)


class WebSocketService:
    """
    Service for sending messages to WebSocket clients.
    
    Handles message sending, connection management, and retry logic
    for failed message deliveries.
    """
    
    def __init__(
        self,
        websocket_connections_table_name: Optional[str] = None,
        api_gateway_endpoint: Optional[str] = None
    ):
        """
        Initialize WebSocketService.
        
        Args:
            websocket_connections_table_name: DynamoDB table name for connections (default: from env var)
            api_gateway_endpoint: API Gateway Management API endpoint URL (default: from env var or event)
        """
        self.websocket_connections_table_name = (
            websocket_connections_table_name or 
            os.environ.get('WEBSOCKET_CONNECTIONS_TABLE_NAME')
        )
        self.api_gateway_endpoint = api_gateway_endpoint
        
        if not self.websocket_connections_table_name:
            raise ValueError("WEBSOCKET_CONNECTIONS_TABLE_NAME environment variable is required")
        
        self.dynamodb = boto3.client('dynamodb')
        self._apigateway_client = None
        self._connection_cache: Dict[str, List[str]] = {}  # job_id -> [connection_ids]
    
    def _get_apigateway_client(self, endpoint_url: Optional[str] = None) -> Any:
        """
        Get or create API Gateway Management API client.
        
        Args:
            endpoint_url: API Gateway endpoint URL (default: from instance or env)
            
        Returns:
            API Gateway Management API client
        """
        endpoint = endpoint_url or self.api_gateway_endpoint
        
        if self._apigateway_client is None or endpoint:
            self._apigateway_client = boto3.client(
                'apigatewaymanagementapi',
                endpoint_url=endpoint
            )
        
        return self._apigateway_client
    
    def get_connections_for_job(self, job_id: str) -> List[str]:
        """
        Get all connection IDs subscribed to a job.
        
        Args:
            job_id: Job ID to get connections for
            
        Returns:
            List of connection IDs
        """
        # Check cache first
        if job_id in self._connection_cache:
            return self._connection_cache[job_id]
        
        try:
            # Query using GSI for efficient lookup by job_id
            response = self.dynamodb.query(
                TableName=self.websocket_connections_table_name,
                IndexName='JobIdIndex',
                KeyConditionExpression='job_id = :job_id',
                ExpressionAttributeValues={
                    ':job_id': {'S': job_id}
                }
            )
            
            connection_ids = [
                item.get('connection_id', {}).get('S')
                for item in response.get('Items', [])
                if item.get('connection_id', {}).get('S')
            ]
            
            # Cache the results
            self._connection_cache[job_id] = connection_ids
            
            logger.debug(
                f'Found {len(connection_ids)} connections for job {job_id}',
                context={'job_id': job_id, 'connection_count': len(connection_ids)}
            )
            
            return connection_ids
        
        except ClientError as e:
            logger.error(
                f'Failed to query connections for job {job_id}: {str(e)}',
                exc_info=True,
                context={'job_id': job_id}
            )
            return []
    
    def send_message(
        self,
        connection_id: str,
        message: Dict[str, Any],
        endpoint_url: Optional[str] = None
    ) -> bool:
        """
        Send a message to a specific WebSocket connection.
        
        Args:
            connection_id: Connection ID to send message to
            message: Message dictionary to send
            endpoint_url: API Gateway endpoint URL (default: from instance)
            
        Returns:
            True if message sent successfully, False otherwise
        """
        try:
            api_client = self._get_apigateway_client(endpoint_url)
            message_json = json.dumps(message)
            
            def send_message_call():
                api_client.post_to_connection(
                    ConnectionId=connection_id,
                    Data=message_json.encode('utf-8')
                )
            
            # Use retry logic for transient failures
            retry_aws_call(send_message_call)
            
            logger.debug(
                'Message sent to connection',
                context={
                    'connection_id': connection_id,
                    'message_type': message.get('type', 'unknown')
                }
            )
            return True
        
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            
            if error_code == 'GoneException':
                # Connection no longer exists - clean up cache
                logger.warning(
                    'Connection gone, removing from cache',
                    context={'connection_id': connection_id}
                )
                # Try to determine job_id from cache to invalidate specific cache entry
                job_id_for_cache = None
                for job_id_key, conn_ids in self._connection_cache.items():
                    if connection_id in conn_ids:
                        job_id_for_cache = job_id_key
                        break
                self._remove_connection_from_cache(connection_id, job_id_for_cache)
            elif is_retryable_error(e):
                # Retryable error - log but don't fail processing
                logger.warning(
                    f'Retryable error sending message: {str(e)}',
                    context={'connection_id': connection_id}
                )
            else:
                # Non-retryable error - log but don't fail processing
                logger.error(
                    f'Failed to send message: {str(e)}',
                    exc_info=True,
                    context={'connection_id': connection_id}
                )
            
            return False
        
        except Exception as e:
            # Unexpected error - log but don't fail processing
            logger.error(
                f'Unexpected error sending message: {str(e)}',
                exc_info=True,
                context={'connection_id': connection_id}
            )
            return False
    
    def send_message_to_job(
        self,
        job_id: str,
        message: Dict[str, Any],
        endpoint_url: Optional[str] = None
    ) -> int:
        """
        Send a message to all connections subscribed to a job.
        
        Args:
            job_id: Job ID to send message to
            message: Message dictionary to send
            endpoint_url: API Gateway endpoint URL (default: from instance)
            
        Returns:
            Number of connections message was sent to successfully
        """
        connection_ids = self.get_connections_for_job(job_id)
        
        if not connection_ids:
            logger.debug(
                f'No connections found for job {job_id}',
                context={'job_id': job_id}
            )
            return 0
        
        success_count = 0
        for connection_id in connection_ids:
            if self.send_message(connection_id, message, endpoint_url):
                success_count += 1
        
        logger.info(
            f'Sent message to {success_count}/{len(connection_ids)} connections for job {job_id}',
            context={
                'job_id': job_id,
                'success_count': success_count,
                'total_connections': len(connection_ids),
                'message_type': message.get('type', 'unknown')
            }
        )
        
        return success_count
    
    def send_progress_update(
        self,
        job_id: str,
        stage: str,
        progress: int,
        message: str,
        estimated_seconds_remaining: Optional[int] = None,
        endpoint_url: Optional[str] = None
    ) -> int:
        """
        Send a progress update message to all connections subscribed to a job.
        
        Args:
            job_id: Job ID
            stage: Current pipeline stage
            progress: Progress percentage (0-100)
            message: Progress message
            estimated_seconds_remaining: Estimated seconds remaining (default: None)
            endpoint_url: API Gateway endpoint URL (default: from instance)
            
        Returns:
            Number of connections message was sent to successfully
        """
        progress_message = {
            'type': 'progress_update',
            'job_id': job_id,
            'stage': stage,
            'progress': progress,
            'message': message,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        if estimated_seconds_remaining is not None:
            progress_message['estimated_seconds_remaining'] = estimated_seconds_remaining
        
        return self.send_message_to_job(job_id, progress_message, endpoint_url)
    
    def send_stage_complete(
        self,
        job_id: str,
        stage: str,
        results: Dict[str, Any],
        endpoint_url: Optional[str] = None
    ) -> int:
        """
        Send a stage complete message to all connections subscribed to a job.
        
        Args:
            job_id: Job ID
            stage: Completed stage name
            results: Stage results
            endpoint_url: API Gateway endpoint URL (default: from instance)
            
        Returns:
            Number of connections message was sent to successfully
        """
        stage_complete_message = {
            'type': 'stage_complete',
            'job_id': job_id,
            'stage': stage,
            'results': results,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return self.send_message_to_job(job_id, stage_complete_message, endpoint_url)
    
    def send_job_complete(
        self,
        job_id: str,
        results: Dict[str, Any],
        endpoint_url: Optional[str] = None
    ) -> int:
        """
        Send a job complete message to all connections subscribed to a job.
        
        Args:
            job_id: Job ID
            results: Final job results
            endpoint_url: API Gateway endpoint URL (default: from instance)
            
        Returns:
            Number of connections message was sent to successfully
        """
        job_complete_message = {
            'type': 'job_complete',
            'job_id': job_id,
            'results': results,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return self.send_message_to_job(job_id, job_complete_message, endpoint_url)
    
    def send_job_failed(
        self,
        job_id: str,
        error: Dict[str, Any],
        endpoint_url: Optional[str] = None
    ) -> int:
        """
        Send a job failed message to all connections subscribed to a job.
        
        Args:
            job_id: Job ID
            error: Error details
            endpoint_url: API Gateway endpoint URL (default: from instance)
            
        Returns:
            Number of connections message was sent to successfully
        """
        job_failed_message = {
            'type': 'job_failed',
            'job_id': job_id,
            'error': error,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return self.send_message_to_job(job_id, job_failed_message, endpoint_url)
    
    def send_job_cancelled(
        self,
        job_id: str,
        endpoint_url: Optional[str] = None
    ) -> int:
        """
        Send a job cancelled message to all connections subscribed to a job.
        
        Args:
            job_id: Job ID
            endpoint_url: API Gateway endpoint URL (default: from instance)
            
        Returns:
            Number of connections message was sent to successfully
        """
        job_cancelled_message = {
            'type': 'job_cancelled',
            'job_id': job_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return self.send_message_to_job(job_id, job_cancelled_message, endpoint_url)
    
    def _remove_connection_from_cache(self, connection_id: str, job_id: Optional[str] = None):
        """
        Remove a connection from the cache.
        
        Args:
            connection_id: Connection ID to remove
            job_id: Optional job_id to remove from specific job cache
        """
        if job_id:
            # Remove from specific job cache
            if job_id in self._connection_cache:
                if connection_id in self._connection_cache[job_id]:
                    self._connection_cache[job_id].remove(connection_id)
                    if not self._connection_cache[job_id]:
                        # Remove job entry if no connections left
                        del self._connection_cache[job_id]
        else:
            # Remove from all job caches
            for job_id_key, connection_ids in list(self._connection_cache.items()):
                if connection_id in connection_ids:
                    connection_ids.remove(connection_id)
                    if not connection_ids:
                        # Remove job entry if no connections left
                        del self._connection_cache[job_id_key]
    
    def clear_cache(self, job_id: Optional[str] = None):
        """
        Clear the connection cache.
        
        Args:
            job_id: If provided, clear cache for this job only (default: clear all)
        """
        if job_id:
            self._connection_cache.pop(job_id, None)
        else:
            self._connection_cache.clear()

