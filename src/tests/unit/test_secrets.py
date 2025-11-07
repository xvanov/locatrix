"""
Unit tests for secrets utility.
"""
import pytest
import time
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

from src.utils.secrets import (
    get_secret,
    get_secret_string,
    get_secret_dict,
    clear_cache,
    CACHE_TTL_SECONDS
)


@pytest.fixture
def mock_secrets_client():
    """Mock Secrets Manager client."""
    with patch('src.utils.secrets.boto3.client') as mock_client:
        mock_secrets = MagicMock()
        mock_client.return_value = mock_secrets
        yield mock_secrets


class TestGetSecret:
    """Test get_secret function."""
    
    def test_get_secret_json(self, mock_secrets_client):
        """Test retrieving a JSON secret."""
        mock_secrets_client.get_secret_value.return_value = {
            'SecretString': '{"username": "user", "password": "pass"}'
        }
        
        result = get_secret('test-secret')
        assert result == {'username': 'user', 'password': 'pass'}
    
    def test_get_secret_string(self, mock_secrets_client):
        """Test retrieving a string secret."""
        mock_secrets_client.get_secret_value.return_value = {
            'SecretString': 'simple-secret-value'
        }
        
        result = get_secret('test-secret')
        assert result == 'simple-secret-value'
    
    def test_get_secret_with_default(self, mock_secrets_client):
        """Test secret not found with default."""
        mock_secrets_client.get_secret_value.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException'}},
            'GetSecretValue'
        )
        
        result = get_secret('missing-secret', default='default-value')
        assert result == 'default-value'
    
    def test_get_secret_caching(self, mock_secrets_client):
        """Test secret caching with TTL."""
        mock_secrets_client.get_secret_value.return_value = {
            'SecretString': 'cached-secret'
        }
        
        # First call
        result1 = get_secret('test-secret')
        assert result1 == 'cached-secret'
        
        # Second call should use cache (within TTL)
        result2 = get_secret('test-secret')
        assert result2 == 'cached-secret'
        
        # Should only be called once due to caching
        assert mock_secrets_client.get_secret_value.call_count == 1
        
        # Clear cache and call again
        clear_cache()
        result3 = get_secret('test-secret')
        assert result3 == 'cached-secret'
        assert mock_secrets_client.get_secret_value.call_count == 2


class TestGetSecretString:
    """Test get_secret_string function."""
    
    def test_get_secret_string_from_string(self, mock_secrets_client):
        """Test getting string secret as string."""
        mock_secrets_client.get_secret_value.return_value = {
            'SecretString': 'simple-secret'
        }
        
        result = get_secret_string('test-secret')
        assert result == 'simple-secret'
    
    def test_get_secret_string_from_json(self, mock_secrets_client):
        """Test getting JSON secret as string."""
        mock_secrets_client.get_secret_value.return_value = {
            'SecretString': '{"key": "value"}'
        }
        
        result = get_secret_string('test-secret')
        assert isinstance(result, str)
        assert 'key' in result


class TestGetSecretDict:
    """Test get_secret_dict function."""
    
    def test_get_secret_dict_from_json(self, mock_secrets_client):
        """Test getting JSON secret as dict."""
        mock_secrets_client.get_secret_value.return_value = {
            'SecretString': '{"username": "user", "password": "pass"}'
        }
        
        result = get_secret_dict('test-secret')
        assert isinstance(result, dict)
        assert result['username'] == 'user'
        assert result['password'] == 'pass'
    
    def test_get_secret_dict_from_string_json(self, mock_secrets_client):
        """Test getting string JSON secret as dict."""
        mock_secrets_client.get_secret_value.return_value = {
            'SecretString': '{"key": "value"}'
        }
        
        result = get_secret_dict('test-secret')
        assert isinstance(result, dict)
        assert result['key'] == 'value'

