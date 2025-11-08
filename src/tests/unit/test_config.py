"""
Unit tests for configuration utility.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from src.utils.config import get_parameter, get_parameters_by_path, clear_cache, get_environment


@pytest.fixture
def mock_ssm_client():
    """Mock SSM client."""
    with patch('src.utils.config.boto3.client') as mock_client:
        mock_ssm = MagicMock()
        mock_client.return_value = mock_ssm
        yield mock_ssm


class TestGetParameter:
    """Test get_parameter function."""
    
    def test_get_parameter_string(self, mock_ssm_client):
        """Test retrieving a string parameter."""
        mock_ssm_client.get_parameter.return_value = {
            'Parameter': {
                'Name': '/test/param',
                'Value': 'test-value',
                'Type': 'String'
            }
        }
        
        result = get_parameter('/test/param')
        assert result == 'test-value'
        mock_ssm_client.get_parameter.assert_called_once_with(
            Name='/test/param',
            WithDecryption=False
        )
    
    def test_get_parameter_json(self, mock_ssm_client):
        """Test retrieving a JSON parameter."""
        mock_ssm_client.get_parameter.return_value = {
            'Parameter': {
                'Name': '/test/config',
                'Value': '{"key": "value"}',
                'Type': 'String'
            }
        }
        
        result = get_parameter('/test/config')
        assert result == {'key': 'value'}
    
    def test_get_parameter_with_default(self, mock_ssm_client):
        """Test parameter not found with default."""
        mock_ssm_client.get_parameter.side_effect = ClientError(
            {'Error': {'Code': 'ParameterNotFound'}},
            'GetParameter'
        )
        
        result = get_parameter('/test/missing', default='default-value')
        assert result == 'default-value'
    
    def test_get_parameter_not_found_no_default(self, mock_ssm_client):
        """Test parameter not found without default raises error."""
        mock_ssm_client.get_parameter.side_effect = ClientError(
            {'Error': {'Code': 'ParameterNotFound'}},
            'GetParameter'
        )
        
        with pytest.raises(ValueError, match="not found"):
            get_parameter('/test/missing')
    
    def test_get_parameter_caching(self, mock_ssm_client):
        """Test parameter caching."""
        # Clear cache before test to ensure clean state
        clear_cache()
        
        mock_ssm_client.get_parameter.return_value = {
            'Parameter': {
                'Name': '/test/param',
                'Value': 'test-value',
                'Type': 'String'
            }
        }
        
        # First call - should call API
        result1 = get_parameter('/test/param')
        assert result1 == 'test-value'
        assert mock_ssm_client.get_parameter.call_count == 1
        
        # Second call - should use cache, no API call
        result2 = get_parameter('/test/param')
        assert result2 == 'test-value'
        assert mock_ssm_client.get_parameter.call_count == 1  # Still 1 due to cache
        
        # Clear cache and call again - should call API again
        clear_cache()
        result3 = get_parameter('/test/param')
        assert result3 == 'test-value'
        assert mock_ssm_client.get_parameter.call_count == 2  # Now 2 after cache clear


class TestGetParametersByPath:
    """Test get_parameters_by_path function."""
    
    def test_get_parameters_by_path(self, mock_ssm_client):
        """Test retrieving parameters by path."""
        mock_paginator = MagicMock()
        mock_ssm_client.get_paginator.return_value = mock_paginator
        
        mock_paginator.paginate.return_value = [
            {
                'Parameters': [
                    {
                        'Name': '/test/param1',
                        'Value': 'value1'
                    },
                    {
                        'Name': '/test/param2',
                        'Value': 'value2'
                    }
                ]
            }
        ]
        
        result = get_parameters_by_path('/test/')
        assert result['param1'] == 'value1'
        assert result['param2'] == 'value2'


class TestGetEnvironment:
    """Test get_environment function."""
    
    @patch.dict('os.environ', {'ENVIRONMENT': 'prod'})
    def test_get_environment_from_env(self):
        """Test getting environment from environment variable."""
        assert get_environment() == 'prod'
    
    @patch.dict('os.environ', {}, clear=True)
    def test_get_environment_default(self):
        """Test default environment when not set."""
        assert get_environment() == 'dev'

