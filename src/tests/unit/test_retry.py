"""
Unit tests for retry utility.
"""
import pytest
import time
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

from src.utils.retry import (
    retry_with_backoff,
    retry_aws_call,
    is_retryable_error,
    exponential_backoff_delay
)


class TestIsRetryableError:
    """Test is_retryable_error function."""
    
    def test_retryable_client_error(self):
        """Test retryable ClientError."""
        error = ClientError(
            {'Error': {'Code': 'ThrottlingException'}},
            'GetItem'
        )
        assert is_retryable_error(error) is True
    
    def test_non_retryable_client_error(self):
        """Test non-retryable ClientError."""
        error = ClientError(
            {'Error': {'Code': 'ValidationException'}},
            'GetItem'
        )
        assert is_retryable_error(error) is False
    
    def test_connection_error(self):
        """Test connection error."""
        error = ConnectionError('Connection failed')
        assert is_retryable_error(error) is True


class TestExponentialBackoffDelay:
    """Test exponential_backoff_delay function."""
    
    def test_delay_calculation(self):
        """Test delay calculation."""
        delay1 = exponential_backoff_delay(0)
        delay2 = exponential_backoff_delay(1)
        delay3 = exponential_backoff_delay(2)
        
        # Delays should increase exponentially (with jitter)
        assert delay1 < delay2 < delay3
        assert delay1 >= 1.0  # At least initial delay
        assert delay3 <= 8.0  # Capped at max delay
    
    def test_max_delay_cap(self):
        """Test max delay cap."""
        delay = exponential_backoff_delay(10)  # Very high attempt
        assert delay <= 8.0  # Should be capped


class TestRetryWithBackoff:
    """Test retry_with_backoff decorator."""
    
    def test_successful_call_no_retry(self):
        """Test successful call doesn't retry."""
        call_count = [0]
        
        @retry_with_backoff(max_retries=3)
        def test_func():
            call_count[0] += 1
            return 'success'
        
        result = test_func()
        assert result == 'success'
        assert call_count[0] == 1
    
    def test_retry_on_retryable_error(self):
        """Test retry on retryable error."""
        call_count = [0]
        
        @retry_with_backoff(max_retries=3, initial_delay=0.01)
        def test_func():
            call_count[0] += 1
            if call_count[0] < 2:
                error = ClientError(
                    {'Error': {'Code': 'ThrottlingException'}},
                    'GetItem'
                )
                raise error
            return 'success'
        
        result = test_func()
        assert result == 'success'
        assert call_count[0] == 2
    
    def test_max_retries_exceeded(self):
        """Test max retries exceeded."""
        call_count = [0]
        
        @retry_with_backoff(max_retries=2, initial_delay=0.01)
        def test_func():
            call_count[0] += 1
            error = ClientError(
                {'Error': {'Code': 'ThrottlingException'}},
                'GetItem'
            )
            raise error
        
        with pytest.raises(ClientError):
            test_func()
        
        assert call_count[0] == 3  # Initial + 2 retries


class TestRetryAwsCall:
    """Test retry_aws_call function."""
    
    def test_successful_call(self):
        """Test successful AWS call."""
        mock_func = Mock(return_value='success')
        result = retry_aws_call(mock_func, max_retries=3, initial_delay=0.01)
        
        assert result == 'success'
        assert mock_func.call_count == 1
    
    def test_retry_on_throttling(self):
        """Test retry on throttling."""
        call_count = [0]
        
        def mock_func():
            call_count[0] += 1
            if call_count[0] < 2:
                error = ClientError(
                    {'Error': {'Code': 'ThrottlingException'}},
                    'GetItem'
                )
                raise error
            return 'success'
        
        result = retry_aws_call(mock_func, max_retries=3, initial_delay=0.01)
        assert result == 'success'
        assert call_count[0] == 2

