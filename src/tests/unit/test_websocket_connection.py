"""
Unit tests for WebSocket connection model.
"""
import pytest
from datetime import datetime, timezone

from src.models.websocket_connection import WebSocketConnection, ConnectionStatus


class TestWebSocketConnection:
    """Test WebSocketConnection model."""
    
    def test_connection_creation(self):
        """Test connection creation."""
        connection = WebSocketConnection(
            connection_id='conn_123',
            job_id='job_456'
        )
        
        assert connection.connection_id == 'conn_123'
        assert connection.job_id == 'job_456'
        assert connection.status == ConnectionStatus.CONNECTED
        assert connection.created_at is not None
        assert connection.last_activity is not None
        assert connection.expires_at is not None
    
    def test_connection_creation_missing_connection_id(self):
        """Test connection creation with missing connection_id."""
        with pytest.raises(ValueError, match='connection_id is required'):
            WebSocketConnection(connection_id='', job_id='job_456')
    
    def test_connection_creation_missing_job_id(self):
        """Test connection creation with missing job_id."""
        with pytest.raises(ValueError, match='job_id is required'):
            WebSocketConnection(connection_id='conn_123', job_id='')
    
    def test_connection_to_dynamodb_item(self):
        """Test connection to DynamoDB item conversion."""
        connection = WebSocketConnection(
            connection_id='conn_123',
            job_id='job_456',
            status=ConnectionStatus.SUBSCRIBED
        )
        
        item = connection.to_dynamodb_item()
        assert item['connection_id']['S'] == 'conn_123'
        assert item['job_id']['S'] == 'job_456'
        assert item['status']['S'] == ConnectionStatus.SUBSCRIBED
        assert 'expires_at' in item
        assert isinstance(item['expires_at']['N'], str)
    
    def test_connection_from_dynamodb_item(self):
        """Test connection from DynamoDB item creation."""
        item = {
            'connection_id': {'S': 'conn_123'},
            'job_id': {'S': 'job_456'},
            'created_at': {'S': '2024-01-15T10:30:00Z'},
            'last_activity': {'S': '2024-01-15T10:30:00Z'},
            'status': {'S': ConnectionStatus.SUBSCRIBED},
            'expires_at': {'N': '1234567890'}
        }
        
        connection = WebSocketConnection.from_dynamodb_item(item)
        assert connection.connection_id == 'conn_123'
        assert connection.job_id == 'job_456'
        assert connection.status == ConnectionStatus.SUBSCRIBED
        assert connection.expires_at == 1234567890
    
    def test_connection_from_dynamodb_item_missing_connection_id(self):
        """Test from_dynamodb_item with missing connection_id."""
        item = {
            'job_id': {'S': 'job_456'}
        }
        
        with pytest.raises(ValueError, match='connection_id is required'):
            WebSocketConnection.from_dynamodb_item(item)
    
    def test_connection_from_dynamodb_item_missing_job_id(self):
        """Test from_dynamodb_item with missing job_id."""
        item = {
            'connection_id': {'S': 'conn_123'}
        }
        
        with pytest.raises(ValueError, match='job_id is required'):
            WebSocketConnection.from_dynamodb_item(item)
    
    def test_update_activity(self):
        """Test updating last_activity timestamp."""
        connection = WebSocketConnection(
            connection_id='conn_123',
            job_id='job_456'
        )
        
        original_activity = connection.last_activity
        connection.update_activity()
        
        assert connection.last_activity != original_activity
        assert connection.last_activity is not None
    
    def test_connection_to_dict(self):
        """Test connection to dictionary conversion."""
        connection = WebSocketConnection(
            connection_id='conn_123',
            job_id='job_456',
            status=ConnectionStatus.SUBSCRIBED
        )
        
        connection_dict = connection.to_dict()
        assert connection_dict['connection_id'] == 'conn_123'
        assert connection_dict['job_id'] == 'job_456'
        assert connection_dict['status'] == ConnectionStatus.SUBSCRIBED
        assert 'created_at' in connection_dict
        assert 'last_activity' in connection_dict
        assert 'expires_at' in connection_dict
    
    def test_connection_repr(self):
        """Test connection string representation."""
        connection = WebSocketConnection(
            connection_id='conn_123',
            job_id='job_456',
            status=ConnectionStatus.SUBSCRIBED
        )
        
        repr_str = repr(connection)
        assert 'conn_123' in repr_str
        assert 'job_456' in repr_str
        assert ConnectionStatus.SUBSCRIBED in repr_str



