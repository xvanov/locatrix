"""
Request ID generation utility for Location Detection AI service.

This module provides request ID generation in the format req_{timestamp}_{random}
for distributed tracing and correlation.
"""
import uuid
from datetime import datetime, timezone


def generate_request_id() -> str:
    """
    Generate a unique request ID in format: req_{timestamp}_{random}.
    
    Format: req_YYYYMMDD_HHMMSS_{random_string}
    
    Returns:
        Request ID string
        
    Example:
        >>> request_id = generate_request_id()
        >>> # Returns: req_20240115_143022_a1b2c3d4
    """
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    random_part = uuid.uuid4().hex[:8]
    return f"req_{timestamp}_{random_part}"


def extract_api_version(path: str) -> str:
    """
    Extract API version from request path.
    
    Supports path-based versioning: /api/v1/... -> v1
    Defaults to 'v1' if version not found in path.
    
    Args:
        path: Request path (e.g., '/api/v1/jobs')
        
    Returns:
        API version string (e.g., 'v1')
        
    Example:
        >>> version = extract_api_version('/api/v1/jobs')
        >>> # Returns: 'v1'
        >>> version = extract_api_version('/health')
        >>> # Returns: 'v1' (default)
    """
    import re
    match = re.match(r'^/api/v(\d+)/', path)
    if match:
        return f"v{match.group(1)}"
    return 'v1'  # Default to v1

