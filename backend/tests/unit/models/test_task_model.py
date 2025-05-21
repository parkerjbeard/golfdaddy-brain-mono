import pytest
from uuid import uuid4
from datetime import datetime
from pydantic import ValidationError

from app.models.task import Task, TaskStatus


def test_task_model_valid():
    task = Task(
        id=uuid4(),
        title="Test Task",
        description="A task for testing",
        status=TaskStatus.IN_PROGRESS,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    assert task.title == "Test Task"
    assert task.status == TaskStatus.IN_PROGRESS


def test_task_model_invalid_status():
    with pytest.raises(ValidationError):
        Task(title="x", description="y", status="not_valid")


def test_task_model_missing_title():
    with pytest.raises(ValidationError):
        Task(description="y")
