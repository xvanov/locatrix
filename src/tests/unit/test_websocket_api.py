"""
Unit tests for WebSocket API handler.
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from src.api import websocket_api


@pytest.fixture
def mock_aws_services():
    """Mock AWS services."""
    with patch('src.api.websocket_api.boto3') as mock_boto3, \
         patch('src.api.websocket_api.dynamodb') as mock_dynamodb:
        
        mock_apigateway = MagicMock()
        
        def client_side_effect(service, **kwargs):
            if service == 'dynamodb':
                return mock_dynamodb
            elif service == 'apigatewaymanagementapi':
                return mock_apigateway
            return MagicMock()
        
        mock_boto3.client.side_effect = client_side_effect
        
        # Mock get_apigateway_management_api to return our mocked client
        with patch('src.api.websocket_api.get_apigateway_management_api') as mock_get_api:
            mock_get_api.return_value = mock_apigateway
            
            yield {
                'dynamodb': mock_dynamodb,
                'apigateway': mock_apigateway,
                'get_api': mock_get_api
            }


@pytest.fixture
def mock_context():
    """Mock Lambda context."""
    class MockContext:
        function_name = 'test-websocket-handler'
        function_version = '$LATEST'
        invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test-websocket-handler'
        memory_limit_in_mb = '256'
        aws_request_id = 'test-request-id'
    
    return MockContext()


@pytest.fixture
def base_websocket_event():
    """Base WebSocket event structure."""
    return {
        'requestContext': {
            'connectionId': 'conn_test_123',
            'domainName': 'test-api.execute-api.us-east-1.amazonaws.com',
            'stage': 'api',
            'routeKey': '$connect'
        }
    }


class TestConnectHandler:
    """Test $connect event handler."""
    
    def test_handle_connect_success(self, mock_aws_services, mock_context, base_websocket_event):
        """Test successful connection."""
        # Patch the module-level variables
        with patch.dict('os.environ', {'WEBSOCKET_CONNECTIONS_TABLE_NAME': 'test-connections'}), \
             patch.object(websocket_api, 'WEBSOCKET_CONNECTIONS_TABLE_NAME', 'test-connections'), \
             patch.object(websocket_api, 'dynamodb', mock_aws_services['dynamodb']):
            response = websocket_api.handler(base_websocket_event, mock_context)
            
            assert response['statusCode'] == 200
            # Verify DynamoDB put_item was called
            mock_aws_services['dynamodb'].put_item.assert_called_once()
            call_args = mock_aws_services['dynamodb'].put_item.call_args
            assert call_args[1]['TableName'] == 'test-connections'
            item = call_args[1]['Item']
            assert item['connection_id']['S'] == 'conn_test_123'
            assert item['job_id']['S'] == '__pending__'
    
    def test_handle_connect_missing_table_name(self, mock_aws_services, mock_context, base_websocket_event):
        """Test connect when table name is not configured."""
        with patch.dict('os.environ', {'WEBSOCKET_CONNECTIONS_TABLE_NAME': ''}):
            response = websocket_api.handler(base_websocket_event, mock_context)
            
            assert response['statusCode'] == 200
            # Should not fail even if table name is missing
            mock_aws_services['dynamodb'].put_item.assert_not_called()
    
    def test_handle_connect_dynamodb_error(self, mock_aws_services, mock_context, base_websocket_event):
        """Test connect when DynamoDB write fails."""
        mock_aws_services['dynamodb'].put_item.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable'}},
            'PutItem'
        )
        
        with patch.dict('os.environ', {'WEBSOCKET_CONNECTIONS_TABLE_NAME': 'test-connections'}):
            # Should not fail - connection should still succeed
            response = websocket_api.handler(base_websocket_event, mock_context)
            assert response['statusCode'] == 200


class TestDisconnectHandler:
    """Test $disconnect event handler."""
    
    def test_handle_disconnect_success(self, mock_aws_services, mock_context, base_websocket_event):
        """Test successful disconnection."""
        base_websocket_event['requestContext']['routeKey'] = '$disconnect'
        
        # Mock query response
        mock_aws_services['dynamodb'].query.return_value = {
            'Items': [
                {
                    'connection_id': {'S': 'conn_test_123'},
                    'job_id': {'S': 'job_123'}
                },
                {
                    'connection_id': {'S': 'conn_test_123'},
                    'job_id': {'S': '__pending__'}
                }
            ]
        }
        
        with patch.dict('os.environ', {'WEBSOCKET_CONNECTIONS_TABLE_NAME': 'test-connections'}), \
             patch.object(websocket_api, 'WEBSOCKET_CONNECTIONS_TABLE_NAME', 'test-connections'), \
             patch.object(websocket_api, 'dynamodb', mock_aws_services['dynamodb']):
            response = websocket_api.handler(base_websocket_event, mock_context)
            
            assert response['statusCode'] == 200
            # Verify query was called
            assert mock_aws_services['dynamodb'].query.call_count >= 1
            # Verify delete_item was called for each connection record
            assert mock_aws_services['dynamodb'].delete_item.call_count >= 1
    
    def test_handle_disconnect_no_records(self, mock_aws_services, mock_context, base_websocket_event):
        """Test disconnect when no connection records exist."""
        base_websocket_event['requestContext']['routeKey'] = '$disconnect'
        mock_aws_services['dynamodb'].query.return_value = {'Items': []}
        
        with patch.dict('os.environ', {'WEBSOCKET_CONNECTIONS_TABLE_NAME': 'test-connections'}):
            response = websocket_api.handler(base_websocket_event, mock_context)
            
            assert response['statusCode'] == 200
            mock_aws_services['dynamodb'].delete_item.assert_not_called()


class TestDefaultHandler:
    """Test $default event handler (client messages)."""
    
    def test_handle_subscribe_success(self, mock_aws_services, mock_context, base_websocket_event):
        """Test successful subscribe message."""
        base_websocket_event['requestContext']['routeKey'] = '$default'
        base_websocket_event['body'] = json.dumps({
            'type': 'subscribe',
            'job_id': 'job_123'
        })
        
        # Mock job service
        mock_job = MagicMock()
        mock_job.status.value = 'pending'
        
        with patch('src.api.websocket_api.JobService') as mock_job_service_class, \
             patch.dict('os.environ', {'WEBSOCKET_CONNECTIONS_TABLE_NAME': 'test-connections'}), \
             patch.object(websocket_api, 'WEBSOCKET_CONNECTIONS_TABLE_NAME', 'test-connections'), \
             patch.object(websocket_api, 'dynamodb', mock_aws_services['dynamodb']):
            mock_job_service = MagicMock()
            mock_job_service.get_job.return_value = mock_job
            mock_job_service_class.return_value = mock_job_service
            
            # Mock DynamoDB operations
            mock_aws_services['dynamodb'].delete_item.side_effect = ClientError(
                {'Error': {'Code': 'ResourceNotFoundException'}},
                'DeleteItem'
            )
            
            response = websocket_api.handler(base_websocket_event, mock_context)
            
            assert response['statusCode'] == 200
            # Verify job service was called
            mock_job_service.get_job.assert_called_once_with('job_123')
            # Verify put_item was called to store connection
            mock_aws_services['dynamodb'].put_item.assert_called()
            # Verify message was sent
            mock_aws_services['apigateway'].post_to_connection.assert_called_once()
    
    def test_handle_subscribe_job_not_found(self, mock_aws_services, mock_context, base_websocket_event):
        """Test subscribe when job doesn't exist."""
        base_websocket_event['requestContext']['routeKey'] = '$default'
        base_websocket_event['body'] = json.dumps({
            'type': 'subscribe',
            'job_id': 'job_nonexistent'
        })
        
        with patch('src.api.websocket_api.JobService') as mock_job_service_class:
            from src.utils.errors import JobNotFoundError
            mock_job_service = MagicMock()
            mock_job_service.get_job.side_effect = JobNotFoundError('job_nonexistent')
            mock_job_service_class.return_value = mock_job_service
            
            with patch.dict('os.environ', {'WEBSOCKET_CONNECTIONS_TABLE_NAME': 'test-connections'}):
                response = websocket_api.handler(base_websocket_event, mock_context)
                
                assert response['statusCode'] == 200
                # Verify error message was sent
                mock_aws_services['apigateway'].post_to_connection.assert_called_once()
                call_args = mock_aws_services['apigateway'].post_to_connection.call_args
                sent_data = json.loads(call_args[1]['Data'].decode('utf-8'))
                assert sent_data['type'] == 'error'
    
    def test_handle_cancel_job_success(self, mock_aws_services, mock_context, base_websocket_event):
        """Test successful cancel_job message."""
        base_websocket_event['requestContext']['routeKey'] = '$default'
        base_websocket_event['body'] = json.dumps({
            'type': 'cancel_job',
            'job_id': 'job_123'
        })
        
        mock_cancelled_job = MagicMock()
        mock_cancelled_job.status.value = 'cancelled'
        
        with patch('src.api.websocket_api.JobService') as mock_job_service_class:
            mock_job_service = MagicMock()
            mock_job_service.cancel_job.return_value = mock_cancelled_job
            mock_job_service_class.return_value = mock_job_service
            
            with patch.dict('os.environ', {'WEBSOCKET_CONNECTIONS_TABLE_NAME': 'test-connections'}):
                response = websocket_api.handler(base_websocket_event, mock_context)
                
                assert response['statusCode'] == 200
                mock_job_service.cancel_job.assert_called_once_with('job_123')
                mock_aws_services['apigateway'].post_to_connection.assert_called_once()
                call_args = mock_aws_services['apigateway'].post_to_connection.call_args
                sent_data = json.loads(call_args[1]['Data'].decode('utf-8'))
                assert sent_data['type'] == 'job_cancelled'
    
    def test_handle_request_status_success(self, mock_aws_services, mock_context, base_websocket_event):
        """Test successful request_status message."""
        base_websocket_event['requestContext']['routeKey'] = '$default'
        base_websocket_event['body'] = json.dumps({
            'type': 'request_status',
            'job_id': 'job_123'
        })
        
        mock_job = MagicMock()
        mock_job.status.value = 'processing'
        mock_job.created_at = '2024-01-15T10:30:00Z'
        mock_job.updated_at = '2024-01-15T10:30:15Z'
        mock_job.blueprint_format = 'pdf'
        mock_job.result_s3_key = None
        mock_job.error = None
        
        with patch('src.api.websocket_api.JobService') as mock_job_service_class:
            mock_job_service = MagicMock()
            mock_job_service.get_job.return_value = mock_job
            mock_job_service_class.return_value = mock_job_service
            
            with patch.dict('os.environ', {'WEBSOCKET_CONNECTIONS_TABLE_NAME': 'test-connections'}):
                response = websocket_api.handler(base_websocket_event, mock_context)
                
                assert response['statusCode'] == 200
                mock_job_service.get_job.assert_called_once_with('job_123')
                mock_aws_services['apigateway'].post_to_connection.assert_called_once()
                call_args = mock_aws_services['apigateway'].post_to_connection.call_args
                sent_data = json.loads(call_args[1]['Data'].decode('utf-8'))
                assert sent_data['type'] == 'job_status'
                assert sent_data['status'] == 'processing'
    
    def test_handle_invalid_message_type(self, mock_aws_services, mock_context, base_websocket_event):
        """Test handling of invalid message type."""
        base_websocket_event['requestContext']['routeKey'] = '$default'
        base_websocket_event['body'] = json.dumps({
            'type': 'invalid_type',
            'job_id': 'job_123'
        })
        
        with patch.dict('os.environ', {'WEBSOCKET_CONNECTIONS_TABLE_NAME': 'test-connections'}):
            response = websocket_api.handler(base_websocket_event, mock_context)
            
            assert response['statusCode'] == 200
            mock_aws_services['apigateway'].post_to_connection.assert_called_once()
            call_args = mock_aws_services['apigateway'].post_to_connection.call_args
            sent_data = json.loads(call_args[1]['Data'].decode('utf-8'))
            assert sent_data['type'] == 'error'
    
    def test_handle_invalid_json(self, mock_aws_services, mock_context, base_websocket_event):
        """Test handling of invalid JSON."""
        base_websocket_event['requestContext']['routeKey'] = '$default'
        base_websocket_event['body'] = 'invalid json'
        
        with patch.dict('os.environ', {'WEBSOCKET_CONNECTIONS_TABLE_NAME': 'test-connections'}):
            response = websocket_api.handler(base_websocket_event, mock_context)
            
            assert response['statusCode'] == 200
            mock_aws_services['apigateway'].post_to_connection.assert_called_once()
            call_args = mock_aws_services['apigateway'].post_to_connection.call_args
            sent_data = json.loads(call_args[1]['Data'].decode('utf-8'))
            assert sent_data['type'] == 'error'
    
    def test_handle_empty_body(self, mock_aws_services, mock_context, base_websocket_event):
        """Test handling of empty message body."""
        base_websocket_event['requestContext']['routeKey'] = '$default'
        base_websocket_event['body'] = ''
        
        with patch.dict('os.environ', {'WEBSOCKET_CONNECTIONS_TABLE_NAME': 'test-connections'}):
            response = websocket_api.handler(base_websocket_event, mock_context)
            
            assert response['statusCode'] == 200
            mock_aws_services['apigateway'].post_to_connection.assert_called_once()
            call_args = mock_aws_services['apigateway'].post_to_connection.call_args
            sent_data = json.loads(call_args[1]['Data'].decode('utf-8'))
            assert sent_data['type'] == 'error'
    
    def test_handle_missing_job_id(self, mock_aws_services, mock_context, base_websocket_event):
        """Test handling of message with missing job_id."""
        base_websocket_event['requestContext']['routeKey'] = '$default'
        base_websocket_event['body'] = json.dumps({
            'type': 'subscribe'
            # Missing job_id
        })
        
        with patch.dict('os.environ', {'WEBSOCKET_CONNECTIONS_TABLE_NAME': 'test-connections'}):
            response = websocket_api.handler(base_websocket_event, mock_context)
            
            assert response['statusCode'] == 200
            mock_aws_services['apigateway'].post_to_connection.assert_called_once()
            call_args = mock_aws_services['apigateway'].post_to_connection.call_args
            sent_data = json.loads(call_args[1]['Data'].decode('utf-8'))
            assert sent_data['type'] == 'error'


class TestHelperFunctions:
    """Test helper functions."""
    
    def test_extract_connection_id_success(self, base_websocket_event):
        """Test successful connection ID extraction."""
        connection_id = websocket_api.extract_connection_id(base_websocket_event)
        assert connection_id == 'conn_test_123'
    
    def test_extract_connection_id_missing(self):
        """Test connection ID extraction when missing."""
        event = {'requestContext': {}}
        with pytest.raises(websocket_api.WebSocketError, match='Connection ID not found'):
            websocket_api.extract_connection_id(event)
    
    def test_get_apigateway_management_api_success(self, base_websocket_event):
        """Test API Gateway Management API client creation."""
        with patch('src.api.websocket_api.boto3') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client
            
            # Reset the global variable
            websocket_api.apigateway_management_api = None
            
            client = websocket_api.get_apigateway_management_api(base_websocket_event)
            
            assert client == mock_client
            mock_boto3.client.assert_called_once()
    
    def test_get_apigateway_management_api_missing_domain(self):
        """Test API Gateway client creation with missing domain."""
        event = {
            'requestContext': {
                'stage': 'api'
                # Missing domainName
            }
        }
        with pytest.raises(websocket_api.WebSocketError, match='Missing domain or stage'):
            websocket_api.get_apigateway_management_api(event)
    
    def test_unknown_route_key(self, mock_aws_services, mock_context, base_websocket_event):
        """Test handler with unknown route key."""
        base_websocket_event['requestContext']['routeKey'] = '$unknown'
        
        response = websocket_api.handler(base_websocket_event, mock_context)
        
        assert response['statusCode'] == 200

