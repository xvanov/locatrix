"""
REST API Lambda handler for Location Detection AI service.

This module provides the health check endpoint handler.
"""
import json
from typing import Dict, Any


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for REST API endpoints.
    
    Currently implements:
    - GET /health - Health check endpoint
    
    Args:
        event: API Gateway HTTP API event
        context: Lambda context object
        
    Returns:
        API Gateway HTTP API response with status code and body
    """
    # Extract HTTP method and path from event
    http_method = event.get('requestContext', {}).get('http', {}).get('method', '')
    path = event.get('requestContext', {}).get('http', {}).get('path', '')
    
    # Route to appropriate handler
    if http_method == 'GET' and path == '/health':
        return handle_health_check(event, context)
    
    # Default 404 response
    return {
        'statusCode': 404,
        'headers': get_cors_headers(),
        'body': json.dumps({
            'status': 'error',
            'error': {
                'code': 'NOT_FOUND',
                'message': f'Endpoint {http_method} {path} not found'
            }
        })
    }


def handle_health_check(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle GET /health endpoint.
    
    Returns service health status with service checks.
    
    Args:
        event: API Gateway HTTP API event
        context: Lambda context object
        
    Returns:
        API Gateway HTTP API response with health status
    """
    # For now, return healthy status for all services
    # In future stories, this will check actual service connectivity
    response_body = {
        'status': 'healthy',
        'services': {
            'dynamodb': 'healthy',
            's3': 'healthy',
            'sagemaker': 'healthy'
        }
    }
    
    return {
        'statusCode': 200,
        'headers': get_cors_headers(),
        'body': json.dumps(response_body)
    }


def get_cors_headers() -> Dict[str, str]:
    """
    Get CORS headers for API responses.
    
    Returns:
        Dictionary of CORS headers
    """
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        'Access-Control-Max-Age': '300'
    }

