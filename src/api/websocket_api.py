"""
WebSocket API Lambda handler for Location Detection AI service.

This module provides WebSocket API handlers for real-time progress updates.
"""
import json
import os
from typing import Dict, Any, Optional
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

# Handle imports for both Lambda (src/ directory) and local testing (project root)
try:
    from utils.logging import get_logger
    from utils.request_id import generate_request_id
    from utils.errors import LocationDetectionError
    from services.job_service import JobService
    from models.websocket_connection import WebSocketConnection, ConnectionStatus
except ImportError:
    # Fallback for local testing from project root
    from src.utils.logging import get_logger
    from src.utils.request_id import generate_request_id
    from src.utils.errors import LocationDetectionError
    from src.services.job_service import JobService
    from src.models.websocket_connection import WebSocketConnection, ConnectionStatus


logger = get_logger(__name__)

# AWS clients
dynamodb = boto3.client('dynamodb')
apigateway_management_api = None  # Will be initialized per request

# Environment variables
WEBSOCKET_CONNECTIONS_TABLE_NAME = os.environ.get('WEBSOCKET_CONNECTIONS_TABLE_NAME', '')


class WebSocketError(LocationDetectionError):
    """Error raised for WebSocket-specific issues."""
    pass


class InvalidMessageError(WebSocketError):
    """Error raised when client message format is invalid."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code='INVALID_MESSAGE',
            message=message,
            details=details or {},
            status_code=400
        )


def get_apigateway_management_api(event: Dict[str, Any]) -> Any:
    """
    Get API Gateway Management API client for the WebSocket API.
    
    Args:
        event: WebSocket event containing domain and stage
        
    Returns:
        API Gateway Management API client
    """
    global apigateway_management_api
    
    domain_name = event.get('requestContext', {}).get('domainName', '')
    stage = event.get('requestContext', {}).get('stage', '')
    
    if not domain_name or not stage:
        raise WebSocketError(
            code='MISSING_API_GATEWAY_CONTEXT',
            message='Missing domain or stage in request context',
            status_code=500
        )
    
    # Construct endpoint URL
    endpoint_url = f'https://{domain_name}/{stage}'
    
    # Create client if not exists or if endpoint changed
    if apigateway_management_api is None:
        apigateway_management_api = boto3.client(
            'apigatewaymanagementapi',
            endpoint_url=endpoint_url
        )
    
    return apigateway_management_api


def extract_connection_id(event: Dict[str, Any]) -> str:
    """
    Extract connection ID from WebSocket event.
    
    Args:
        event: WebSocket event
        
    Returns:
        Connection ID string
        
    Raises:
        WebSocketError: If connection ID is missing
    """
    connection_id = event.get('requestContext', {}).get('connectionId')
    if not connection_id:
        raise WebSocketError(
            code='MISSING_CONNECTION_ID',
            message='Connection ID not found in event context',
            status_code=500
        )
    return connection_id


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for WebSocket API events.
    
    Handles:
    - $connect: Client connects to WebSocket
    - $disconnect: Client disconnects from WebSocket
    - $default: Client sends a message
    
    Args:
        event: API Gateway WebSocket event
        context: Lambda context object
        
    Returns:
        Response dictionary with statusCode
    """
    # Generate request ID for tracing
    request_id = generate_request_id()
    logger.set_request_id(request_id)
    
    # Extract route key (event type)
    route_key = event.get('requestContext', {}).get('routeKey', '')
    
    try:
        if route_key == '$connect':
            return handle_connect(event, context, request_id)
        elif route_key == '$disconnect':
            return handle_disconnect(event, context, request_id)
        elif route_key == '$default':
            return handle_default(event, context, request_id)
        else:
            logger.warning(f'Unknown route key: {route_key}', context={'route_key': route_key})
            return {'statusCode': 200}
    except Exception as e:
        logger.error(
            f'Error handling WebSocket event: {str(e)}',
            exc_info=True,
            context={'route_key': route_key, 'request_id': request_id}
        )
        # For WebSocket, we return 200 even on error to avoid connection issues
        return {'statusCode': 200}


def handle_connect(event: Dict[str, Any], context: Any, request_id: str) -> Dict[str, Any]:
    """
    Handle $connect event - client connects to WebSocket.
    
    Stores connection ID in DynamoDB for later message routing.
    
    Args:
        event: WebSocket $connect event
        context: Lambda context
        request_id: Request ID for tracing
        
    Returns:
        Response dictionary with statusCode
    """
    connection_id = extract_connection_id(event)
    logger.set_request_id(request_id)
    
    logger.info(
        'WebSocket connection established',
        context={
            'connection_id': connection_id,
            'request_id': request_id
        }
    )
    
    # Store connection in DynamoDB
    # Note: job_id will be set when client sends subscribe message
    # For now, we store connection with a placeholder job_id
    try:
        if WEBSOCKET_CONNECTIONS_TABLE_NAME:
            # Store connection record with placeholder job_id
            # Task 2 will handle proper job_id association via subscribe message
            connection = WebSocketConnection(
                connection_id=connection_id,
                job_id='__pending__',  # Placeholder until subscribe
                status=ConnectionStatus.CONNECTED
            )
            
            dynamodb.put_item(
                TableName=WEBSOCKET_CONNECTIONS_TABLE_NAME,
                Item=connection.to_dynamodb_item()
            )
            logger.info(
                'Connection stored in DynamoDB',
                context={'connection_id': connection_id}
            )
    except ClientError as e:
        logger.error(
            f'Failed to store connection in DynamoDB: {str(e)}',
            exc_info=True,
            context={'connection_id': connection_id}
        )
        # Don't fail connection if DynamoDB write fails
        # Connection will be cleaned up on disconnect anyway
    
    return {'statusCode': 200}


def handle_disconnect(event: Dict[str, Any], context: Any, request_id: str) -> Dict[str, Any]:
    """
    Handle $disconnect event - client disconnects from WebSocket.
    
    Cleans up connection records from DynamoDB.
    
    Args:
        event: WebSocket $disconnect event
        context: Lambda context
        request_id: Request ID for tracing
        
    Returns:
        Response dictionary with statusCode
    """
    connection_id = extract_connection_id(event)
    logger.set_request_id(request_id)
    
    logger.info(
        'WebSocket connection disconnected',
        context={
            'connection_id': connection_id,
            'request_id': request_id
        }
    )
    
    # Clean up connection records from DynamoDB
    # Need to query for all records with this connection_id
    try:
        if WEBSOCKET_CONNECTIONS_TABLE_NAME:
            # Query for all items with this connection_id
            # Since job_id is sort key, we need to query and delete all items
            response = dynamodb.query(
                TableName=WEBSOCKET_CONNECTIONS_TABLE_NAME,
                KeyConditionExpression='connection_id = :conn_id',
                ExpressionAttributeValues={
                    ':conn_id': {'S': connection_id}
                }
            )
            
            # Delete all connection records
            for item in response.get('Items', []):
                job_id = item.get('job_id', {}).get('S', '')
                dynamodb.delete_item(
                    TableName=WEBSOCKET_CONNECTIONS_TABLE_NAME,
                    Key={
                        'connection_id': {'S': connection_id},
                        'job_id': {'S': job_id}
                    }
                )
            
            logger.info(
                'Connection records cleaned up from DynamoDB',
                context={
                    'connection_id': connection_id,
                    'deleted_count': len(response.get('Items', []))
                }
            )
    except ClientError as e:
        logger.error(
            f'Failed to clean up connection from DynamoDB: {str(e)}',
            exc_info=True,
            context={'connection_id': connection_id}
        )
        # Don't fail disconnect if cleanup fails
    
    return {'statusCode': 200}


def handle_default(event: Dict[str, Any], context: Any, request_id: str) -> Dict[str, Any]:
    """
    Handle $default event - client sends a message.
    
    Processes client messages: subscribe, cancel_job, request_status.
    Task 7 will implement full message handling logic.
    
    Args:
        event: WebSocket $default event
        context: Lambda context
        request_id: Request ID for tracing
        
    Returns:
        Response dictionary with statusCode
    """
    connection_id = extract_connection_id(event)
    logger.set_request_id(request_id)
    
    # Extract message body
    body = event.get('body', '')
    if not body:
        logger.warning('Empty message body received', context={'connection_id': connection_id})
        send_error_message(event, connection_id, 'Empty message body')
        return {'statusCode': 200}
    
    try:
        # Parse JSON message
        message_data = json.loads(body)
        message_type = message_data.get('type', '')
        
        logger.info(
            'Received client message',
            context={
                'connection_id': connection_id,
                'message_type': message_type,
                'request_id': request_id
            }
        )
        
        # Update last_activity timestamp
        update_connection_activity(connection_id)
        
        # Route to appropriate handler
        if message_type == 'subscribe':
            handle_subscribe(event, connection_id, message_data, request_id)
        elif message_type == 'cancel_job':
            handle_cancel_job(event, connection_id, message_data, request_id)
        elif message_type == 'request_status':
            handle_request_status(event, connection_id, message_data, request_id)
        else:
            send_error_message(
                event,
                connection_id,
                f'Unknown message type: {message_type}',
                details={
                    'received_type': message_type,
                    'allowed_types': ['subscribe', 'cancel_job', 'request_status']
                }
            )
    
    except json.JSONDecodeError as e:
        logger.warning(
            f'Invalid JSON in message body: {str(e)}',
            context={'connection_id': connection_id, 'body': body}
        )
        send_error_message(event, connection_id, 'Invalid JSON format')
    except Exception as e:
        logger.error(
            f'Error processing client message: {str(e)}',
            exc_info=True,
            context={'connection_id': connection_id}
        )
        send_error_message(event, connection_id, 'Internal error processing message')
    
    return {'statusCode': 200}


def handle_subscribe(event: Dict[str, Any], connection_id: str, message_data: Dict[str, Any], request_id: str):
    """
    Handle subscribe message - associate connection with job_id.
    
    Validates job exists and stores connection-to-job mapping in DynamoDB.
    
    Args:
        event: WebSocket event
        connection_id: Connection ID
        message_data: Parsed message data
        request_id: Request ID for tracing
    """
    job_id = message_data.get('job_id')
    if not job_id:
        send_error_message(event, connection_id, 'Missing job_id in subscribe message')
        return
    
    logger.info(
        'Processing subscribe message',
        context={
            'connection_id': connection_id,
            'job_id': job_id,
            'request_id': request_id
        }
    )
    
    try:
        # Validate job exists
        job_service = JobService()
        try:
            job = job_service.get_job(job_id)
            logger.debug(
                f'Job found for subscription: {job_id}',
                context={'job_id': job_id, 'status': job.status.value}
            )
        except Exception as e:
            logger.warning(
                f'Job not found for subscription: {job_id}',
                context={'job_id': job_id, 'error': str(e)}
            )
            send_error_message(
                event,
                connection_id,
                f'Job not found: {job_id}',
                details={'job_id': job_id}
            )
            return
        
        # Store connection-to-job mapping
        if WEBSOCKET_CONNECTIONS_TABLE_NAME:
            # Delete placeholder record if it exists
            try:
                dynamodb.delete_item(
                    TableName=WEBSOCKET_CONNECTIONS_TABLE_NAME,
                    Key={
                        'connection_id': {'S': connection_id},
                        'job_id': {'S': '__pending__'}
                    }
                )
            except ClientError:
                pass  # Ignore if record doesn't exist
            
            # Create connection record
            connection = WebSocketConnection(
                connection_id=connection_id,
                job_id=job_id,
                status=ConnectionStatus.SUBSCRIBED
            )
            
            dynamodb.put_item(
                TableName=WEBSOCKET_CONNECTIONS_TABLE_NAME,
                Item=connection.to_dynamodb_item()
            )
            
            logger.info(
                'Connection subscribed to job',
                context={
                    'connection_id': connection_id,
                    'job_id': job_id
                }
            )
            
            # Send success response with current job status
            send_message(event, connection_id, {
                'type': 'subscribed',
                'job_id': job_id,
                'job_status': job.status.value,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
    except Exception as e:
        logger.error(
            f'Failed to process subscribe message: {str(e)}',
            exc_info=True,
            context={'connection_id': connection_id, 'job_id': job_id}
        )
        send_error_message(event, connection_id, 'Failed to subscribe to job updates')


def handle_cancel_job(event: Dict[str, Any], connection_id: str, message_data: Dict[str, Any], request_id: str):
    """
    Handle cancel_job message - cancel job processing.
    
    Cancels the job and sends cancellation confirmation to client.
    
    Args:
        event: WebSocket event
        connection_id: Connection ID
        message_data: Parsed message data
        request_id: Request ID for tracing
    """
    job_id = message_data.get('job_id')
    if not job_id:
        send_error_message(event, connection_id, 'Missing job_id in cancel_job message')
        return
    
    logger.info(
        'Processing cancel_job message',
        context={
            'connection_id': connection_id,
            'job_id': job_id,
            'request_id': request_id
        }
    )
    
    try:
        job_service = JobService()
        cancelled_job = job_service.cancel_job(job_id)
        
        logger.info(
            'Job cancelled via WebSocket',
            context={
                'connection_id': connection_id,
                'job_id': job_id,
                'status': cancelled_job.status.value
            }
        )
        
        # Send cancellation confirmation
        send_message(event, connection_id, {
            'type': 'job_cancelled',
            'job_id': job_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    except Exception as e:
        error_message = str(e)
        logger.error(
            f'Failed to cancel job: {error_message}',
            exc_info=True,
            context={'connection_id': connection_id, 'job_id': job_id}
        )
        
        # Send error response
        send_error_message(
            event,
            connection_id,
            f'Failed to cancel job: {error_message}',
            details={'job_id': job_id}
        )


def handle_request_status(event: Dict[str, Any], connection_id: str, message_data: Dict[str, Any], request_id: str):
    """
    Handle request_status message - send current job status.
    
    Retrieves job status and sends it to the client.
    
    Args:
        event: WebSocket event
        connection_id: Connection ID
        message_data: Parsed message data
        request_id: Request ID for tracing
    """
    job_id = message_data.get('job_id')
    if not job_id:
        send_error_message(event, connection_id, 'Missing job_id in request_status message')
        return
    
    logger.info(
        'Processing request_status message',
        context={
            'connection_id': connection_id,
            'job_id': job_id,
            'request_id': request_id
        }
    )
    
    try:
        job_service = JobService()
        job = job_service.get_job(job_id)
        
        # Build status response
        status_response = {
            'type': 'job_status',
            'job_id': job_id,
            'status': job.status.value,
            'created_at': job.created_at,
            'updated_at': job.updated_at,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Add additional fields if available
        if job.blueprint_format:
            status_response['blueprint_format'] = job.blueprint_format
        if job.result_s3_key:
            status_response['result_s3_key'] = job.result_s3_key
        if job.error:
            status_response['error'] = job.error
        
        send_message(event, connection_id, status_response)
        
        logger.debug(
            'Job status sent to client',
            context={
                'connection_id': connection_id,
                'job_id': job_id,
                'status': job.status.value
            }
        )
    
    except Exception as e:
        error_message = str(e)
        logger.error(
            f'Failed to get job status: {error_message}',
            exc_info=True,
            context={'connection_id': connection_id, 'job_id': job_id}
        )
        
        # Send error response
        send_error_message(
            event,
            connection_id,
            f'Failed to get job status: {error_message}',
            details={'job_id': job_id}
        )


def update_connection_activity(connection_id: str):
    """
    Update last_activity timestamp for a connection.
    
    Args:
        connection_id: Connection ID
    """
    if not WEBSOCKET_CONNECTIONS_TABLE_NAME:
        return
    
    try:
        # Query for all connection records
        response = dynamodb.query(
            TableName=WEBSOCKET_CONNECTIONS_TABLE_NAME,
            KeyConditionExpression='connection_id = :conn_id',
            ExpressionAttributeValues={
                ':conn_id': {'S': connection_id}
            }
        )
        
        # Update last_activity for all records
        now = datetime.now(timezone.utc).isoformat()
        for item in response.get('Items', []):
            job_id = item.get('job_id', {}).get('S', '')
            dynamodb.update_item(
                TableName=WEBSOCKET_CONNECTIONS_TABLE_NAME,
                Key={
                    'connection_id': {'S': connection_id},
                    'job_id': {'S': job_id}
                },
                UpdateExpression='SET last_activity = :now',
                ExpressionAttributeValues={
                    ':now': {'S': now}
                }
            )
    except Exception as e:
        logger.warning(
            f'Failed to update connection activity: {str(e)}',
            context={'connection_id': connection_id}
        )


def send_message(event: Dict[str, Any], connection_id: str, message: Dict[str, Any]):
    """
    Send a message to a WebSocket client.
    
    Args:
        event: WebSocket event (for API Gateway endpoint)
        connection_id: Connection ID to send message to
        message: Message dictionary to send
    """
    try:
        api_client = get_apigateway_management_api(event)
        message_json = json.dumps(message)
        
        api_client.post_to_connection(
            ConnectionId=connection_id,
            Data=message_json.encode('utf-8')
        )
        
        logger.debug(
            'Message sent to client',
            context={
                'connection_id': connection_id,
                'message_type': message.get('type', 'unknown')
            }
        )
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == 'GoneException':
            # Connection no longer exists, clean up
            logger.warning(
                'Connection gone, cleaning up',
                context={'connection_id': connection_id}
            )
            # Cleanup will happen on disconnect event
        else:
            logger.error(
                f'Failed to send message: {str(e)}',
                exc_info=True,
                context={'connection_id': connection_id}
            )
    except Exception as e:
        logger.error(
            f'Unexpected error sending message: {str(e)}',
            exc_info=True,
            context={'connection_id': connection_id}
        )


def send_error_message(event: Dict[str, Any], connection_id: str, error_message: str, details: Optional[Dict[str, Any]] = None):
    """
    Send an error message to a WebSocket client.
    
    Args:
        event: WebSocket event
        connection_id: Connection ID
        error_message: Error message
        details: Additional error details
    """
    error_response = {
        'type': 'error',
        'message': error_message,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    if details:
        error_response['details'] = details
    
    send_message(event, connection_id, error_response)

