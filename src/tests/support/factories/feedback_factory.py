"""
Data factories for feedback testing.

These factories create test data with sensible defaults and support overrides.
Uses faker-like patterns adapted for Python testing.
"""
import random
import string
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List


def generate_feedback_id() -> str:
    """
    Generate a unique feedback ID in format: fb_{timestamp}_{random}.
    
    Returns:
        Feedback ID string
    """
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"fb_{timestamp}_{random_part}"


def generate_job_id() -> str:
    """
    Generate a unique job ID in format: job_{timestamp}_{random}.
    
    Returns:
        Job ID string
    """
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"job_{timestamp}_{random_part}"


def generate_room_id() -> str:
    """
    Generate a unique room ID.
    
    Returns:
        Room ID string
    """
    random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"room_{random_part}"


def create_feedback_data(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create feedback data dictionary with sensible defaults.
    
    Args:
        overrides: Dictionary of fields to override
        
    Returns:
        Feedback data dictionary
        
    Example:
        >>> # Default feedback (correct type)
        >>> feedback = create_feedback_data()
        >>> 
        >>> # Wrong feedback with correction
        >>> feedback = create_feedback_data({
        ...     'feedback': 'wrong',
        ...     'room_id': 'room_001',
        ...     'correction': {'bounding_box': [60, 60, 210, 310]}
        ... })
    """
    defaults = {
        'feedback': 'correct',
        'room_id': None,
        'correction': None
    }
    
    if overrides:
        defaults.update(overrides)
    
    return defaults


def create_feedback_dict(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create complete feedback dictionary (as would be returned from API).
    
    Args:
        overrides: Dictionary of fields to override
        
    Returns:
        Complete feedback dictionary with all fields
        
    Example:
        >>> # Default feedback dict
        >>> feedback_dict = create_feedback_dict()
        >>> 
        >>> # Custom feedback dict
        >>> feedback_dict = create_feedback_dict({
        ...     'job_id': 'job_123',
        ...     'feedback': 'wrong'
        ... })
    """
    defaults = {
        'feedback_id': generate_feedback_id(),
        'job_id': generate_job_id(),
        'feedback': 'correct',
        'room_id': None,
        'correction': None,
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    if overrides:
        defaults.update(overrides)
    
    return defaults


def create_feedback_list(count: int, job_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Create a list of feedback dictionaries.
    
    Args:
        count: Number of feedback items to create
        job_id: Optional job_id to use for all items (default: generate unique)
        
    Returns:
        List of feedback dictionaries
        
    Example:
        >>> # Create 3 feedback items for same job
        >>> feedback_list = create_feedback_list(3, job_id='job_123')
    """
    if job_id is None:
        job_id = generate_job_id()
    
    feedback_types = ['correct', 'wrong', 'partial']
    
    feedback_list = []
    for i in range(count):
        feedback_type = random.choice(feedback_types)
        feedback_dict = create_feedback_dict({
            'job_id': job_id,
            'feedback': feedback_type
        })
        
        if feedback_type == 'wrong':
            feedback_dict['room_id'] = generate_room_id()
            feedback_dict['correction'] = {
                'bounding_box': [
                    random.randint(0, 100),
                    random.randint(0, 100),
                    random.randint(200, 400),
                    random.randint(200, 400)
                ]
            }
        elif feedback_type == 'partial':
            feedback_dict['room_id'] = generate_room_id()
            feedback_dict['correction'] = {
                'bounding_box': [
                    random.randint(0, 100),
                    random.randint(0, 100),
                    random.randint(200, 400),
                    random.randint(200, 400)
                ]
            }
        
        feedback_list.append(feedback_dict)
    
    return feedback_list


def create_correction_data(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create correction data dictionary with bounding box.
    
    Args:
        overrides: Dictionary of fields to override
        
    Returns:
        Correction data dictionary
        
    Example:
        >>> # Default bounding box
        >>> correction = create_correction_data()
        >>> 
        >>> # Custom bounding box
        >>> correction = create_correction_data({
        ...     'bounding_box': [60, 60, 210, 310]
        ... })
    """
    defaults = {
        'bounding_box': [
            random.randint(0, 100),
            random.randint(0, 100),
            random.randint(200, 400),
            random.randint(200, 400)
        ]
    }
    
    if overrides:
        defaults.update(overrides)
    
    return defaults


