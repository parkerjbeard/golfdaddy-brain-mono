import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
from unittest.mock import AsyncMock

from app.main import app
from app.models.user import User, UserRole
from app.models.commit import Commit
from app.models.daily_report import DailyReport, AiAnalysis
from app.api.developer_insights_endpoints import (
    get_commit_repository,
    get_daily_report_repository,
    get_current_user,
)

pytestmark = pytest.mark.asyncio

# Sample data
SAMPLE_DATE = "2023-10-26"

@pytest.fixture
def mock_commit_repo():
    repo = AsyncMock()
    repo.get_commits_by_user_and_date_range.return_value = [
        Commit(commit_hash="abc123", commit_timestamp="2023-10-26T12:00:00Z")
    ]
    return repo

@pytest.fixture
def mock_report_repo():
    repo = AsyncMock()
    repo.get_daily_reports_by_user_and_date.return_value = DailyReport(
        id=uuid4(),
        user_id=uuid4(),
        raw_text_input="Report",
        ai_analysis=AiAnalysis(summary="done"),
    )
    return repo

@pytest.fixture
def test_client(mock_commit_repo, mock_report_repo):
    user = User(id=uuid4(), email="mgr@example.com", role=UserRole.MANAGER)

    app.dependency_overrides[get_commit_repository] = lambda: mock_commit_repo
    app.dependency_overrides[get_daily_report_repository] = lambda: mock_report_repo
    app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_summary_authorized_for_manager(test_client):
    other_user_id = uuid4()
    response = test_client.get(f"/api/v1/insights/developer/{other_user_id}/daily_summary/{SAMPLE_DATE}")
    assert response.status_code == 200


def test_summary_forbidden_without_privilege(mock_commit_repo, mock_report_repo):
    user = User(id=uuid4(), email="dev@example.com", role=UserRole.DEVELOPER)
    app.dependency_overrides[get_commit_repository] = lambda: mock_commit_repo
    app.dependency_overrides[get_daily_report_repository] = lambda: mock_report_repo
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/insights/developer/{uuid4()}/daily_summary/{SAMPLE_DATE}"
        )
        assert response.status_code == 403
    app.dependency_overrides.clear()

