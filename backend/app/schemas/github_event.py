from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class CommitPayload(BaseModel):
    commit_hash: str = Field(..., description="Unique commit SHA")
    commit_message: str = Field(..., description="The commit message")
    commit_url: HttpUrl = Field(..., description="URL to the commit details on GitHub")
    commit_timestamp: datetime = Field(..., description="Timestamp when the commit was authored")
    author_github_username: Optional[str] = Field(None, description="GitHub username of the author")
    author_email: Optional[str] = Field(None, description="Email address associated with the commit author")
    repository_name: str = Field(..., description="Name of the repository")
    repository_url: HttpUrl = Field(..., description="URL of the repository")
    branch: str = Field(..., description="Branch the commit was pushed to")
    diff_url: Optional[HttpUrl] = Field(None, description="URL to the .diff or .patch file for the commit")
    commit_diff: Optional[str] = Field(None, description="Optional: The actual diff content if fetched by Make.com")
    files_changed: Optional[List[str]] = Field(None, description="List of files changed in the commit")
    additions: Optional[int] = Field(None, description="Number of additions in the commit")
    deletions: Optional[int] = Field(None, description="Number of deletions in the commit")
    parent_commit: Optional[str] = Field(None, description="SHA of the parent commit")

    # Additional fields for compatibility
    repository: Optional[str] = Field(None, description="Full repository name in owner/repo format")
    diff_data: Optional[str] = Field(None, description="Alias for commit_diff")

    class Config:
        from_attributes = True  # Replaced orm_mode
        str_strip_whitespace = True


class CommitFileData(BaseModel):
    filename: str
    status: str  # 'added', 'modified', 'removed', etc.
    additions: int
    deletions: int
    changes: int
    patch: Optional[str] = None

    class Config:
        from_attributes = True  # Replaced orm_mode


class CommitDetail(BaseModel):
    commit_hash: str
    repository: str
    files_changed: List[str]
    additions: int
    deletions: int
    retrieved_at: str  # Consider changing to datetime if appropriate
    author: Dict[str, Any]
    committer: Dict[str, Any]
    message: str
    url: str  # Consider HttpUrl
    verification: Dict[str, Any]
    files: List[CommitFileData]

    class Config:
        from_attributes = True  # Replaced orm_mode


class GitHubRepo(BaseModel):
    id: int
    name: str  # e.g., "octocat/Hello-World"
    url: HttpUrl

    class Config:
        from_attributes = True  # Allows compatibility if needed later, good practice


class GitHubUser(BaseModel):
    login: str  # Username
    name: Optional[str] = None
    email: Optional[EmailStr] = None

    class Config:
        from_attributes = True


class Commit(BaseModel):
    id: str  # SHA
    distinct: bool

    class Config:
        from_attributes = True


class PushEvent(BaseModel):
    ref: Optional[str] = None
    before: Optional[str] = None
    after: Optional[str] = None
    repository: Optional[GitHubRepo] = None
    pusher: Optional[GitHubUser] = None
    commits: List[Commit] = []
    head_commit: Optional[Commit] = None
    pass
