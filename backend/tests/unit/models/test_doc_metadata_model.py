import pytest
from uuid import uuid4
from datetime import datetime
from pydantic import ValidationError

from app.models.doc_metadata import DocMetadata


def test_doc_metadata_valid():
    data = {
        "id": uuid4(),
        "doc_git_url": "http://example.com/repo/file.md",
        "doc_file_path": "docs/file.md",
        "title": "Readme",
        "created_at": datetime.utcnow(),
    }
    doc = DocMetadata(**data)
    assert doc.doc_git_url == data["doc_git_url"]
    assert doc.doc_file_path == "docs/file.md"


def test_doc_metadata_missing_required():
    with pytest.raises(ValidationError):
        DocMetadata(doc_git_url="http://example.com")
    with pytest.raises(ValidationError):
        DocMetadata(doc_file_path="path")
