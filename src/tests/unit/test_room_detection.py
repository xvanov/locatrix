"""
Unit tests for room detection algorithm.
"""
import pytest

from src.utils.room_detection import detect_rooms, _extract_room_name_hint


@pytest.fixture
def sample_textract_result():
    """Sample Textract analysis result."""
    return {
        'text_blocks': [
            {
                'id': 'text-1',
                'text': 'Kitchen',
                'geometry': {
                    'BoundingBox': {
                        'Left': 0.1,
                        'Top': 0.2,
                        'Width': 0.15,
                        'Height': 0.05
                    }
                }
            },
            {
                'id': 'text-2',
                'text': 'Living Room',
                'geometry': {
                    'BoundingBox': {
                        'Left': 0.5,
                        'Top': 0.3,
                        'Width': 0.2,
                        'Height': 0.05
                    }
                }
            }
        ],
        'layout_blocks': [
            {
                'id': 'layout-1',
                'blockType': 'PAGE',
                'geometry': {
                    'BoundingBox': {
                        'Left': 0.0,
                        'Top': 0.0,
                        'Width': 1.0,
                        'Height': 1.0
                    }
                }
            },
            {
                'id': 'layout-2',
                'blockType': 'TABLE',
                'geometry': {
                    'BoundingBox': {
                        'Left': 0.2,
                        'Top': 0.4,
                        'Width': 0.4,
                        'Height': 0.3
                    }
                }
            },
            {
                'id': 'layout-3',
                'blockType': 'TABLE',
                'geometry': {
                    'BoundingBox': {
                        'Left': 0.6,
                        'Top': 0.5,
                        'Width': 0.3,
                        'Height': 0.2
                    }
                }
            }
        ]
    }


class TestDetectRooms:
    """Test detect_rooms function."""
    
    def test_detect_rooms_with_table_blocks(self, sample_textract_result):
        """Test room detection using TABLE blocks."""
        rooms = detect_rooms(sample_textract_result)
        
        assert len(rooms) == 2  # Two TABLE blocks
        
        # Check first room
        room1 = rooms[0]
        assert room1['id'] == 'room_001'
        assert len(room1['bounding_box']) == 4
        assert room1['bounding_box'][0] < room1['bounding_box'][2]  # x_min < x_max
        assert room1['bounding_box'][1] < room1['bounding_box'][3]  # y_min < y_max
        assert 'confidence' in room1
        assert 0 <= room1['confidence'] <= 1
        
        # Check second room
        room2 = rooms[1]
        assert room2['id'] == 'room_002'
        assert len(room2['bounding_box']) == 4
    
    def test_detect_rooms_with_page_blocks_only(self):
        """Test room detection fallback to PAGE blocks."""
        textract_result = {
            'text_blocks': [],
            'layout_blocks': [
                {
                    'id': 'layout-1',
                    'blockType': 'PAGE',
                    'geometry': {
                        'BoundingBox': {
                            'Left': 0.0,
                            'Top': 0.0,
                            'Width': 1.0,
                            'Height': 1.0
                        }
                    }
                }
            ]
        }
        
        rooms = detect_rooms(textract_result)
        
        assert len(rooms) == 1
        assert rooms[0]['id'] == 'room_001'
        assert rooms[0]['confidence'] == 0.6  # Lower confidence for fallback
    
    def test_detect_rooms_no_layout_blocks(self):
        """Test room detection with no layout blocks (fallback to default)."""
        textract_result = {
            'text_blocks': [],
            'layout_blocks': []
        }
        
        rooms = detect_rooms(textract_result)
        
        assert len(rooms) == 1
        assert rooms[0]['id'] == 'room_001'
        assert rooms[0]['bounding_box'] == [0, 0, 1000, 1000]  # Default room
        assert rooms[0]['confidence'] == 0.5  # Low confidence for default
    
    def test_detect_rooms_bounding_box_format(self, sample_textract_result):
        """Test that bounding boxes are in correct format [x_min, y_min, x_max, y_max]."""
        rooms = detect_rooms(sample_textract_result)
        
        for room in rooms:
            bbox = room['bounding_box']
            assert len(bbox) == 4
            assert isinstance(bbox[0], int)  # x_min
            assert isinstance(bbox[1], int)  # y_min
            assert isinstance(bbox[2], int)  # x_max
            assert isinstance(bbox[3], int)  # y_max
            assert bbox[0] < bbox[2]  # x_min < x_max
            assert bbox[1] < bbox[3]  # y_min < y_max
    
    def test_detect_rooms_name_hints(self, sample_textract_result):
        """Test that room name hints are extracted when available."""
        rooms = detect_rooms(sample_textract_result)
        
        # At least some rooms should have name hints if text blocks are nearby
        rooms_with_names = [r for r in rooms if r.get('name_hint')]
        # Name hints are optional, so we just check the structure
        for room in rooms:
            if 'name_hint' in room:
                assert isinstance(room['name_hint'], str)


class TestExtractRoomNameHint:
    """Test _extract_room_name_hint function."""
    
    def test_extract_room_name_hint_found(self):
        """Test extraction of room name hint when text block is within bounding box."""
        text_blocks = [
            {
                'id': 'text-1',
                'text': 'Kitchen',
                'geometry': {
                    'BoundingBox': {
                        'Left': 0.1,
                        'Top': 0.2,
                        'Width': 0.15,
                        'Height': 0.05
                    }
                }
            }
        ]
        
        # Bounding box that contains the text block
        name_hint = _extract_room_name_hint(text_blocks, 50, 100, 300, 400)
        
        assert name_hint == 'Kitchen'
    
    def test_extract_room_name_hint_not_found(self):
        """Test when no text block is within bounding box."""
        text_blocks = [
            {
                'id': 'text-1',
                'text': 'Kitchen',
                'geometry': {
                    'BoundingBox': {
                        'Left': 0.1,
                        'Top': 0.2,
                        'Width': 0.15,
                        'Height': 0.05
                    }
                }
            }
        ]
        
        # Bounding box that doesn't contain the text block
        name_hint = _extract_room_name_hint(text_blocks, 500, 500, 700, 700)
        
        assert name_hint is None
    
    def test_extract_room_name_hint_keyword_matching(self):
        """Test that room keywords are matched."""
        text_blocks = [
            {
                'id': 'text-1',
                'text': 'This is a bedroom',
                'geometry': {
                    'BoundingBox': {
                        'Left': 0.1,
                        'Top': 0.2,
                        'Width': 0.2,
                        'Height': 0.05
                    }
                }
            }
        ]
        
        name_hint = _extract_room_name_hint(text_blocks, 50, 100, 300, 400)
        
        assert name_hint == 'This is a bedroom'

