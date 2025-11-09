"""
WebSocket connection data model for Location Detection AI service.

This module defines the WebSocketConnection model for storing connection
mappings between connection IDs and job IDs.
"""
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import uuid


# TTL configuration
CONNECTION_TTL_HOURS = 1


class ConnectionStatus(str):
    """Connection status constants."""
    CONNECTED = 'connected'
    SUBSCRIBED = 'subscribed'
    DISCONNECTED = 'disconnected'


class WebSocketConnection:
    """
    WebSocket connection model representing a connection-to-job mapping.
    
    Attributes:
        connection_id: WebSocket connection ID from API Gateway
        job_id: Job ID that this connection is subscribed to
        created_at: ISO 8601 timestamp when connection was created
        last_activity: ISO 8601 timestamp of last activity
        status: Connection status (connected, subscribed, disconnected)
        expires_at: Unix timestamp for TTL expiration
    """
    
    def __init__(
        self,
        connection_id: str,
        job_id: str,
        created_at: Optional[str] = None,
        last_activity: Optional[str] = None,
        status: str = ConnectionStatus.CONNECTED,
        expires_at: Optional[int] = None
    ):
        """
        Initialize WebSocketConnection instance.
        
        Args:
            connection_id: WebSocket connection ID (required)
            job_id: Job ID (required)
            created_at: ISO 8601 timestamp (auto-generated if None)
            last_activity: ISO 8601 timestamp (auto-generated if None)
            status: Connection status (default: connected)
            expires_at: Unix timestamp for TTL (auto-generated if None)
        """
        if not connection_id:
            raise ValueError('connection_id is required')
        if not job_id:
            raise ValueError('job_id is required')
        
        self.connection_id = connection_id
        self.job_id = job_id
        
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        
        self.created_at = created_at or now_iso
        self.last_activity = last_activity or now_iso
        self.status = status
        
        # Calculate expires_at if not provided
        if expires_at is None:
            expires_at = int((now + timedelta(hours=CONNECTION_TTL_HOURS)).timestamp())
        self.expires_at = expires_at
    
    def to_dynamodb_item(self) -> Dict[str, Any]:
        """
        Convert connection to DynamoDB item format.
        
        Returns:
            Dictionary with DynamoDB attribute types
        """
        return {
            'connection_id': {'S': self.connection_id},
            'job_id': {'S': self.job_id},
            'created_at': {'S': self.created_at},
            'last_activity': {'S': self.last_activity},
            'status': {'S': self.status},
            'expires_at': {'N': str(self.expires_at)}
        }
    
    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> 'WebSocketConnection':
        """
        Create WebSocketConnection from DynamoDB item.
        
        Args:
            item: DynamoDB item dictionary
            
        Returns:
            WebSocketConnection instance
            
        Raises:
            ValueError: If required fields are missing
        """
        connection_id = item.get('connection_id', {}).get('S')
        job_id = item.get('job_id', {}).get('S')
        
        if not connection_id:
            raise ValueError('connection_id is required in DynamoDB item')
        if not job_id:
            raise ValueError('job_id is required in DynamoDB item')
        
        created_at = item.get('created_at', {}).get('S')
        last_activity = item.get('last_activity', {}).get('S')
        status = item.get('status', {}).get('S', ConnectionStatus.CONNECTED)
        expires_at_str = item.get('expires_at', {}).get('N')
        expires_at = int(expires_at_str) if expires_at_str else None
        
        return cls(
            connection_id=connection_id,
            job_id=job_id,
            created_at=created_at,
            last_activity=last_activity,
            status=status,
            expires_at=expires_at
        )
    
    def update_activity(self):
        """Update last_activity timestamp to now."""
        self.last_activity = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert connection to dictionary format.
        
        Returns:
            Dictionary representation of connection
        """
        return {
            'connection_id': self.connection_id,
            'job_id': self.job_id,
            'created_at': self.created_at,
            'last_activity': self.last_activity,
            'status': self.status,
            'expires_at': self.expires_at
        }
    
    def __repr__(self) -> str:
        """String representation of connection."""
        return (
            f"WebSocketConnection(connection_id='{self.connection_id}', "
            f"job_id='{self.job_id}', status='{self.status}')"
        )



