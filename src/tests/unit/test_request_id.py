"""
Unit tests for request ID generation utility.
"""
import pytest
import re
from src.utils.request_id import generate_request_id, extract_api_version


class TestGenerateRequestId:
    """Test request ID generation."""
    
    def test_generate_request_id_format(self):
        """Test request ID follows correct format: req_{timestamp}_{random}."""
        request_id = generate_request_id()
        
        assert request_id.startswith('req_')
        # Format: req_YYYYMMDD_HHMMSS_{8 hex chars}
        pattern = r'^req_\d{8}_\d{6}_[a-f0-9]{8}$'
        assert re.match(pattern, request_id), f"Request ID {request_id} doesn't match expected format"
    
    def test_generate_request_id_uniqueness(self):
        """Test that multiple request IDs are unique."""
        request_ids = [generate_request_id() for _ in range(10)]
        assert len(set(request_ids)) == 10, "Request IDs should be unique"


class TestExtractApiVersion:
    """Test API version extraction."""
    
    def test_extract_api_version_v1(self):
        """Test extracting v1 from path."""
        assert extract_api_version('/api/v1/jobs') == 'v1'
        assert extract_api_version('/api/v1/jobs/123') == 'v1'
    
    def test_extract_api_version_v2(self):
        """Test extracting v2 from path."""
        assert extract_api_version('/api/v2/jobs') == 'v2'
        assert extract_api_version('/api/v2/jobs/123') == 'v2'
    
    def test_extract_api_version_default(self):
        """Test default version when no version in path."""
        assert extract_api_version('/health') == 'v1'
        assert extract_api_version('/api/jobs') == 'v1'
        assert extract_api_version('/') == 'v1'
    
    def test_extract_api_version_multiple_digits(self):
        """Test extracting version with multiple digits."""
        assert extract_api_version('/api/v10/jobs') == 'v10'

