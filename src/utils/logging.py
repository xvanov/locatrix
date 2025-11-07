"""
Structured JSON logging utility for Location Detection AI service.

This module provides structured JSON logging with request IDs, job IDs,
and correlation IDs for CloudWatch integration.
"""
import json
import logging
import os
import sys
from typing import Optional, Dict, Any
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON string representation of log record
        """
        log_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add request ID if available
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        
        # Add job ID if available
        if hasattr(record, 'job_id'):
            log_data['job_id'] = record.job_id
        
        # Add correlation ID if available
        if hasattr(record, 'correlation_id'):
            log_data['correlation_id'] = record.correlation_id
        
        # Add any extra context
        if hasattr(record, 'context') and isinstance(record.context, dict):
            log_data['context'] = record.context
        
        # Add exception info if present
        if record.exc_info:
            # exc_info can be True (use sys.exc_info()) or a tuple
            if record.exc_info is True:
                exc_info = sys.exc_info()
            else:
                exc_info = record.exc_info
            if exc_info[0] is not None:  # Only format if there's an exception
                log_data['exception'] = self.formatException(exc_info)
        
        return json.dumps(log_data)


class StructuredLogger:
    """
    Structured logger with support for request IDs, job IDs, and correlation IDs.
    
    This logger automatically includes context information in all log entries
    and formats output as JSON for CloudWatch integration.
    """
    
    def __init__(self, name: str, level: int = logging.INFO):
        """
        Initialize structured logger.
        
        Args:
            name: Logger name (typically __name__)
            level: Logging level (default: INFO)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Remove existing handlers to avoid duplicate logs
        self.logger.handlers.clear()
        
        # Add console handler with JSON formatter
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        self.logger.addHandler(handler)
        
        # Set default context
        self._request_id: Optional[str] = None
        self._job_id: Optional[str] = None
        self._correlation_id: Optional[str] = None
    
    def set_request_id(self, request_id: str):
        """Set request ID for all subsequent log entries."""
        self._request_id = request_id
    
    def set_job_id(self, job_id: str):
        """Set job ID for all subsequent log entries."""
        self._job_id = job_id
    
    def set_correlation_id(self, correlation_id: str):
        """Set correlation ID for all subsequent log entries."""
        self._correlation_id = correlation_id
    
    def _make_record(self, level: int, msg: str, *args, context: Optional[Dict[str, Any]] = None, **kwargs) -> logging.LogRecord:
        """Create log record with context information."""
        # Create record using logger's makeRecord method
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            '',  # filename
            0,   # lineno
            msg,
            args,
            None  # exc_info
        )
        
        # Add context attributes
        if self._request_id:
            record.request_id = self._request_id
        if self._job_id:
            record.job_id = self._job_id
        if self._correlation_id:
            record.correlation_id = self._correlation_id
        if context:
            record.context = context
        
        return record
    
    def debug(self, msg: str, *args, context: Optional[Dict[str, Any]] = None, **kwargs):
        """Log debug message."""
        record = self._make_record(logging.DEBUG, msg, *args, context=context, **kwargs)
        self.logger.handle(record)
    
    def info(self, msg: str, *args, context: Optional[Dict[str, Any]] = None, **kwargs):
        """Log info message."""
        record = self._make_record(logging.INFO, msg, *args, context=context, **kwargs)
        self.logger.handle(record)
    
    def warning(self, msg: str, *args, context: Optional[Dict[str, Any]] = None, **kwargs):
        """Log warning message."""
        record = self._make_record(logging.WARNING, msg, *args, context=context, **kwargs)
        self.logger.handle(record)
    
    def error(self, msg: str, *args, context: Optional[Dict[str, Any]] = None, exc_info=None, **kwargs):
        """Log error message."""
        record = self._make_record(logging.ERROR, msg, *args, context=context, **kwargs)
        if exc_info:
            # Convert exc_info=True to sys.exc_info() tuple
            if exc_info is True:
                record.exc_info = sys.exc_info()
            else:
                record.exc_info = exc_info
        self.logger.handle(record)
    
    def critical(self, msg: str, *args, context: Optional[Dict[str, Any]] = None, exc_info=None, **kwargs):
        """Log critical message."""
        record = self._make_record(logging.CRITICAL, msg, *args, context=context, **kwargs)
        if exc_info:
            # Convert exc_info=True to sys.exc_info() tuple
            if exc_info is True:
                record.exc_info = sys.exc_info()
            else:
                record.exc_info = exc_info
        self.logger.handle(record)


def get_logger(name: str, level: Optional[int] = None) -> StructuredLogger:
    """
    Get or create a structured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        level: Logging level (default: INFO, or from LOG_LEVEL env var)
        
    Returns:
        StructuredLogger instance
        
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.set_request_id('req_123')
        >>> logger.set_job_id('job_456')
        >>> logger.info('Processing started', context={'stage': 'preview'})
    """
    if level is None:
        level_str = os.environ.get('LOG_LEVEL', 'INFO').upper()
        level = getattr(logging, level_str, logging.INFO)
    
    return StructuredLogger(name, level)

