"""
Unit tests for WebSocket service.
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from src.services.websocket_service import WebSocketService


@pytest.fixture
def mock_aws_services():
    """Mock AWS services."""
    with patch('src.services.websocket_service.boto3') as mock_boto3:
        mock_dynamodb = MagicMock()
        mock_apigateway = MagicMock()
        
        def client_side_effect(service, **kwargs):
            if service == 'dynamodb':
                return mock_dynamodb
            elif service == 'apigatewaymanagementapi':
                return mock_apigateway
            return MagicMock()
        
        mock_boto3.client.side_effect = client_side_effect
        
        yield {
            'dynamodb': mock_dynamodb,
            'apigateway': mock_apigateway
        }


@pytest.fixture
def websocket_service(mock_aws_services):
    """Create WebSocketService instance with mocked AWS services."""
    with patch.dict('os.environ', {
        'WEBSOCKET_CONNECTIONS_TABLE_NAME': 'test-websocket-connections'
    }):
        service = WebSocketService(
            websocket_connections_table_name='test-websocket-connections'
        )
        # Inject mocked clients
        service.dynamodb = mock_aws_services['dynamodb']
        service._apigateway_client = mock_aws_services['apigateway']
        return service


class TestGetConnectionsForJob:
    """Test get_connections_for_job method."""
    
    def test_get_connections_success(self, websocket_service, mock_aws_services):
        """Test successful connection retrieval."""
        mock_aws_services['dynamodb'].query.return_value = {
            'Items': [
                {
                    'connection_id': {'S': 'conn_1'},
                    'job_id': {'S': 'job_123'}
                },
                {
                    'connection_id': {'S': 'conn_2'},
                    'job_id': {'S': 'job_123'}
                }
            ]
        }
        
        connections = websocket_service.get_connections_for_job('job_123')
        
        assert len(connections) == 2
        assert 'conn_1' in connections
        assert 'conn_2' in connections
        mock_aws_services['dynamodb'].query.assert_called_once()
        # Verify GSI was used
        call_args = mock_aws_services['dynamodb'].query.call_args
        assert call_args[1]['IndexName'] == 'JobIdIndex'
    
    def test_get_connections_empty(self, websocket_service, mock_aws_services):
        """Test connection retrieval with no connections."""
        mock_aws_services['dynamodb'].query.return_value = {'Items': []}
        
        connections = websocket_service.get_connections_for_job('job_123')
        
        assert len(connections) == 0
    
    def test_get_connections_cached(self, websocket_service, mock_aws_services):
        """Test connection caching."""
        mock_aws_services['dynamodb'].query.return_value = {
            'Items': [
                {'connection_id': {'S': 'conn_1'}, 'job_id': {'S': 'job_123'}}
            ]
        }
        
        # First call
        connections1 = websocket_service.get_connections_for_job('job_123')
        assert len(connections1) == 1
        
        # Second call should use cache
        connections2 = websocket_service.get_connections_for_job('job_123')
        assert len(connections2) == 1
        
        # Should only call query once
        assert mock_aws_services['dynamodb'].query.call_count == 1
    
    def test_get_connections_error(self, websocket_service, mock_aws_services):
        """Test connection retrieval with error."""
        mock_aws_services['dynamodb'].query.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable'}},
            'Query'
        )
        
        connections = websocket_service.get_connections_for_job('job_123')
        
        assert len(connections) == 0


class TestSendMessage:
    """Test send_message method."""
    
    def test_send_message_success(self, websocket_service, mock_aws_services):
        """Test successful message sending."""
        message = {'type': 'progress_update', 'job_id': 'job_123'}
        
        result = websocket_service.send_message('conn_1', message)
        
        assert result is True
        mock_aws_services['apigateway'].post_to_connection.assert_called_once()
    
    def test_send_message_gone_exception(self, websocket_service, mock_aws_services):
        """Test message sending with GoneException."""
        mock_aws_services['apigateway'].post_to_connection.side_effect = ClientError(
            {'Error': {'Code': 'GoneException'}},
            'PostToConnection'
        )
        
        message = {'type': 'progress_update', 'job_id': 'job_123'}
        result = websocket_service.send_message('conn_1', message)
        
        assert result is False
    
    def test_send_message_retryable_error(self, websocket_service, mock_aws_services):
        """Test message sending with retryable error."""
        mock_aws_services['apigateway'].post_to_connection.side_effect = [
            ClientError({'Error': {'Code': 'Throttling'}}, 'PostToConnection'),
            None  # Success on retry
        ]
        
        message = {'type': 'progress_update', 'job_id': 'job_123'}
        result = websocket_service.send_message('conn_1', message)
        
        assert result is True
        assert mock_aws_services['apigateway'].post_to_connection.call_count == 2


class TestSendMessageToJob:
    """Test send_message_to_job method."""
    
    def test_send_message_to_job_success(self, websocket_service, mock_aws_services):
        """Test successful message sending to job."""
        mock_aws_services['dynamodb'].query.return_value = {
            'Items': [
                {'connection_id': {'S': 'conn_1'}, 'job_id': {'S': 'job_123'}},
                {'connection_id': {'S': 'conn_2'}, 'job_id': {'S': 'job_123'}}
            ]
        }
        
        message = {'type': 'progress_update', 'job_id': 'job_123'}
        count = websocket_service.send_message_to_job('job_123', message)
        
        assert count == 2
        assert mock_aws_services['apigateway'].post_to_connection.call_count == 2
    
    def test_send_message_to_job_no_connections(self, websocket_service, mock_aws_services):
        """Test message sending with no connections."""
        mock_aws_services['dynamodb'].query.return_value = {'Items': []}
        
        message = {'type': 'progress_update', 'job_id': 'job_123'}
        count = websocket_service.send_message_to_job('job_123', message)
        
        assert count == 0


class TestProgressUpdateMessages:
    """Test progress update message methods."""
    
    def test_send_progress_update(self, websocket_service, mock_aws_services):
        """Test sending progress update."""
        mock_aws_services['dynamodb'].query.return_value = {
            'Items': [
                {'connection_id': {'S': 'conn_1'}, 'job_id': {'S': 'job_123'}}
            ]
        }
        
        count = websocket_service.send_progress_update(
            job_id='job_123',
            stage='stage_1',
            progress=50,
            message='Processing...',
            estimated_seconds_remaining=10
        )
        
        assert count == 1
        call_args = mock_aws_services['apigateway'].post_to_connection.call_args
        sent_data = json.loads(call_args[1]['Data'].decode('utf-8'))
        assert sent_data['type'] == 'progress_update'
        assert sent_data['job_id'] == 'job_123'
        assert sent_data['stage'] == 'stage_1'
        assert sent_data['progress'] == 50
        assert sent_data['estimated_seconds_remaining'] == 10
    
    def test_send_stage_complete(self, websocket_service, mock_aws_services):
        """Test sending stage complete."""
        mock_aws_services['dynamodb'].query.return_value = {
            'Items': [
                {'connection_id': {'S': 'conn_1'}, 'job_id': {'S': 'job_123'}}
            ]
        }
        
        results = {'rooms': []}
        count = websocket_service.send_stage_complete(
            job_id='job_123',
            stage='stage_1',
            results=results
        )
        
        assert count == 1
        call_args = mock_aws_services['apigateway'].post_to_connection.call_args
        sent_data = json.loads(call_args[1]['Data'].decode('utf-8'))
        assert sent_data['type'] == 'stage_complete'
        assert sent_data['stage'] == 'stage_1'
        assert sent_data['results'] == results
    
    def test_send_job_complete(self, websocket_service, mock_aws_services):
        """Test sending job complete."""
        mock_aws_services['dynamodb'].query.return_value = {
            'Items': [
                {'connection_id': {'S': 'conn_1'}, 'job_id': {'S': 'job_123'}}
            ]
        }
        
        results = {'rooms': []}
        count = websocket_service.send_job_complete(
            job_id='job_123',
            results=results
        )
        
        assert count == 1
        call_args = mock_aws_services['apigateway'].post_to_connection.call_args
        sent_data = json.loads(call_args[1]['Data'].decode('utf-8'))
        assert sent_data['type'] == 'job_complete'
        assert sent_data['results'] == results
    
    def test_send_job_failed(self, websocket_service, mock_aws_services):
        """Test sending job failed."""
        mock_aws_services['dynamodb'].query.return_value = {
            'Items': [
                {'connection_id': {'S': 'conn_1'}, 'job_id': {'S': 'job_123'}}
            ]
        }
        
        error = {'code': 'PROCESSING_ERROR', 'message': 'Processing failed'}
        count = websocket_service.send_job_failed(
            job_id='job_123',
            error=error
        )
        
        assert count == 1
        call_args = mock_aws_services['apigateway'].post_to_connection.call_args
        sent_data = json.loads(call_args[1]['Data'].decode('utf-8'))
        assert sent_data['type'] == 'job_failed'
        assert sent_data['error'] == error
    
    def test_send_job_cancelled(self, websocket_service, mock_aws_services):
        """Test sending job cancelled."""
        mock_aws_services['dynamodb'].query.return_value = {
            'Items': [
                {'connection_id': {'S': 'conn_1'}, 'job_id': {'S': 'job_123'}}
            ]
        }
        
        count = websocket_service.send_job_cancelled(job_id='job_123')
        
        assert count == 1
        call_args = mock_aws_services['apigateway'].post_to_connection.call_args
        sent_data = json.loads(call_args[1]['Data'].decode('utf-8'))
        assert sent_data['type'] == 'job_cancelled'

