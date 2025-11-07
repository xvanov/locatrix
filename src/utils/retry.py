"""
Retry utility with exponential backoff for transient failures.

This module provides retry logic with exponential backoff (1s, 2s, 4s, 8s)
and configurable max retries for handling transient AWS service failures.
"""
import time
import random
from typing import Callable, TypeVar, Optional, List, Type
from functools import wraps
import boto3
from botocore.exceptions import ClientError


T = TypeVar('T')


# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_DELAY = 1  # seconds
DEFAULT_MAX_DELAY = 8  # seconds
DEFAULT_BACKOFF_MULTIPLIER = 2


# Retryable error codes for AWS services
RETRYABLE_ERROR_CODES = [
    'Throttling',
    'ThrottlingException',
    'ServiceUnavailable',
    'InternalServerError',
    'RequestTimeout',
    'RequestTimeoutException',
    'TooManyRequestsException',
    'ProvisionedThroughputExceededException',
    'LimitExceededException',
]


def is_retryable_error(error: Exception) -> bool:
    """
    Check if an error is retryable.
    
    Args:
        error: Exception to check
        
    Returns:
        True if error is retryable, False otherwise
    """
    if isinstance(error, ClientError):
        error_code = error.response.get('Error', {}).get('Code', '')
        return error_code in RETRYABLE_ERROR_CODES
    
    # Check for connection errors, timeouts, etc.
    error_type = type(error).__name__
    retryable_types = [
        'ConnectionError',
        'TimeoutError',
        'ReadTimeout',
        'ConnectTimeout',
    ]
    
    return error_type in retryable_types


def exponential_backoff_delay(attempt: int, initial_delay: float = DEFAULT_INITIAL_DELAY,
                             max_delay: float = DEFAULT_MAX_DELAY,
                             backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER) -> float:
    """
    Calculate exponential backoff delay with jitter.
    
    Args:
        attempt: Current attempt number (0-indexed)
        initial_delay: Initial delay in seconds (default: 1)
        max_delay: Maximum delay in seconds (default: 8)
        backoff_multiplier: Multiplier for exponential backoff (default: 2)
        
    Returns:
        Delay in seconds
        
    Example:
        >>> delay = exponential_backoff_delay(0)  # ~1 second
        >>> delay = exponential_backoff_delay(1)  # ~2 seconds
        >>> delay = exponential_backoff_delay(2)  # ~4 seconds
        >>> delay = exponential_backoff_delay(3)  # ~8 seconds (capped)
    """
    # Calculate exponential delay
    delay = initial_delay * (backoff_multiplier ** attempt)
    
    # Cap at max delay
    delay = min(delay, max_delay)
    
    # Add jitter (random 0-25% of delay)
    jitter = random.uniform(0, delay * 0.25)
    delay = delay + jitter
    
    return delay


def retry_with_backoff(
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
    retryable_exceptions: Optional[List[Type[Exception]]] = None,
    on_retry: Optional[Callable[[Exception, int], None]] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 1)
        max_delay: Maximum delay in seconds (default: 8)
        backoff_multiplier: Multiplier for exponential backoff (default: 2)
        retryable_exceptions: List of exception types to retry (default: None, uses is_retryable_error)
        on_retry: Optional callback function called on each retry (default: None)
        
    Returns:
        Decorated function with retry logic
        
    Example:
        >>> @retry_with_backoff(max_retries=5)
        >>> def call_aws_service():
        >>>     # AWS service call
        >>>     pass
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Check if error is retryable
                    is_retryable = False
                    if retryable_exceptions:
                        is_retryable = isinstance(e, tuple(retryable_exceptions))
                    else:
                        is_retryable = is_retryable_error(e)
                    
                    # If not retryable or last attempt, raise
                    if not is_retryable or attempt >= max_retries:
                        raise
                    
                    # Calculate delay and wait
                    delay = exponential_backoff_delay(
                        attempt,
                        initial_delay=initial_delay,
                        max_delay=max_delay,
                        backoff_multiplier=backoff_multiplier
                    )
                    
                    # Call retry callback if provided
                    if on_retry:
                        on_retry(e, attempt + 1)
                    
                    time.sleep(delay)
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
            
        return wrapper
    return decorator


def retry_aws_call(
    func: Callable[..., T],
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
    on_retry: Optional[Callable[[Exception, int], None]] = None
) -> T:
    """
    Retry an AWS service call with exponential backoff.
    
    Convenience function for retrying AWS calls without decorator syntax.
    
    Args:
        func: Function to call (should be a callable that returns the result)
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 1)
        max_delay: Maximum delay in seconds (default: 8)
        backoff_multiplier: Multiplier for exponential backoff (default: 2)
        on_retry: Optional callback function called on each retry (default: None)
        
    Returns:
        Result of function call
        
    Raises:
        Last exception if all retries fail
        
    Example:
        >>> result = retry_aws_call(
        >>>     lambda: dynamodb.get_item(Key={'job_id': 'job_123'}),
        >>>     max_retries=5
        >>> )
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_exception = e
            
            # Check if error is retryable
            if not is_retryable_error(e) or attempt >= max_retries:
                raise
            
            # Calculate delay and wait
            delay = exponential_backoff_delay(
                attempt,
                initial_delay=initial_delay,
                max_delay=max_delay,
                backoff_multiplier=backoff_multiplier
            )
            
            # Call retry callback if provided
            if on_retry:
                on_retry(e, attempt + 1)
            
            time.sleep(delay)
    
    # Should never reach here, but just in case
    if last_exception:
        raise last_exception

