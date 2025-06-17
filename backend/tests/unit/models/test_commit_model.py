import pytest
from uuid import uuid4
from datetime import datetime
from pydantic import ValidationError

from app.models.commit import Commit


def test_commit_model_valid():
    data = {
        "id": uuid4(),
        "commit_hash": "abc123",
        "commit_timestamp": datetime.utcnow(),
    }
    commit = Commit(**data)
    assert commit.commit_hash == "abc123"
    assert commit.commit_timestamp == data["commit_timestamp"]


def test_commit_model_missing_required():
    with pytest.raises(ValidationError):
        Commit(commit_timestamp=datetime.utcnow())
    with pytest.raises(ValidationError):
        Commit(commit_hash="abc123")
