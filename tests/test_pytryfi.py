"""Test embedded pytryfi functionality."""
from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from custom_components.tryfi.pytryfi import PyTryFi
from custom_components.tryfi.pytryfi.exceptions import TryFiError


def test_pytryfi_update_error_handling():
    """Test PyTryFi update method error handling."""
    with patch("custom_components.tryfi.pytryfi.PyTryFi.updateBases") as mock_update_bases:
        with patch("custom_components.tryfi.pytryfi.PyTryFi.updatePets") as mock_update_pets:
            # Create instance without going through __init__
            tryfi = object.__new__(PyTryFi)
            
            # Test both updates failing
            mock_update_bases.side_effect = Exception("Base update failed")
            mock_update_pets.side_effect = Exception("Pet update failed")
            
            with pytest.raises(Exception) as exc_info:
                tryfi.update()
            
            assert "Base update failed" in str(exc_info.value)
            assert "Pet update failed" in str(exc_info.value)
            
            # Test only base update failing
            mock_update_bases.side_effect = Exception("Base update failed")
            mock_update_pets.side_effect = None
            
            with pytest.raises(Exception) as exc_info:
                tryfi.update()
            
            assert "Base update failed" in str(exc_info.value)
            
            # Test only pet update failing
            mock_update_bases.side_effect = None
            mock_update_pets.side_effect = Exception("Pet update failed")
            
            with pytest.raises(Exception) as exc_info:
                tryfi.update()
            
            assert "Pet update failed" in str(exc_info.value)
            
            # Test both succeed
            mock_update_bases.side_effect = None
            mock_update_pets.side_effect = None
            
            # Should not raise
            tryfi.update()

def test_hex_to_rgb_edge_cases():
    """Test hex to RGB conversion edge cases."""
    from custom_components.tryfi.light import hex_to_rgb
    
    # Valid cases
    assert hex_to_rgb("#FFFFFF") == (255, 255, 255)
    assert hex_to_rgb("000000") == (0, 0, 0)
    assert hex_to_rgb("#123456") == (18, 52, 86)
    
    # Edge cases that should raise
    with pytest.raises(ValueError):
        hex_to_rgb("#FFF")  # Too short
    
    with pytest.raises(ValueError):
        hex_to_rgb("#GGGGGG")  # Invalid hex
    
    with pytest.raises(ValueError):
        hex_to_rgb("")  # Empty string


def test_color_distance_calculation():
    """Test color distance calculation."""
    from custom_components.tryfi.light import calculate_distance
    
    # Same color
    assert calculate_distance((0, 0, 0), (0, 0, 0)) == 0
    
    # Maximum distance (black to white)
    distance = calculate_distance((0, 0, 0), (255, 255, 255))
    assert distance == pytest.approx(441.67, rel=0.01)
    
    # Partial distances
    assert calculate_distance((100, 100, 100), (150, 150, 150)) == pytest.approx(86.60, rel=0.01)


def test_find_closest_color_empty_map():
    """Test finding closest color with empty color map."""
    from custom_components.tryfi.light import find_closest_color_code
    
    # Empty color map should return default
    assert find_closest_color_code((255, 0, 0), {}) == 8  # Default white


def test_embedded_pytryfi_import():
    """Test that embedded pytryfi can be imported."""
    from custom_components.tryfi.pytryfi import PyTryFi
    
    # Should be able to import without error
    assert PyTryFi is not None