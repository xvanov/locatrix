"""
Secrets utility for retrieving secrets from AWS Secrets Manager.

This module provides functions to retrieve secrets from Secrets Manager
with TTL-based caching (5 minutes) to reduce API calls.
"""
import os
import json
import time
from typing import Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError


# Cache for secrets with TTL (5 minutes = 300 seconds)
_secrets_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 300


def get_secret(secret_name: str, default: Optional[Any] = None) -> Any:
    """
    Retrieve a secret from Secrets Manager.
    
    Uses TTL-based caching (5 minutes) to reduce API calls. Cache entries
    expire after 5 minutes and are automatically refreshed.
    
    Args:
        secret_name: Name or ARN of the secret in Secrets Manager
        default: Default value to return if secret not found (default: None)
        
    Returns:
        Secret value (string, JSON-parsed dict/list, or default)
        
    Raises:
        ValueError: If secret not found and no default provided
        ClientError: If AWS API call fails
        
    Example:
        >>> api_key = get_secret('location-detection-api-key')
        >>> db_credentials = get_secret('location-detection-db-credentials')
        >>> # Returns dict: {'username': '...', 'password': '...'}
    """
    # Check cache first
    if secret_name in _secrets_cache:
        cached_entry = _secrets_cache[secret_name]
        cache_time = cached_entry.get('timestamp', 0)
        current_time = time.time()
        
        # Check if cache is still valid (within TTL)
        if current_time - cache_time < CACHE_TTL_SECONDS:
            return cached_entry['value']
        
        # Cache expired, remove it
        del _secrets_cache[secret_name]
    
    # Create Secrets Manager client
    secrets_client = boto3.client('secretsmanager')
    
    try:
        # Retrieve secret
        response = secrets_client.get_secret_value(SecretId=secret_name)
        
        secret_string = response.get('SecretString', '')
        
        # Try to parse as JSON (most secrets are JSON)
        try:
            secret_value = json.loads(secret_string)
        except json.JSONDecodeError:
            # Not JSON, return as string
            secret_value = secret_string
        
        # Cache the value with timestamp
        _secrets_cache[secret_name] = {
            'value': secret_value,
            'timestamp': time.time()
        }
        
        return secret_value
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        
        if error_code == 'ResourceNotFoundException':
            if default is not None:
                return default
            raise ValueError(f"Secret '{secret_name}' not found and no default provided") from e
        
        # Re-raise other errors
        raise


def get_secret_string(secret_name: str, default: Optional[str] = None) -> str:
    """
    Retrieve a secret as a string from Secrets Manager.
    
    Convenience method that ensures the return value is a string.
    
    Args:
        secret_name: Name or ARN of the secret in Secrets Manager
        default: Default value to return if secret not found (default: None)
        
    Returns:
        Secret value as string
        
    Raises:
        ValueError: If secret not found and no default provided
        ClientError: If AWS API call fails
    """
    secret_value = get_secret(secret_name, default=default)
    
    if isinstance(secret_value, str):
        return secret_value
    
    # If it's a dict/list, convert to JSON string
    return json.dumps(secret_value)


def get_secret_dict(secret_name: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Retrieve a secret as a dictionary from Secrets Manager.
    
    Convenience method that ensures the return value is a dictionary.
    If the secret is a JSON string, it will be parsed. If it's already
    a dict, it will be returned as-is.
    
    Args:
        secret_name: Name or ARN of the secret in Secrets Manager
        default: Default value to return if secret not found (default: None)
        
    Returns:
        Secret value as dictionary
        
    Raises:
        ValueError: If secret not found and no default provided, or if secret is not a dict
        ClientError: If AWS API call fails
    """
    secret_value = get_secret(secret_name, default=default)
    
    if isinstance(secret_value, dict):
        return secret_value
    
    if isinstance(secret_value, str):
        try:
            parsed = json.loads(secret_value)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    
    raise ValueError(f"Secret '{secret_name}' is not a dictionary")


def clear_cache():
    """
    Clear the secrets cache.
    
    Useful for testing or when secrets need to be refreshed immediately.
    """
    global _secrets_cache
    _secrets_cache.clear()

