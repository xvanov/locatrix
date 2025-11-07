"""
Unit tests for logging utility.
"""
import pytest
import json
from unittest.mock import patch

from src.utils.logging import get_logger, StructuredLogger


class TestStructuredLogger:
    """Test StructuredLogger class."""
    
    def test_logger_creation(self):
        """Test logger creation."""
        logger = get_logger(__name__)
        assert isinstance(logger, StructuredLogger)
    
    def test_set_request_id(self):
        """Test setting request ID."""
        logger = get_logger(__name__)
        logger.set_request_id('req_123')
        assert logger._request_id == 'req_123'
    
    def test_set_job_id(self):
        """Test setting job ID."""
        logger = get_logger(__name__)
        logger.set_job_id('job_456')
        assert logger._job_id == 'job_456'
    
    def test_info_log(self, capsys):
        """Test info logging."""
        logger = get_logger(__name__)
        logger.set_request_id('req_123')
        logger.info('Test message')
        
        captured = capsys.readouterr()
        log_data = json.loads(captured.out.strip())
        
        assert log_data['level'] == 'INFO'
        assert log_data['message'] == 'Test message'
        assert log_data['request_id'] == 'req_123'
    
    def test_error_log_with_exception(self, capsys):
        """Test error logging with exception."""
        logger = get_logger(__name__)
        logger.set_job_id('job_456')
        
        try:
            raise ValueError('Test error')
        except Exception:
            logger.error('Error occurred', exc_info=True)
        
        captured = capsys.readouterr()
        log_data = json.loads(captured.out.strip())
        
        assert log_data['level'] == 'ERROR'
        assert log_data['job_id'] == 'job_456'
        assert 'exception' in log_data
    
    def test_log_with_context(self, capsys):
        """Test logging with context."""
        logger = get_logger(__name__)
        logger.info('Processing', context={'stage': 'preview', 'progress': 50})
        
        captured = capsys.readouterr()
        log_data = json.loads(captured.out.strip())
        
        assert log_data['context']['stage'] == 'preview'
        assert log_data['context']['progress'] == 50

