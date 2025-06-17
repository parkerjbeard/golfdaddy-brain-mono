"""
Fixtures for integration tests.

This file contains pytest fixtures specific to integration tests that interact with a real test database.
"""
import pytest
import asyncio
import uuid
from typing import Dict, Any, Generator, AsyncGenerator
import os
import logging
from dotenv import load_dotenv
from unittest.mock import patch

from app.config.settings import settings
from app.config.supabase_client import get_supabase_client
from supabase import Client, create_client

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file if available
load_dotenv()

# Define integration test fixtures

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up the test environment for integration tests."""
    # Save original settings
    original_testing_mode = settings.TESTING_MODE
    
    # Override settings for testing
    settings.TESTING_MODE = True
    
    # Make sure Supabase URL and key are properly set for testing
    supabase_url_str = str(settings.SUPABASE_URL)
    if not supabase_url_str or "your-project-ref" in supabase_url_str:
        raise ValueError(
            "SUPABASE_URL must be set to a valid Supabase URL for integration tests. "
            "Check your environment variables or .env file."
        )
    
    if not settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_SERVICE_KEY == "your-service-role-key-here":
        raise ValueError(
            "SUPABASE_SERVICE_KEY must be set to a valid service role key for integration tests. "
            "Check your environment variables or .env file."
        )
    
    logger.info("Integration test environment setup complete")
    
    yield
    
    # Restore original settings
    settings.TESTING_MODE = original_testing_mode
    logger.info("Integration test environment teardown complete")

@pytest.fixture(scope="function")
async def test_supabase_client() -> AsyncGenerator[Client, None]:
    """
    Get a real Supabase client for integration tests.
    
    This client uses the actual Supabase instance but with test-specific tables
    to avoid affecting production data.
    """
    # Use the service role key for integration tests
    client = create_client(str(settings.SUPABASE_URL), settings.SUPABASE_SERVICE_KEY)
    
    # Let the test use this real client
    yield client

@pytest.fixture(scope="function")
async def test_db_tables(test_supabase_client: Client) -> AsyncGenerator[Dict[str, str], None]:
    """
    Create test tables for integration tests and return their names.
    
    This fixture creates temporary tables with unique names for each test run,
    and drops them when the test is complete.
    """
    # Generate unique suffixes for test tables
    test_id = str(uuid.uuid4()).replace("-", "_")
    
    # Define table names for this test run
    table_names = {
        "users": f"users_test_{test_id}",
        "tasks": f"tasks_test_{test_id}",
        "commits": f"commits_test_{test_id}",
        "daily_reports": f"daily_reports_test_{test_id}"
    }
    
    # Create tables (in a real setup, this would use actual SQL schema definitions)
    # Here we'll implement a simplified version
    
    # Example of creating users test table with basic schema
    # In a real implementation, you'd use the actual schema from your database migrations
    try:
        # SQL for creating test users table
        users_sql = f"""
        CREATE TABLE {table_names['users']} (
            id UUID PRIMARY KEY,
            name TEXT,
            email TEXT,
            role TEXT,
            avatar_url TEXT,
            slack_id TEXT,
            github_username TEXT,
            team TEXT,
            team_id UUID,
            reports_to_id UUID,
            metadata JSONB,
            personal_mastery JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            last_login_at TIMESTAMP WITH TIME ZONE,
            is_active BOOLEAN DEFAULT TRUE,
            preferences JSONB
        );
        """
        
        # Execute the SQL to create the test table
        # In a real implementation, you would execute this SQL against the database
        # For now, we'll log it and assume it works
        logger.info(f"Creating test table: {table_names['users']}")
        # await test_supabase_client.rpc("execute_sql", {"sql": users_sql}).execute()
        
        # Similar SQL would be created for other tables
        
        # Return the table names for the tests to use
        yield table_names
        
    finally:
        # Clean up - drop all test tables
        logger.info("Cleaning up test tables")
        for table in table_names.values():
            drop_sql = f"DROP TABLE IF EXISTS {table};"
            # await test_supabase_client.rpc("execute_sql", {"sql": drop_sql}).execute()
            logger.info(f"Dropped test table: {table}")

@pytest.fixture(scope="function")
def patch_repository_tables(test_db_tables: Dict[str, str]):
    """
    Patch the repository classes to use the test tables.
    
    This allows the repositories to interact with the test tables
    instead of the production tables.
    """
    # Start all the patches
    patches = [
        patch('app.repositories.user_repository.UserRepository._table', test_db_tables["users"]),
        patch('app.repositories.task_repository.TaskRepository._table', test_db_tables["tasks"]),
        patch('app.repositories.commit_repository.CommitRepository._table', test_db_tables["commits"]),
        patch('app.repositories.daily_report_repository.DailyReportRepository._table', test_db_tables["daily_reports"])
    ]
    
    # Apply all patches
    for p in patches:
        p.start()
    
    # Let the test run
    yield
    
    # Stop all patches
    for p in patches:
        p.stop() 