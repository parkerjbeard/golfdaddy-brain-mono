from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.models.daily_report import (
    AiAnalysis,
    ClarificationRequest,
    ClarificationStatus,
    DailyReport,
    DailyReportCreate,
    DailyReportUpdate,
)


def test_ai_analysis_creation_minimal():
    ai_analysis = AiAnalysis(summary="Test summary")
    assert ai_analysis.summary == "Test summary"
    assert ai_analysis.estimated_hours is None
    assert ai_analysis.estimated_difficulty is None
    assert ai_analysis.clarification_requests == []


def test_ai_analysis_creation_full():
    cr = ClarificationRequest(question="Need more details?", original_text="details about what?", requested_by_ai=True)
    ai_analysis = AiAnalysis(
        summary="Full test", estimated_hours=5.5, estimated_difficulty="Medium", clarification_requests=[cr]
    )
    assert ai_analysis.summary == "Full test"
    assert ai_analysis.estimated_hours == 5.5
    assert ai_analysis.estimated_difficulty == "Medium"
    assert len(ai_analysis.clarification_requests) == 1
    assert ai_analysis.clarification_requests[0].question == "Need more details?"


def test_clarification_request_creation_defaults():
    cr = ClarificationRequest(question="A question", original_text="context for question")
    assert cr.question == "A question"
    assert cr.answer is None
    assert cr.status == ClarificationStatus.PENDING
    assert cr.requested_by_ai is False
    assert isinstance(cr.created_at, datetime)


def test_clarification_request_creation_with_status():
    cr = ClarificationRequest(
        question="A question",
        original_text="Some original text for context",
        answer="An answer",
        status=ClarificationStatus.ANSWERED,
        requested_by_ai=True,
    )
    assert cr.status == ClarificationStatus.ANSWERED
    assert cr.answer == "An answer"
    assert cr.requested_by_ai is True


def test_daily_report_create_fields():
    base_data = {"user_id": uuid4(), "raw_text_input": "Base text input"}
    report_create_instance = DailyReportCreate(**base_data)
    assert report_create_instance.user_id == base_data["user_id"]
    assert report_create_instance.raw_text_input == base_data["raw_text_input"]
    # Fields not in DailyReportCreate are not asserted here


def test_daily_report_create_creation():
    create_data = {"user_id": uuid4(), "raw_text_input": "Create text input"}
    report_create = DailyReportCreate(**create_data)
    assert report_create.user_id == create_data["user_id"]
    assert report_create.raw_text_input == create_data["raw_text_input"]
    # Ensure it doesn't have fields not in DailyReportCreate (like ai_analysis from DailyReportBase directly)
    with pytest.raises(
        AttributeError
    ):  # Pydantic models don't raise AttributeError for non-existent fields during init, they ignore.
        # Accessing it after would. Better to check model_fields.
        _ = report_create.ai_analysis
    assert "ai_analysis" not in report_create.model_fields


def test_daily_report_update_creation_empty():
    report_update = DailyReportUpdate()
    assert report_update.model_dump(exclude_unset=True) == {}  # No fields set


def test_daily_report_update_creation_with_data():
    update_data = {"raw_text_input": "Updated text", "final_estimated_hours": 3.0}
    report_update = DailyReportUpdate(**update_data)
    assert report_update.raw_text_input == "Updated text"
    assert report_update.final_estimated_hours == 3.0
    assert report_update.clarified_tasks_summary is None


def test_daily_report_db_model_creation():
    user_id = uuid4()
    report_id = uuid4()
    now = datetime.now(timezone.utc)

    ai_analysis_data = AiAnalysis(summary="DB model AI summary")
    report_data = {
        "id": report_id,
        "user_id": user_id,
        "raw_text_input": "DB model text",
        "ai_analysis": ai_analysis_data,
        "created_at": now,
        "updated_at": now,
    }
    # Minimal required fields for DailyReport (which inherits from DailyReportBase)
    db_report = DailyReport(**report_data)

    assert db_report.id == report_id
    assert db_report.user_id == user_id
    assert db_report.raw_text_input == "DB model text"
    assert db_report.ai_analysis.summary == "DB model AI summary"
    assert db_report.created_at == now
    assert db_report.updated_at == now
    assert db_report.linked_commit_ids == []


def test_daily_report_validation_error():
    # Test for DailyReportCreate (user_id is UUID, raw_text_input is str)
    with pytest.raises(ValidationError):
        DailyReportCreate(user_id="not-a-uuid", raw_text_input="test")

    with pytest.raises(ValidationError):
        DailyReportCreate(user_id=uuid4())  # Missing raw_text_input

    with pytest.raises(ValidationError):
        AiAnalysis(summary="test", estimated_hours="not-a-float")


def test_model_serialization_deserialization():
    cr = ClarificationRequest(question="Serialize me?", original_text="text to serialize")
    ai_analysis = AiAnalysis(summary="Test Serialize", clarification_requests=[cr])

    json_data = ai_analysis.model_dump_json()
    rehydrated_ai = AiAnalysis.model_validate_json(json_data)

    assert rehydrated_ai.summary == "Test Serialize"
    assert len(rehydrated_ai.clarification_requests) == 1
    assert rehydrated_ai.clarification_requests[0].question == "Serialize me?"

    user_id = uuid4()
    report = DailyReport(
        id=uuid4(),
        user_id=user_id,
        raw_text_input="Test report for serialization",
        ai_analysis=ai_analysis,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    json_report = report.model_dump_json()
    rehydrated_report = DailyReport.model_validate_json(json_report)

    assert rehydrated_report.user_id == user_id
    assert rehydrated_report.raw_text_input == "Test report for serialization"
    assert rehydrated_report.ai_analysis.summary == "Test Serialize"


# It's good practice to ensure __init__.py exists in test directories if using pytest discovery
# For example, backend/tests/__init__.py and backend/tests/models/__init__.py
# However, this tool creates the file directly so we don't need to manage __init__.py files here.
