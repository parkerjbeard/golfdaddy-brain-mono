import pytest
from datetime import datetime
from pydantic import ValidationError

from app.schemas.github_event import (
    CommitPayload,
    CommitFileData,
    CommitDetail,
    GitHubRepo,
    GitHubUser,
    Commit,
    PushEvent,
)


def test_commit_payload_valid():
    payload = CommitPayload(
        commit_hash="abc",
        commit_message="msg",
        commit_url="http://example.com/commit/abc",
        commit_timestamp=datetime.utcnow(),
        repository_name="repo",
        repository_url="http://example.com/repo",
        branch="main",
    )
    assert payload.commit_hash == "abc"


def test_commit_payload_invalid_url():
    with pytest.raises(ValidationError):
        CommitPayload(
            commit_hash="abc",
            commit_message="msg",
            commit_url="not-a-url",
            commit_timestamp=datetime.utcnow(),
            repository_name="repo",
            repository_url="http://example.com/repo",
            branch="main",
        )


def test_commit_file_data_required():
    file_data = CommitFileData(
        filename="file.py",
        status="modified",
        additions=1,
        deletions=0,
        changes=1,
    )
    assert file_data.filename == "file.py"

    with pytest.raises(ValidationError):
        CommitFileData(filename="file.py")


def test_commit_detail_missing_field():
    with pytest.raises(ValidationError):
        CommitDetail(
            repository="repo",
            files_changed=[],
            additions=0,
            deletions=0,
            retrieved_at="now",
            author={},
            committer={},
            message="m",
            url="u",
            verification={},
            files=[],
        )


def test_github_repo_valid():
    repo = GitHubRepo(id=1, name="repo", url="http://example.com")
    assert repo.id == 1


def test_github_repo_invalid_url():
    with pytest.raises(ValidationError):
        GitHubRepo(id=1, name="repo", url="not-url")


def test_github_user_email_validation():
    with pytest.raises(ValidationError):
        GitHubUser(login="user", email="not-email")
    user = GitHubUser(login="user", email=None)
    assert user.login == "user"


def test_commit_and_push_event():
    commit_obj = Commit(id="abc", distinct=True)
    push = PushEvent(commits=[commit_obj])
    assert push.commits[0].id == "abc"

    with pytest.raises(ValidationError):
        Commit(id="abc", distinct="yes")
