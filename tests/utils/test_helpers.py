"""
Common test helper functions and utilities.
"""
import json
import os
from typing import Any, Dict, Optional


def load_test_data(filename: str) -> Dict[str, Any]:
    """
    Load test data from a JSON file in the fixtures directory.
    
    Args:
        filename: Name of the JSON file to load
        
    Returns:
        Dictionary containing the test data
    """
    fixtures_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures")
    filepath = os.path.join(fixtures_dir, filename)
    
    with open(filepath, 'r') as f:
        return json.load(f)


def assert_dict_contains_subset(subset: Dict[str, Any], full_dict: Dict[str, Any]) -> None:
    """
    Assert that a dictionary contains all the keys and values from a subset.
    
    Args:
        subset: Dictionary of expected key-value pairs
        full_dict: Dictionary that should contain all items from subset
    """
    for key, value in subset.items():
        assert key in full_dict, f"Key '{key}' not found in dictionary"
        assert full_dict[key] == value, f"Value for key '{key}' doesn't match: {full_dict[key]} != {value}"


def get_test_file_path(relative_path: str) -> str:
    """
    Get the absolute path to a test file.
    
    Args:
        relative_path: Path relative to the tests directory
        
    Returns:
        Absolute path to the file
    """
    base_dir = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base_dir, relative_path) 