"""
Room detection algorithm for preview pipeline.

This module provides fast room detection using Textract layout data
to generate bounding boxes for detected rooms.
"""
from typing import List, Dict, Any
from datetime import datetime, timezone


def detect_rooms(textract_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Detect rooms from Textract analysis results using lightweight heuristics.
    
    This is a fast preview algorithm that uses Textract layout blocks
    to identify potential room boundaries. For production, this would be
    replaced with a more sophisticated ML model.
    
    Args:
        textract_result: Textract analysis result with text_blocks and layout_blocks
        
    Returns:
        List of room detection results with bounding boxes
    """
    rooms = []
    
    # Extract layout blocks (PAGE, TABLE, CELL blocks often indicate room boundaries)
    layout_blocks = textract_result.get('layout_blocks', [])
    text_blocks = textract_result.get('text_blocks', [])
    
    # Simple heuristic: Use TABLE blocks as room boundaries
    # In a real implementation, this would use ML model or more sophisticated heuristics
    table_blocks = [b for b in layout_blocks if b.get('blockType') == 'TABLE']
    
    # If we have table blocks, use them as room boundaries
    if table_blocks:
        for idx, table_block in enumerate(table_blocks):
            geometry = table_block.get('geometry', {})
            bounding_box = geometry.get('BoundingBox', {})
            
            if bounding_box:
                # Convert Textract bounding box format to our format
                # Textract uses normalized coordinates (0-1) with left, top, width, height
                # We need to convert to pixel coordinates [x_min, y_min, x_max, y_max]
                # For preview, we'll use a default image size of 1000x1000
                # In production, we'd get actual image dimensions
                image_width = 1000
                image_height = 1000
                
                left = bounding_box.get('Left', 0) * image_width
                top = bounding_box.get('Top', 0) * image_height
                width = bounding_box.get('Width', 0) * image_width
                height = bounding_box.get('Height', 0) * image_height
                
                x_min = int(left)
                y_min = int(top)
                x_max = int(left + width)
                y_max = int(top + height)
                
                # Extract room name hint from nearby text blocks
                name_hint = _extract_room_name_hint(text_blocks, x_min, y_min, x_max, y_max)
                
                room = {
                    'id': f"room_{idx + 1:03d}",
                    'bounding_box': [x_min, y_min, x_max, y_max],
                    'confidence': 0.75  # Default confidence for preview
                }
                # Only include name_hint if it's not None
                if name_hint is not None:
                    room['name_hint'] = name_hint
                rooms.append(room)
    
    # If no table blocks, use PAGE blocks or create default rooms from text blocks
    if not rooms:
        # Fallback: Create rooms from text blocks grouped by proximity
        page_blocks = [b for b in layout_blocks if b.get('blockType') == 'PAGE']
        
        if page_blocks:
            # Use first page block as a single room
            page_block = page_blocks[0]
            geometry = page_block.get('geometry', {})
            bounding_box = geometry.get('BoundingBox', {})
            
            if bounding_box:
                image_width = 1000
                image_height = 1000
                
                left = bounding_box.get('Left', 0) * image_width
                top = bounding_box.get('Top', 0) * image_height
                width = bounding_box.get('Width', 0) * image_width
                height = bounding_box.get('Height', 0) * image_height
                
                x_min = int(left)
                y_min = int(top)
                x_max = int(left + width)
                y_max = int(top + height)
                
                name_hint = _extract_room_name_hint(text_blocks, x_min, y_min, x_max, y_max)
                
                room = {
                    'id': 'room_001',
                    'bounding_box': [x_min, y_min, x_max, y_max],
                    'confidence': 0.6  # Lower confidence for fallback
                }
                # Only include name_hint if it's not None
                if name_hint is not None:
                    room['name_hint'] = name_hint
                rooms.append(room)
        else:
            # Last resort: Create a default room covering the entire image
            room = {
                'id': 'room_001',
                'bounding_box': [0, 0, 1000, 1000],
                'confidence': 0.5  # Low confidence for default room
            }
            # No name_hint for default room
            rooms.append(room)
    
    return rooms


def _extract_room_name_hint(
    text_blocks: List[Dict[str, Any]],
    x_min: int,
    y_min: int,
    x_max: int,
    y_max: int
) -> str:
    """
    Extract room name hint from text blocks within bounding box.
    
    Args:
        text_blocks: List of text blocks from Textract
        x_min, y_min, x_max, y_max: Bounding box coordinates
        
    Returns:
        Room name hint string or None
    """
    # Common room name keywords
    room_keywords = [
        'room', 'bedroom', 'bathroom', 'kitchen', 'living', 'dining',
        'hall', 'entry', 'office', 'study', 'garage', 'basement',
        'attic', 'closet', 'pantry', 'laundry', 'utility'
    ]
    
    # Find text blocks within bounding box
    for text_block in text_blocks:
        geometry = text_block.get('geometry', {})
        bounding_box = geometry.get('BoundingBox', {})
        
        if bounding_box:
            # Check if text block is within room bounding box
            text_left = bounding_box.get('Left', 0) * 1000
            text_top = bounding_box.get('Top', 0) * 1000
            
            if (x_min <= text_left <= x_max and y_min <= text_top <= y_max):
                text = text_block.get('text', '').lower()
                
                # Check if text contains room keywords
                for keyword in room_keywords:
                    if keyword in text:
                        return text_block.get('text', '').strip()
    
    return None

