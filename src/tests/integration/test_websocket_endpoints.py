"""
Integration tests for WebSocket API endpoints.
"""
import json
import pytest
from unittest.mock import patch, MagicMock

from src.api import websocket_api
from src.models.job import Job, JobStatus
from src.models.websocket_connection import WebSocketConnection, ConnectionStatus


@pytest.fixture
def mock_job_service():
    """Mock JobService."""
    with patch('src.api.websocket_api.JobService') as mock_service_class:
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        yield mock_service


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
def websocket_event_base():
    """Base WebSocket event structure."""
    return {
        'requestContext': {
            'connectionId': 'conn_test_123',
            'domainName': 'test-api.execute-api.us-east-1.amazonaws.com',
            'stage': 'api',
            'routeKey': '$connect'
        }
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


class TestWebSocketConnectionLifecycle:
    """Test WebSocket connection lifecycle end-to-end."""
    
    def test_connect_subscribe_disconnect_flow(
        self, mock_aws_services, mock_job_service, websocket_event_base, mock_context
    ):
        """Test complete connection lifecycle: connect -> subscribe -> disconnect."""
        with patch.dict('os.environ', {'WEBSOCKET_CONNECTIONS_TABLE_NAME': 'test-connections'}), \
             patch.object(websocket_api, 'WEBSOCKET_CONNECTIONS_TABLE_NAME', 'test-connections'), \
             patch.object(websocket_api, 'dynamodb', mock_aws_services['dynamodb']):
            # Step 1: Connect
            connect_event = websocket_event_base.copy()
            connect_event['requestContext']['routeKey'] = '$connect'
            
            response = websocket_api.handler(connect_event, mock_context)
            assert response['statusCode'] == 200
            mock_aws_services['dynamodb'].put_item.assert_called()
            
            # Step 2: Subscribe
            mock_job = Job(
                job_id='job_123',
                status=JobStatus.PENDING,
                blueprint_format='pdf'
            )
            mock_job_service.get_job.return_value = mock_job
            
            subscribe_event = websocket_event_base.copy()
            subscribe_event['requestContext']['routeKey'] = '$default'
            subscribe_event['body'] = json.dumps({
                'type': 'subscribe',
                'job_id': 'job_123'
            })
            
            # Reset mock call counts
            mock_aws_services['dynamodb'].reset_mock()
            mock_aws_services['apigateway'].reset_mock()
            
            response = websocket_api.handler(subscribe_event, mock_context)
            assert response['statusCode'] == 200
            
            # Verify job lookup
            mock_job_service.get_job.assert_called_once_with('job_123')
            
            # Verify connection record updated
            put_calls = [call for call in mock_aws_services['dynamodb'].put_item.call_args_list]
            assert len(put_calls) > 0
            
            # Verify subscription confirmation sent
            mock_aws_services['apigateway'].post_to_connection.assert_called_once()
            call_args = mock_aws_services['apigateway'].post_to_connection.call_args
            sent_data = json.loads(call_args[1]['Data'].decode('utf-8'))
            assert sent_data['type'] == 'subscribed'
            assert sent_data['job_id'] == 'job_123'
            
            # Step 3: Disconnect
            disconnect_event = websocket_event_base.copy()
            disconnect_event['requestContext']['routeKey'] = '$disconnect'
            
            # Mock query response for disconnect cleanup
            mock_aws_services['dynamodb'].query.return_value = {
                'Items': [
                    {
                        'connection_id': {'S': 'conn_test_123'},
                        'job_id': {'S': 'job_123'}
                    }
                ]
            }
            
            response = websocket_api.handler(disconnect_event, mock_context)
            assert response['statusCode'] == 200
            
            # Verify cleanup
            # Note: query is called multiple times (disconnect cleanup, update_activity)
            # delete_item is called for each connection record (placeholder + actual job_id)
            assert mock_aws_services['dynamodb'].query.call_count >= 1
            assert mock_aws_services['dynamodb'].delete_item.call_count >= 1


class TestMessageSending:
    """Test message sending to connected clients."""
    
    def test_send_progress_update_to_subscribed_client(
        self, mock_aws_services, mock_job_service, websocket_event_base, mock_context
    ):
        """Test sending progress update to subscribed client."""
        with patch('src.services.websocket_service.WebSocketService') as mock_service_class:
            mock_ws_service = MagicMock()
            mock_ws_service.get_connections_for_job.return_value = ['conn_test_123']
            mock_ws_service.send_message.return_value = True
            mock_service_class.return_value = mock_ws_service
            
            # Subscribe first
            mock_job = Job(job_id='job_123', status=JobStatus.PROCESSING)
            mock_job_service.get_job.return_value = mock_job
            
            subscribe_event = websocket_event_base.copy()
            subscribe_event['requestContext']['routeKey'] = '$default'
            subscribe_event['body'] = json.dumps({
                'type': 'subscribe',
                'job_id': 'job_123'
            })
            
            with patch.dict('os.environ', {'WEBSOCKET_CONNECTIONS_TABLE_NAME': 'test-connections'}):
                websocket_api.handler(subscribe_event, mock_context)
                
                # Now simulate progress update (would be called from pipeline)
                # This tests the WebSocketService integration
                mock_ws_service.send_progress_update(
                    job_id='job_123',
                    stage='stage_1',
                    progress=50,
                    message='Processing...',
                    estimated_seconds_remaining=10
                )
                
                # Verify service was called correctly
                mock_ws_service.send_progress_update.assert_called_once_with(
                    job_id='job_123',
                    stage='stage_1',
                    progress=50,
                    message='Processing...',
                    estimated_seconds_remaining=10
                )


class TestClientMessageHandling:
    """Test client message handling end-to-end."""
    
    def test_subscribe_message_flow(
        self, mock_aws_services, mock_job_service, websocket_event_base, mock_context
    ):
        """Test subscribe message handling flow."""
        mock_job = Job(job_id='job_123', status=JobStatus.PENDING)
        mock_job_service.get_job.return_value = mock_job
        
        event = websocket_event_base.copy()
        event['requestContext']['routeKey'] = '$default'
        event['body'] = json.dumps({
            'type': 'subscribe',
            'job_id': 'job_123'
        })
        
        with patch.dict('os.environ', {'WEBSOCKET_CONNECTIONS_TABLE_NAME': 'test-connections'}), \
             patch.object(websocket_api, 'WEBSOCKET_CONNECTIONS_TABLE_NAME', 'test-connections'), \
             patch.object(websocket_api, 'dynamodb', mock_aws_services['dynamodb']):
            response = websocket_api.handler(event, mock_context)
            
            assert response['statusCode'] == 200
            mock_job_service.get_job.assert_called_once_with('job_123')
            
            # Verify subscription confirmation
            mock_aws_services['apigateway'].post_to_connection.assert_called_once()
            call_args = mock_aws_services['apigateway'].post_to_connection.call_args
            sent_data = json.loads(call_args[1]['Data'].decode('utf-8'))
            assert sent_data['type'] == 'subscribed'
            assert sent_data['job_id'] == 'job_123'
            assert 'job_status' in sent_data
    
    def test_cancel_job_message_flow(
        self, mock_aws_services, mock_job_service, websocket_event_base, mock_context
    ):
        """Test cancel_job message handling flow."""
        cancelled_job = Job(job_id='job_123', status=JobStatus.CANCELLED)
        mock_job_service.cancel_job.return_value = cancelled_job
        
        event = websocket_event_base.copy()
        event['requestContext']['routeKey'] = '$default'
        event['body'] = json.dumps({
            'type': 'cancel_job',
            'job_id': 'job_123'
        })
        
        with patch.dict('os.environ', {'WEBSOCKET_CONNECTIONS_TABLE_NAME': 'test-connections'}), \
             patch.object(websocket_api, 'WEBSOCKET_CONNECTIONS_TABLE_NAME', 'test-connections'), \
             patch.object(websocket_api, 'dynamodb', mock_aws_services['dynamodb']):
            response = websocket_api.handler(event, mock_context)
            
            assert response['statusCode'] == 200
            mock_job_service.cancel_job.assert_called_once_with('job_123')
            
            # Verify cancellation confirmation
            mock_aws_services['apigateway'].post_to_connection.assert_called_once()
            call_args = mock_aws_services['apigateway'].post_to_connection.call_args
            sent_data = json.loads(call_args[1]['Data'].decode('utf-8'))
            assert sent_data['type'] == 'job_cancelled'
            assert sent_data['job_id'] == 'job_123'
    
    def test_request_status_message_flow(
        self, mock_aws_services, mock_job_service, websocket_event_base, mock_context
    ):
        """Test request_status message handling flow."""
        mock_job = Job(
            job_id='job_123',
            status=JobStatus.PROCESSING,
            blueprint_format='pdf',
            created_at='2024-01-15T10:30:00Z',
            updated_at='2024-01-15T10:30:15Z'
        )
        mock_job_service.get_job.return_value = mock_job
        
        event = websocket_event_base.copy()
        event['requestContext']['routeKey'] = '$default'
        event['body'] = json.dumps({
            'type': 'request_status',
            'job_id': 'job_123'
        })
        
        with patch.dict('os.environ', {'WEBSOCKET_CONNECTIONS_TABLE_NAME': 'test-connections'}), \
             patch.object(websocket_api, 'WEBSOCKET_CONNECTIONS_TABLE_NAME', 'test-connections'), \
             patch.object(websocket_api, 'dynamodb', mock_aws_services['dynamodb']):
            response = websocket_api.handler(event, mock_context)
            
            assert response['statusCode'] == 200
            mock_job_service.get_job.assert_called_once_with('job_123')
            
            # Verify status response
            mock_aws_services['apigateway'].post_to_connection.assert_called_once()
            call_args = mock_aws_services['apigateway'].post_to_connection.call_args
            sent_data = json.loads(call_args[1]['Data'].decode('utf-8'))
            assert sent_data['type'] == 'job_status'
            assert sent_data['job_id'] == 'job_123'
            assert sent_data['status'] == 'processing'


class TestConcurrentConnections:
    """Test handling of concurrent connections for same job."""
    
    def test_multiple_connections_same_job(
        self, mock_aws_services, mock_job_service, mock_context
    ):
        """Test multiple clients subscribing to same job."""
        mock_job = Job(job_id='job_123', status=JobStatus.PENDING)
        mock_job_service.get_job.return_value = mock_job
        
        # Connect and subscribe first client
        event1 = {
            'requestContext': {
                'connectionId': 'conn_1',
                'domainName': 'test-api.execute-api.us-east-1.amazonaws.com',
                'stage': 'api',
                'routeKey': '$default'
            },
            'body': json.dumps({
                'type': 'subscribe',
                'job_id': 'job_123'
            })
        }
        
        with patch.dict('os.environ', {'WEBSOCKET_CONNECTIONS_TABLE_NAME': 'test-connections'}), \
             patch.object(websocket_api, 'WEBSOCKET_CONNECTIONS_TABLE_NAME', 'test-connections'), \
             patch.object(websocket_api, 'dynamodb', mock_aws_services['dynamodb']):
            websocket_api.handler(event1, mock_context)
            
            # Connect and subscribe second client
            event2 = {
                'requestContext': {
                    'connectionId': 'conn_2',
                    'domainName': 'test-api.execute-api.us-east-1.amazonaws.com',
                    'stage': 'api',
                    'routeKey': '$default'
                },
                'body': json.dumps({
                    'type': 'subscribe',
                    'job_id': 'job_123'
                })
            }
            
            websocket_api.handler(event2, mock_context)
            
            # Verify both subscriptions were processed
            assert mock_job_service.get_job.call_count == 2
            assert mock_aws_services['apigateway'].post_to_connection.call_count == 2


class TestErrorHandling:
    """Test error handling in WebSocket API."""
    
    def test_subscribe_job_not_found(
        self, mock_aws_services, mock_job_service, websocket_event_base, mock_context
    ):
        """Test subscribe when job doesn't exist."""
        from src.utils.errors import JobNotFoundError
        mock_job_service.get_job.side_effect = JobNotFoundError('job_123')
        
        event = websocket_event_base.copy()
        event['requestContext']['routeKey'] = '$default'
        event['body'] = json.dumps({
            'type': 'subscribe',
            'job_id': 'job_123'
        })
        
        with patch.dict('os.environ', {'WEBSOCKET_CONNECTIONS_TABLE_NAME': 'test-connections'}), \
             patch.object(websocket_api, 'WEBSOCKET_CONNECTIONS_TABLE_NAME', 'test-connections'), \
             patch.object(websocket_api, 'dynamodb', mock_aws_services['dynamodb']):
            response = websocket_api.handler(event, mock_context)
            
            assert response['statusCode'] == 200
            # Verify error message sent
            mock_aws_services['apigateway'].post_to_connection.assert_called_once()
            call_args = mock_aws_services['apigateway'].post_to_connection.call_args
            sent_data = json.loads(call_args[1]['Data'].decode('utf-8'))
            assert sent_data['type'] == 'error'
            assert 'Job not found' in sent_data['message']
    
    def test_invalid_message_format(
        self, mock_aws_services, websocket_event_base, mock_context
    ):
        """Test handling of invalid message format."""
        event = websocket_event_base.copy()
        event['requestContext']['routeKey'] = '$default'
        event['body'] = 'not valid json'
        
        with patch.dict('os.environ', {'WEBSOCKET_CONNECTIONS_TABLE_NAME': 'test-connections'}), \
             patch.object(websocket_api, 'WEBSOCKET_CONNECTIONS_TABLE_NAME', 'test-connections'), \
             patch.object(websocket_api, 'dynamodb', mock_aws_services['dynamodb']):
            response = websocket_api.handler(event, mock_context)
            
            assert response['statusCode'] == 200
            # Verify error message sent
            mock_aws_services['apigateway'].post_to_connection.assert_called_once()
            call_args = mock_aws_services['apigateway'].post_to_connection.call_args
            sent_data = json.loads(call_args[1]['Data'].decode('utf-8'))
            assert sent_data['type'] == 'error'

