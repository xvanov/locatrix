"""
Configuration utility for retrieving values from AWS Systems Manager Parameter Store.

This module provides functions to retrieve configuration values from Parameter Store
with caching to reduce API calls.
"""
import os
import json
from typing import Optional, Dict, Any
from functools import lru_cache
import boto3
from botocore.exceptions import ClientError


# Cache for configuration values (in-memory cache)
_config_cache: Dict[str, Any] = {}


def get_parameter(parameter_name: str, decrypt: bool = False, default: Optional[Any] = None) -> Any:
    """
    Retrieve a configuration value from Parameter Store.
    
    Uses in-memory caching to reduce API calls. Cache persists for the lifetime
    of the Lambda execution context.
    
    Args:
        parameter_name: Name of the parameter in Parameter Store
        decrypt: Whether to decrypt SecureString parameters (default: False)
        default: Default value to return if parameter not found (default: None)
        
    Returns:
        Parameter value (string, JSON-parsed dict/list, or default)
        
    Raises:
        ValueError: If parameter not found and no default provided
        ClientError: If AWS API call fails
        
    Example:
        >>> api_timeout = get_parameter('/location-detection/api-timeout', default=30)
        >>> db_config = get_parameter('/location-detection/db-config', decrypt=True)
    """
    # Check cache first
    cache_key = f"{parameter_name}:{decrypt}"
    if cache_key in _config_cache:
        return _config_cache[cache_key]
    
    # Create SSM client
    ssm_client = boto3.client('ssm')
    
    try:
        # Retrieve parameter
        response = ssm_client.get_parameter(
            Name=parameter_name,
            WithDecryption=decrypt
        )
        
        parameter_value = response['Parameter']['Value']
        parameter_type = response['Parameter']['Type']
        
        # Parse JSON if parameter type is StringList or if value looks like JSON
        if parameter_type == 'StringList':
            # StringList is comma-separated
            parsed_value = [item.strip() for item in parameter_value.split(',')]
        elif parameter_value.strip().startswith(('{', '[')):
            # Try to parse as JSON
            try:
                parsed_value = json.loads(parameter_value)
            except json.JSONDecodeError:
                parsed_value = parameter_value
        else:
            parsed_value = parameter_value
        
        # Cache the value
        _config_cache[cache_key] = parsed_value
        
        return parsed_value
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        
        if error_code == 'ParameterNotFound':
            if default is not None:
                return default
            raise ValueError(f"Parameter '{parameter_name}' not found and no default provided") from e
        
        # Re-raise other errors
        raise


def get_parameters_by_path(parameter_path: str, recursive: bool = True, decrypt: bool = False) -> Dict[str, Any]:
    """
    Retrieve multiple parameters from Parameter Store by path.
    
    Args:
        parameter_path: Path prefix for parameters (e.g., '/location-detection/')
        recursive: Whether to retrieve parameters recursively (default: True)
        decrypt: Whether to decrypt SecureString parameters (default: False)
        
    Returns:
        Dictionary mapping parameter names (without path prefix) to values
        
    Raises:
        ClientError: If AWS API call fails
        
    Example:
        >>> config = get_parameters_by_path('/location-detection/api/')
        >>> timeout = config['timeout']
    """
    ssm_client = boto3.client('ssm')
    parameters = {}
    
    try:
        paginator = ssm_client.get_paginator('get_parameters_by_path')
        
        for page in paginator.paginate(
            Path=parameter_path,
            Recursive=recursive,
            WithDecryption=decrypt
        ):
            for param in page.get('Parameters', []):
                # Remove path prefix from parameter name
                param_name = param['Name'].replace(parameter_path, '').lstrip('/')
                param_value = param['Value']
                
                # Parse JSON if value looks like JSON
                if param_value.strip().startswith(('{', '[')):
                    try:
                        param_value = json.loads(param_value)
                    except json.JSONDecodeError:
                        pass
                
                parameters[param_name] = param_value
        
        return parameters
        
    except ClientError as e:
        raise


def clear_cache():
    """
    Clear the configuration cache.
    
    Useful for testing or when configuration values need to be refreshed.
    """
    global _config_cache
    _config_cache.clear()


def get_environment() -> str:
    """
    Get the current environment name from environment variable.
    
    Returns:
        Environment name (dev, prod, etc.)
        
    Example:
        >>> env = get_environment()
        >>> if env == 'dev':
        >>>     # Use dev-specific config
    """
    return os.environ.get('ENVIRONMENT', 'dev')

