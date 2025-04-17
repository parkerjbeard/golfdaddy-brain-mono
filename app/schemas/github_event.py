from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Dict, Any, List
from datetime import datetime

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
    
    class Config:
        orm_mode = True # Allows compatibility if needed later, good practice
        anystr_strip_whitespace = True


class CommitFileData(BaseModel):
    filename: str
    status: str  # 'added', 'modified', 'removed', etc.
    additions: int
    deletions: int
    changes: int
    patch: Optional[str] = None

    class Config:
        orm_mode = True

        
class CommitDetail(BaseModel):
    commit_hash: str
    repository: str
    files_changed: List[str]
    additions: int
    deletions: int
    retrieved_at: str
    author: Dict[str, Any]
    committer: Dict[str, Any]
    message: str
    url: str
    verification: Dict[str, Any]
    files: List[CommitFileData]

    class Config:
        orm_mode = True 