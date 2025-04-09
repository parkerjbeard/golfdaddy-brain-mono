"""
Shared fixtures for all tests in the project.

This file contains pytest fixtures that are accessible to all tests.
"""
import pytest
import os
import sys

# Add the project root to the path so that we can import from the package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Define shared fixtures here
@pytest.fixture
def app_config():
    """Return a base configuration for tests."""
    return {
        "testing": True,
        "debug": True,
    }


@pytest.fixture
def test_client():
    """Create a test client for the app."""
    # This is a placeholder. Implement based on actual app structure
    pass 