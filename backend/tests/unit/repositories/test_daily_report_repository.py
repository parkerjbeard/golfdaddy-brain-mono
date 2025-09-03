from datetime import datetime, timedelta, timezone
from typing import Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import UUID, uuid4

import pytest

from app.models.daily_report import AiAnalysis, DailyReport, DailyReportCreate, DailyReportUpdate
from app.repositories.daily_report_repository import DailyReportRepository

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_supabase_client():
    """Create a mock Supabase client for testing."""
    mock_client = MagicMock()
    mock_client.table.return_value = mock_client
    mock_client.insert.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.update.return_value = mock_client
    mock_client.delete.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.single.return_value = mock_client
    mock_client.order.return_value = mock_client
    mock_client.limit.return_value = mock_client
    return mock_client


@pytest.fixture
def report_repository(mock_supabase_client):
    """Create a repository with mocked Supabase client."""
    return DailyReportRepository(client=mock_supabase_client)


@pytest.fixture
def sample_user_id():
    return uuid4()


@pytest.fixture
def sample_report_create(sample_user_id: UUID):
    return DailyReportCreate(user_id=sample_user_id, raw_text_input="Test report content")


async def test_create_daily_report(
    report_repository: DailyReportRepository, sample_report_create: DailyReportCreate, mock_supabase_client
):
    # Setup mock response
    mock_response_data = {
        "id": str(uuid4()),
        "user_id": str(sample_report_create.user_id),
        "raw_text_input": sample_report_create.raw_text_input,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "report_date": datetime.now(timezone.utc).date().isoformat(),
        "status": "submitted",
    }
    mock_supabase_client.execute.return_value = MagicMock(data=[mock_response_data], error=None)

    created_report = await report_repository.create_daily_report(sample_report_create)
    assert created_report is not None
    assert isinstance(created_report, DailyReport)
    assert created_report.user_id == sample_report_create.user_id
    assert created_report.raw_text_input == sample_report_create.raw_text_input
    assert created_report.id is not None
    assert isinstance(created_report.created_at, datetime)
    assert isinstance(created_report.updated_at, datetime)
    assert created_report.report_date is not None


async def test_get_daily_report_by_id(
    report_repository: DailyReportRepository, sample_report_create: DailyReportCreate, mock_supabase_client
):
    report_id = uuid4()
    mock_response_data = {
        "id": str(report_id),
        "user_id": str(sample_report_create.user_id),
        "raw_text_input": sample_report_create.raw_text_input,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "report_date": datetime.now(timezone.utc).date().isoformat(),
        "status": "submitted",
    }

    # Mock for create
    mock_supabase_client.execute.return_value = MagicMock(data=[mock_response_data], error=None)
    created_report = await report_repository.create_daily_report(sample_report_create)

    # Mock for get by id
    mock_supabase_client.execute.return_value = MagicMock(data=mock_response_data, error=None)
    retrieved_report = await report_repository.get_daily_report_by_id(report_id)
    assert retrieved_report is not None


async def test_get_daily_report_by_id_not_found(report_repository: DailyReportRepository, mock_supabase_client):
    non_existent_id = uuid4()
    # Mock empty response
    mock_supabase_client.execute.return_value = MagicMock(data=None, error=None)
    retrieved_report = await report_repository.get_daily_report_by_id(non_existent_id)
    assert retrieved_report is None


async def test_get_daily_reports_by_user_id(report_repository: DailyReportRepository, sample_user_id: UUID):
    user1_id = sample_user_id
    user2_id = uuid4()

    report1_create = DailyReportCreate(user_id=user1_id, raw_text_input="User1 Report1")
    report2_create = DailyReportCreate(user_id=user1_id, raw_text_input="User1 Report2")
    report3_create = DailyReportCreate(user_id=user2_id, raw_text_input="User2 Report1")

    await report_repository.create_daily_report(report1_create)
    await report_repository.create_daily_report(report2_create)
    await report_repository.create_daily_report(report3_create)

    user1_reports = await report_repository.get_daily_reports_by_user_id(user1_id)
    assert len(user1_reports) == 2
    for report in user1_reports:
        assert report.user_id == user1_id

    user2_reports = await report_repository.get_daily_reports_by_user_id(user2_id)
    assert len(user2_reports) == 1
    assert user2_reports[0].user_id == user2_id

    non_existent_user_reports = await report_repository.get_daily_reports_by_user_id(uuid4())
    assert len(non_existent_user_reports) == 0


async def test_get_daily_reports_by_user_and_date(report_repository: DailyReportRepository, sample_user_id: UUID):
    user_id = sample_user_id
    today = datetime.now(timezone.utc)
    yesterday = today - timedelta(days=1)

    # Create reports with specific dates by manually setting them in the DB for test precision
    # as the create_daily_report in repo sets report_date = datetime.utcnow()
    from app.repositories.daily_report_repository import _daily_reports_db

    report_today_data = DailyReportCreate(user_id=user_id, raw_text_input="Today's report")
    report_today = DailyReport(**report_today_data.model_dump(), report_date=today, id=uuid4())
    _daily_reports_db[report_today.id] = report_today

    report_yesterday_data = DailyReportCreate(user_id=user_id, raw_text_input="Yesterday's report")
    report_yesterday = DailyReport(**report_yesterday_data.model_dump(), report_date=yesterday, id=uuid4())
    _daily_reports_db[report_yesterday.id] = report_yesterday

    # Different user, same date
    other_user_id = uuid4()
    report_other_user_today_data = DailyReportCreate(user_id=other_user_id, raw_text_input="Other user today")
    report_other_user_today = DailyReport(**report_other_user_today_data.model_dump(), report_date=today, id=uuid4())
    _daily_reports_db[report_other_user_today.id] = report_other_user_today

    retrieved_today = await report_repository.get_daily_reports_by_user_and_date(user_id, today)
    assert retrieved_today is not None
    assert retrieved_today.id == report_today.id
    assert retrieved_today.report_date.date() == today.date()

    retrieved_yesterday = await report_repository.get_daily_reports_by_user_and_date(user_id, yesterday)
    assert retrieved_yesterday is not None
    assert retrieved_yesterday.id == report_yesterday.id
    assert retrieved_yesterday.report_date.date() == yesterday.date()

    retrieved_non_existent_date = await report_repository.get_daily_reports_by_user_and_date(
        user_id, today - timedelta(days=2)
    )
    assert retrieved_non_existent_date is None

    retrieved_other_user = await report_repository.get_daily_reports_by_user_and_date(other_user_id, today)
    assert retrieved_other_user is not None
    assert retrieved_other_user.id == report_other_user_today.id


async def test_update_daily_report(report_repository: DailyReportRepository, sample_report_create: DailyReportCreate):
    created_report = await report_repository.create_daily_report(sample_report_create)
    original_updated_at = created_report.updated_at

    update_payload = DailyReportUpdate(
        raw_text_input="Updated text",
        clarified_tasks_summary="Clarified summary",
        overall_assessment_notes="Assessed.",
        final_estimated_hours=5.0,
        linked_commit_ids=["commit1", "commit2"],
        ai_analysis=AiAnalysis(summary="Updated AI", estimated_hours=4.0),
    )

    # Allow a small delay for updated_at to change
    await asyncio.sleep(0.01)

    updated_report = await report_repository.update_daily_report(created_report.id, update_payload)
    assert updated_report is not None
    assert updated_report.id == created_report.id
    assert updated_report.raw_text_input == "Updated text"
    assert updated_report.clarified_tasks_summary == "Clarified summary"
    assert updated_report.overall_assessment_notes == "Assessed."
    assert updated_report.final_estimated_hours == 5.0
    assert updated_report.linked_commit_ids == ["commit1", "commit2"]
    assert updated_report.ai_analysis is not None
    assert updated_report.ai_analysis.summary == "Updated AI"
    assert updated_report.ai_analysis.estimated_hours == 4.0
    assert updated_report.updated_at > original_updated_at

    # Verify in DB
    from app.repositories.daily_report_repository import _daily_reports_db

    assert _daily_reports_db[created_report.id].raw_text_input == "Updated text"


async def test_update_daily_report_partial(
    report_repository: DailyReportRepository, sample_report_create: DailyReportCreate
):
    created_report = await report_repository.create_daily_report(sample_report_create)
    update_payload = DailyReportUpdate(raw_text_input="Partial update text")

    updated_report = await report_repository.update_daily_report(created_report.id, update_payload)
    assert updated_report is not None
    assert updated_report.raw_text_input == "Partial update text"
    assert updated_report.clarified_tasks_summary == created_report.clarified_tasks_summary  # Should be unchanged


async def test_update_daily_report_not_found(report_repository: DailyReportRepository):
    non_existent_id = uuid4()
    update_payload = DailyReportUpdate(raw_text_input="Test")
    updated_report = await report_repository.update_daily_report(non_existent_id, update_payload)
    assert updated_report is None


async def test_delete_daily_report(report_repository: DailyReportRepository, sample_report_create: DailyReportCreate):
    created_report = await report_repository.create_daily_report(sample_report_create)
    report_id = created_report.id

    # Verify it's in the DB before delete
    from app.repositories.daily_report_repository import _daily_reports_db

    assert report_id in _daily_reports_db

    delete_result = await report_repository.delete_daily_report(report_id)
    assert delete_result is True
    assert report_id not in _daily_reports_db

    # Try to get it again
    retrieved_report = await report_repository.get_daily_report_by_id(report_id)
    assert retrieved_report is None


async def test_delete_daily_report_not_found(report_repository: DailyReportRepository):
    non_existent_id = uuid4()
    delete_result = await report_repository.delete_daily_report(non_existent_id)
    assert delete_result is False


async def test_get_all_daily_reports(report_repository: DailyReportRepository, sample_user_id: UUID):
    await report_repository.create_daily_report(DailyReportCreate(user_id=sample_user_id, raw_text_input="R1"))
    await report_repository.create_daily_report(DailyReportCreate(user_id=uuid4(), raw_text_input="R2"))

    all_reports = await report_repository.get_all_daily_reports()
    assert len(all_reports) == 2

    # Test with empty DB
    from app.repositories.daily_report_repository import _daily_reports_db

    _daily_reports_db.clear()
    all_reports_empty = await report_repository.get_all_daily_reports()
    assert len(all_reports_empty) == 0


# Need to import asyncio for await asyncio.sleep(0.01)
import asyncio
