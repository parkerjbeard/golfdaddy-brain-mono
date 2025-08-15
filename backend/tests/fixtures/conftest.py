"""
Fixtures specific to test data.
"""

import json
import os
from typing import Any, Dict

import pytest


@pytest.fixture
def sample_data() -> Dict[str, Any]:
    """
    Load sample data from the JSON file.
    """
    fixture_path = os.path.join(os.path.dirname(__file__), "sample_data.json")
    with open(fixture_path, "r") as f:
        return json.load(f)


@pytest.fixture
def sample_users(sample_data) -> Dict[str, Any]:
    """
    Get sample user data.
    """
    return sample_data["users"]


@pytest.fixture
def sample_racis(sample_data) -> Dict[str, Any]:
    """
    Get sample RACI data.
    """
    return sample_data["racis"]
