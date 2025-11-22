from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from app.models.daily_report import AiAnalysis, DailyReport, DailyReportCreate, DailyReportUpdate
from app.repositories.daily_report_repository import DailyReportRepository
from app.services.daily_report_service import DailyReportService

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_report_repository():
    return AsyncMock(spec=DailyReportRepository)


@pytest.fixture
def daily_report_service(mock_report_repository):
    service = DailyReportService()
    service.report_repository = mock_report_repository
    service.ai_integration = AsyncMock()
    # Mock AI and User services if they were active
    # service.ai_service = AsyncMock()
    # service.user_service = AsyncMock()
    return service


@pytest.fixture
def sample_user_id():
    return uuid4()


@pytest.fixture
def sample_report_id():
    return uuid4()


@pytest.fixture
def sample_daily_report_create_data(sample_user_id: UUID):
    return DailyReportCreate(user_id=sample_user_id, raw_text_input="Initial report text")


@pytest.fixture
def sample_daily_report(sample_user_id, sample_report_id):
    return DailyReport(
        id=sample_report_id,
        user_id=sample_user_id,
        raw_text_input="Initial report text",
        ai_analysis=AiAnalysis(summary="Pending"),
        clarified_tasks_summary="Initial report text",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


async def test_submit_daily_report_new(
    daily_report_service: DailyReportService,
    mock_report_repository: AsyncMock,
    sample_user_id: UUID,
    sample_daily_report_create_data: DailyReportCreate,
    sample_report_id: UUID,
):
    mock_report_repository.get_daily_reports_by_user_and_date.return_value = None

    created_report_mock = DailyReport(id=sample_report_id, **sample_daily_report_create_data.model_dump())
    mock_report_repository.create_daily_report.return_value = created_report_mock

    processed_report_mock = DailyReport(
        id=sample_report_id,
        user_id=sample_user_id,
        raw_text_input=sample_daily_report_create_data.raw_text_input,
        ai_analysis=AiAnalysis(summary="AI done"),
        clarified_tasks_summary=sample_daily_report_create_data.raw_text_input,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    with patch.object(daily_report_service, "process_report_with_ai", new_callable=AsyncMock) as mock_process_ai:
        mock_process_ai.return_value = processed_report_mock
        report = await daily_report_service.submit_daily_report(sample_daily_report_create_data, sample_user_id)

    mock_report_repository.get_daily_reports_by_user_and_date.assert_called_once()
    mock_report_repository.create_daily_report.assert_called_once()

    # Check that the create_daily_report was called with the correct user_id
    call_args = mock_report_repository.create_daily_report.call_args[0][0]
    assert call_args.user_id == sample_user_id
    assert call_args.raw_text_input == sample_daily_report_create_data.raw_text_input

    mock_report_repository.update_daily_report.assert_not_called()
    assert report is processed_report_mock


async def test_submit_daily_report_ai_processing_fails(
    daily_report_service: DailyReportService,
    mock_report_repository: AsyncMock,
    sample_user_id: UUID,
    sample_daily_report_create_data: DailyReportCreate,
    sample_report_id: UUID,
):
    mock_report_repository.get_daily_reports_by_user_and_date.return_value = None
    created_report_mock = DailyReport(id=sample_report_id, **sample_daily_report_create_data.model_dump())
    mock_report_repository.create_daily_report.return_value = created_report_mock

    with patch.object(daily_report_service, "process_report_with_ai", new_callable=AsyncMock) as mock_process_ai:
        mock_process_ai.side_effect = Exception("AI processing failed")
        with pytest.raises(Exception):
            await daily_report_service.submit_daily_report(sample_daily_report_create_data, sample_user_id)

    mock_report_repository.create_daily_report.assert_called_once()


async def test_get_report_by_id(
    daily_report_service: DailyReportService,
    mock_report_repository: AsyncMock,
    sample_daily_report: DailyReport,
    sample_report_id: UUID,
):
    mock_report_repository.get_daily_report_by_id.return_value = sample_daily_report
    report = await daily_report_service.get_report_by_id(sample_report_id)
    mock_report_repository.get_daily_report_by_id.assert_called_once_with(sample_report_id)
    assert report == sample_daily_report


async def test_get_report_by_id_not_found(
    daily_report_service: DailyReportService, mock_report_repository: AsyncMock, sample_report_id: UUID
):
    mock_report_repository.get_daily_report_by_id.return_value = None
    report = await daily_report_service.get_report_by_id(sample_report_id)
    mock_report_repository.get_daily_report_by_id.assert_called_once_with(sample_report_id)
    assert report is None


async def test_get_reports_for_user(
    daily_report_service: DailyReportService,
    mock_report_repository: AsyncMock,
    sample_user_id: UUID,
    sample_daily_report: DailyReport,
):
    mock_reports = [sample_daily_report, sample_daily_report]
    mock_report_repository.get_daily_reports_by_user_id.return_value = mock_reports
    reports = await daily_report_service.get_reports_for_user(sample_user_id)
    mock_report_repository.get_daily_reports_by_user_id.assert_called_once_with(sample_user_id)
    assert reports == mock_reports


async def test_get_user_report_for_date(
    daily_report_service: DailyReportService,
    mock_report_repository: AsyncMock,
    sample_user_id: UUID,
    sample_daily_report: DailyReport,
):
    test_date = datetime.utcnow()
    mock_report_repository.get_daily_reports_by_user_and_date.return_value = sample_daily_report
    report = await daily_report_service.get_user_report_for_date(sample_user_id, test_date)
    # We need to assert that the date part of the datetime is used for comparison in the repo mock if it matters there
    # For the service, it just passes it through.
    mock_report_repository.get_daily_reports_by_user_and_date.assert_called_once_with(sample_user_id, test_date)
    assert report == sample_daily_report


async def test_update_report_assessment(
    daily_report_service: DailyReportService,
    mock_report_repository: AsyncMock,
    sample_report_id: UUID,
    sample_daily_report: DailyReport,
):
    assessment_notes = "Good work"
    final_hours = 7.5

    updated_report_mock = sample_daily_report.model_copy(deep=True)
    updated_report_mock.overall_assessment_notes = assessment_notes
    updated_report_mock.final_estimated_hours = final_hours
    updated_report_mock.updated_at = datetime.utcnow()

    mock_report_repository.update_daily_report.return_value = updated_report_mock

    report = await daily_report_service.update_report_assessment(sample_report_id, assessment_notes, final_hours)

    mock_report_repository.update_daily_report.assert_called_once()
    call_args = mock_report_repository.update_daily_report.call_args[0]
    assert call_args[0] == sample_report_id
    update_payload = call_args[1]
    assert isinstance(update_payload, DailyReportUpdate)
    assert update_payload.overall_assessment_notes == assessment_notes
    assert update_payload.final_estimated_hours == final_hours

    assert report is not None
    assert report.overall_assessment_notes == assessment_notes
    assert report.final_estimated_hours == final_hours


async def test_link_commits_to_report(
    daily_report_service: DailyReportService,
    mock_report_repository: AsyncMock,
    sample_report_id: UUID,
    sample_daily_report: DailyReport,
):
    initial_commits = ["commit1"]
    sample_daily_report.linked_commit_ids = initial_commits.copy()

    mock_report_repository.get_daily_report_by_id.return_value = sample_daily_report

    updated_report_mock = sample_daily_report.model_copy(deep=True)
    new_commits_to_link = ["commit2", "commit3"]
    all_commits = sorted(list(set(initial_commits + new_commits_to_link)))
    updated_report_mock.linked_commit_ids = all_commits
    mock_report_repository.update_daily_report.return_value = updated_report_mock

    report = await daily_report_service.link_commits_to_report(sample_report_id, new_commits_to_link)

    mock_report_repository.get_daily_report_by_id.assert_called_once_with(sample_report_id)
    mock_report_repository.update_daily_report.assert_called_once()

    call_args = mock_report_repository.update_daily_report.call_args[0]
    assert call_args[0] == sample_report_id
    update_payload = call_args[1]
    assert isinstance(update_payload, DailyReportUpdate)
    assert (
        sorted(update_payload.linked_commit_ids) == all_commits
    )  # Ensure unique and sorted for comparison if order doesn't matter

    assert report is not None
    assert sorted(report.linked_commit_ids) == all_commits


async def test_link_commits_to_report_no_initial_commits(
    daily_report_service: DailyReportService,
    mock_report_repository: AsyncMock,
    sample_report_id: UUID,
    sample_daily_report: DailyReport,  # This fixture will have some default linked_commit_ids
):
    # Ensure the starting report for this test has no commits
    sample_daily_report.linked_commit_ids = []
    mock_report_repository.get_daily_report_by_id.return_value = sample_daily_report

    updated_report_mock = sample_daily_report.model_copy(deep=True)
    new_commits_to_link = ["commitA", "commitB"]
    updated_report_mock.linked_commit_ids = new_commits_to_link
    mock_report_repository.update_daily_report.return_value = updated_report_mock

    report = await daily_report_service.link_commits_to_report(sample_report_id, new_commits_to_link)

    mock_report_repository.get_daily_report_by_id.assert_called_once_with(sample_report_id)
    mock_report_repository.update_daily_report.assert_called_once()

    call_args = mock_report_repository.update_daily_report.call_args[0]
    update_payload = call_args[1]
    assert sorted(update_payload.linked_commit_ids) == sorted(new_commits_to_link)
    assert report is not None
    assert sorted(report.linked_commit_ids) == sorted(new_commits_to_link)


async def test_link_commits_to_report_non_existent_report(
    daily_report_service: DailyReportService, mock_report_repository: AsyncMock, sample_report_id: UUID
):
    mock_report_repository.get_daily_report_by_id.return_value = None

    report = await daily_report_service.link_commits_to_report(sample_report_id, ["commit1"])

    mock_report_repository.get_daily_report_by_id.assert_called_once_with(sample_report_id)
    mock_report_repository.update_daily_report.assert_not_called()
    assert report is None


async def test_submit_daily_report_ai_service_exception(
    daily_report_service: DailyReportService,
    mock_report_repository: AsyncMock,
    sample_user_id: UUID,
    sample_daily_report_create_data: DailyReportCreate,
    sample_report_id: UUID,
):
    # This test requires uncommenting and mocking the actual AI service call
    # For now, it tests the current placeholder's exception handling block

    mock_report_repository.get_daily_reports_by_user_and_date.return_value = None
    created_report_mock = DailyReport(id=sample_report_id, **sample_daily_report_create_data.model_dump())
    mock_report_repository.create_daily_report.return_value = created_report_mock

    # Make the update_daily_report call within the AI processing block raise an exception
    daily_report_service.ai_integration.analyze_eod_report.return_value = {"summary": "Test summary"}
    mock_report_repository.update_daily_report.side_effect = Exception("AI related DB error")

    report = await daily_report_service.submit_daily_report(sample_daily_report_create_data, sample_user_id)

    mock_report_repository.create_daily_report.assert_called_once()
    mock_report_repository.update_daily_report.assert_called_once()  # Attempted but raised exception

    # Service should catch the exception and return the report without AI data
    assert report is not None
    assert report.id == sample_report_id
    assert report.ai_analysis is None  # Placeholder AI data was not set
    assert report.raw_text_input == sample_daily_report_create_data.raw_text_input


# Add a pass statement or ensure the file ends with a newline if necessary
# For now, just ensuring it ends cleanly after the last test function.
