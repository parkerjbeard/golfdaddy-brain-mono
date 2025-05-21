import pytest
from uuid import uuid4
from pydantic import ValidationError

from app.services.kpi_service import UserWidgetSummary


def test_user_widget_summary_valid():
    summary = UserWidgetSummary(
        user_id=uuid4(),
        name="John",
        avatar_url="http://example.com/a.png",
        total_ai_estimated_commit_hours=2.5,
    )
    assert summary.total_ai_estimated_commit_hours == 2.5


def test_user_widget_summary_invalid_hours():
    with pytest.raises(ValidationError):
        UserWidgetSummary(
            user_id=uuid4(),
            total_ai_estimated_commit_hours="a",
        )
