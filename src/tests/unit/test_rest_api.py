"""
Unit tests for REST API handler.
"""
import json
import pytest
from src.api import rest_api


def test_health_check_handler():
    """Test health check handler returns correct response format."""
    # Create mock API Gateway HTTP API event
    event = {
        'requestContext': {
            'http': {
                'method': 'GET',
                'path': '/health'
            }
        }
    }
    
    # Create mock context (minimal required attributes)
    class MockContext:
        function_name = 'test-function'
        function_version = '$LATEST'
        invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test-function'
        memory_limit_in_mb = '256'
        aws_request_id = 'test-request-id'
    
    context = MockContext()
    
    # Call handler
    response = rest_api.handler(event, context)
    
    # Verify response structure
    assert response['statusCode'] == 200
    assert 'headers' in response
    assert 'body' in response
    
    # Verify CORS headers
    headers = response['headers']
    assert headers['Content-Type'] == 'application/json'
    assert headers['Access-Control-Allow-Origin'] == '*'
    assert headers['Access-Control-Allow-Methods'] == 'GET, POST, PUT, DELETE, OPTIONS'
    assert headers['Access-Control-Allow-Headers'] == 'Content-Type, Authorization'
    
    # Verify response body format
    body = json.loads(response['body'])
    assert body['status'] == 'healthy'
    assert 'services' in body
    assert body['services']['dynamodb'] == 'healthy'
    assert body['services']['s3'] == 'healthy'
    assert body['services']['sagemaker'] == 'healthy'


def test_health_check_handler_not_found():
    """Test handler returns 404 for unknown endpoints."""
    event = {
        'requestContext': {
            'http': {
                'method': 'GET',
                'path': '/unknown'
            }
        }
    }
    
    class MockContext:
        function_name = 'test-function'
        function_version = '$LATEST'
        invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test-function'
        memory_limit_in_mb = '256'
        aws_request_id = 'test-request-id'
    
    context = MockContext()
    
    response = rest_api.handler(event, context)
    
    assert response['statusCode'] == 404
    body = json.loads(response['body'])
    assert body['status'] == 'error'
    assert 'error' in body
    assert body['error']['code'] == 'NOT_FOUND'


def test_get_cors_headers():
    """Test CORS headers function returns correct headers."""
    headers = rest_api.get_cors_headers()
    
    assert headers['Content-Type'] == 'application/json'
    assert headers['Access-Control-Allow-Origin'] == '*'
    assert headers['Access-Control-Allow-Methods'] == 'GET, POST, PUT, DELETE, OPTIONS'
    assert headers['Access-Control-Allow-Headers'] == 'Content-Type, Authorization'
    assert headers['Access-Control-Max-Age'] == '300'

