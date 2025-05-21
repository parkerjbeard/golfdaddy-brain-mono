import pytest
import uuid
import asyncio
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone

from app.models.task import Task, TaskStatus
from app.models.user import User, UserRole
from app.models.commit import Commit
from app.services.kpi_service import KpiService, UserWidgetSummary
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.repositories.commit_repository import CommitRepository
from app.repositories.daily_report_repository import DailyReportRepository
from app.core.exceptions import ResourceNotFoundError, DatabaseError

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration

class TestKpiServiceIntegration:
    """
    Integration tests for KpiService.
    
    These tests interact with a real test database to verify:
    - Calculation of KPIs from persisted data
    - Performance metrics across different data types
    - Aggregation of data for reports
    """
    
    @pytest.fixture(scope="function")
    async def setup_test_db(self):
        """
        Fixture to prepare the test database environment.
        
        This sets up clean database tables before each test
        and cleans up after the test completes.
        """
        # Generate unique table names for this test run to isolate tests
        test_id = str(uuid.uuid4()).replace("-", "_")
        
        # Define test table names
        users_table = f"users_test_{test_id}"
        tasks_table = f"tasks_test_{test_id}"
        commits_table = f"commits_test_{test_id}"
        daily_reports_table = f"daily_reports_test_{test_id}"
        
        # Patch the repository classes to use our test tables
        user_repo_patch = patch('app.repositories.user_repository.UserRepository._table', users_table)
        task_repo_patch = patch('app.repositories.task_repository.TaskRepository._table', tasks_table)
        commit_repo_patch = patch('app.repositories.commit_repository.CommitRepository._table', commits_table)
        daily_report_repo_patch = patch('app.repositories.daily_report_repository.DailyReportRepository._table', daily_reports_table)
        
        # Apply all patches
        user_repo_patch.start()
        task_repo_patch.start()
        commit_repo_patch.start()
        daily_report_repo_patch.start()
        
        # Create and return the services and repositories for testing
        user_repo = UserRepository()
        task_repo = TaskRepository()
        commit_repo = CommitRepository()
        daily_report_repo = DailyReportRepository()
        kpi_service = KpiService()
        
        # Return test fixtures
        yield {
            "kpi_service": kpi_service,
            "user_repo": user_repo,
            "task_repo": task_repo,
            "commit_repo": commit_repo,
            "daily_report_repo": daily_report_repo,
            "users_table": users_table,
            "tasks_table": tasks_table,
            "commits_table": commits_table,
            "daily_reports_table": daily_reports_table
        }
        
        # Stop all patches
        user_repo_patch.stop()
        task_repo_patch.stop()
        commit_repo_patch.stop()
        daily_report_repo_patch.stop()
    
    @pytest.fixture(scope="function")
    async def setup_test_data(self, setup_test_db):
        """Create test data for KPI calculations."""
        user_repo = setup_test_db["user_repo"]
        task_repo = setup_test_db["task_repo"]
        commit_repo = setup_test_db["commit_repo"]
        daily_report_repo = setup_test_db["daily_report_repo"]
        
        # Create a test developer user
        dev_id = uuid.uuid4()
        developer = User(
            id=dev_id,
            name="Test Developer",
            email="dev@example.com",
            role=UserRole.DEVELOPER,
            github_username="testdev",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            is_active=True
        )
        
        # Create a test manager user
        manager_id = uuid.uuid4()
        manager = User(
            id=manager_id,
            name="Test Manager",
            email="manager@example.com",
            role=UserRole.MANAGER,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            is_active=True
        )
        
        # Create users in the database
        await user_repo.create_user(developer)
        await user_repo.create_user(manager)
        
        # Create test tasks for the developer
        task_ids = []
        
        # Create a completed task
        completed_task = Task(
            title="Completed Task",
            description="A task that has been completed",
            assignee_id=dev_id,
            creator_id=manager_id,
            responsible_id=dev_id,
            accountable_id=manager_id,
            status=TaskStatus.COMPLETED,
            created_at=datetime.now(timezone.utc) - timedelta(days=5),
            updated_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        
        # Create an in-progress task
        in_progress_task = Task(
            title="In-Progress Task",
            description="A task that is in progress",
            assignee_id=dev_id,
            creator_id=manager_id,
            responsible_id=dev_id,
            accountable_id=manager_id,
            status=TaskStatus.IN_PROGRESS,
            created_at=datetime.now(timezone.utc) - timedelta(days=3),
            updated_at=datetime.now(timezone.utc) - timedelta(hours=6)
        )
        
        # Create the tasks in the database
        completed_task_db = await task_repo.create_task(completed_task)
        in_progress_task_db = await task_repo.create_task(in_progress_task)
        
        task_ids.append(completed_task_db.id)
        task_ids.append(in_progress_task_db.id)
        
        # Create test commits for the developer
        commit_ids = []
        
        # Create commits from the last week
        for i in range(5):
            commit = Commit(
                commit_hash=f"abc{i}def{uuid.uuid4().hex[:8]}",
                repository="test-repo",
                user_id=dev_id,
                github_username="testdev",
                commit_message=f"Test commit {i}",
                commit_timestamp=datetime.now(timezone.utc) - timedelta(days=i),
                files_changed=i + 1,
                lines_added=i * 10,
                lines_deleted=i * 2,
                ai_estimated_hours=float(i + 1.5),
                seniority_score=float(0.7 + 0.05 * i),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            
            commit_db = await commit_repo.create_commit(commit)
            commit_ids.append(commit_db.id)
        
        # Return the test data IDs
        return {
            "developer_id": dev_id,
            "manager_id": manager_id,
            "task_ids": task_ids,
            "commit_ids": commit_ids
        }
    
    @pytest.mark.asyncio
    async def test_get_user_performance_summary(self, setup_test_db, setup_test_data):
        """Test retrieving a performance summary for a user."""
        kpi_service = setup_test_db["kpi_service"]
        test_data = await setup_test_data
        
        # Get performance summary for the developer
        period_days = 7
        summary = await kpi_service.get_user_performance_summary(
            test_data["developer_id"], 
            period_days=period_days
        )
        
        # Verify the summary contains the expected data
        assert summary is not None
        assert summary["user_id"] == str(test_data["developer_id"])
        assert "period_start_date" in summary
        assert "period_end_date" in summary
        
        # Verify commit metrics
        assert summary["total_commits_in_period"] == 5  # We created 5 test commits
        assert summary["total_commit_ai_estimated_hours"] > 0
        assert summary["average_commit_seniority_score"] > 0
    
    @pytest.mark.asyncio
    async def test_get_bulk_widget_summaries(self, setup_test_db, setup_test_data):
        """Test retrieving widget summaries for all developers."""
        kpi_service = setup_test_db["kpi_service"]
        test_data = await setup_test_data
        
        # Define date range for the test
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=7)
        
        # Get widget summaries for all developers
        summaries = await kpi_service.get_bulk_widget_summaries(start_date, end_date)
        
        # Verify the summaries
        assert summaries is not None
        assert len(summaries) > 0
        
        # Find the summary for our test developer
        dev_summary = next((s for s in summaries if s.user_id == test_data["developer_id"]), None)
        
        # Verify the developer's summary
        assert dev_summary is not None
        assert dev_summary.name == "Test Developer"
        assert dev_summary.total_ai_estimated_commit_hours > 0
    
    @pytest.mark.asyncio
    async def test_nonexistent_user_performance_summary(self, setup_test_db):
        """Test retrieving a performance summary for a non-existent user."""
        kpi_service = setup_test_db["kpi_service"]
        
        # Try to get performance summary for a non-existent user
        nonexistent_id = uuid.uuid4()
        
        # Verify it raises a ResourceNotFoundError
        with pytest.raises(ResourceNotFoundError):
            await kpi_service.get_user_performance_summary(nonexistent_id) 