from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from typing import List, Optional, Dict, Any, Tuple
import uuid
from datetime import datetime, timedelta

from app.models.commit import Commit

class CommitRepository:
    """Repository for Commit model operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def save_commit(self, commit_hash: str, author_id: str, repository: str, 
                   branch: str, commit_message: str, commit_timestamp: datetime,
                   lines_added: Optional[int] = None,
                   lines_deleted: Optional[int] = None,
                   changed_files: Optional[List[str]] = None,
                   ai_points: Optional[int] = None, 
                   ai_estimated_hours: Optional[float] = None,
                   ai_analysis_notes: Optional[str] = None,
                   complexity_score: Optional[int] = None,
                   risk_level: Optional[str] = None,
                   risk_factor: Optional[float] = None,
                   point_calculation: Optional[Dict[str, Any]] = None) -> Commit:
        """Save a new commit record with AI analysis results."""
        # Check if commit already exists
        existing_commit = self.get_commit_by_hash(commit_hash)
        
        if existing_commit:
            # Update existing commit
            for key, value in {
                "lines_added": lines_added,
                "lines_deleted": lines_deleted,
                "changed_files": changed_files,
                "ai_points": ai_points,
                "ai_estimated_hours": ai_estimated_hours,
                "ai_analysis_notes": ai_analysis_notes,
                "complexity_score": complexity_score,
                "risk_level": risk_level,
                "risk_factor": risk_factor,
                "point_calculation": point_calculation
            }.items():
                if value is not None:
                    setattr(existing_commit, key, value)
            
            self.db.flush()
            return existing_commit
        
        # Create new commit
        commit = Commit(
            commit_hash=commit_hash,
            author_id=author_id,
            repository=repository,
            branch=branch,
            commit_message=commit_message,
            commit_timestamp=commit_timestamp,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
            changed_files=changed_files,
            ai_points=ai_points,
            ai_estimated_hours=ai_estimated_hours,
            ai_analysis_notes=ai_analysis_notes,
            complexity_score=complexity_score,
            risk_level=risk_level,
            risk_factor=risk_factor,
            point_calculation=point_calculation
        )
        
        self.db.add(commit)
        self.db.flush()
        return commit
    
    def get_commit_by_id(self, commit_id: str) -> Optional[Commit]:
        """Get a commit by ID."""
        return self.db.query(Commit).filter(Commit.id == commit_id).first()
    
    def get_commit_by_hash(self, commit_hash: str) -> Optional[Commit]:
        """Get a commit by hash."""
        return self.db.query(Commit).filter(Commit.commit_hash == commit_hash).first()
    
    def get_commits_by_user(self, author_id: str) -> List[Commit]:
        """Get all commits by a specific user."""
        return self.db.query(Commit).filter(Commit.author_id == author_id).all()
    
    def get_commits_by_user_in_range(self, author_id: str, 
                                     start_date: datetime, 
                                     end_date: datetime) -> List[Commit]:
        """Get commits by a user within a date range."""
        return self.db.query(Commit).filter(
            Commit.author_id == author_id,
            Commit.commit_timestamp >= start_date,
            Commit.commit_timestamp <= end_date
        ).order_by(Commit.commit_timestamp.desc()).all()
    
    def get_commits_by_repository(self, repository: str) -> List[Commit]:
        """Get all commits for a specific repository."""
        return self.db.query(Commit).filter(Commit.repository == repository).all()
    
    def bulk_insert_commits(self, commits_data: List[Dict[str, Any]]) -> List[Commit]:
        """Bulk insert multiple commits."""
        commits = []
        
        for data in commits_data:
            # Check if commit already exists
            existing_commit = self.get_commit_by_hash(data["commit_hash"])
            
            if existing_commit:
                # Update AI analysis if provided
                update_fields = [
                    "lines_added", "lines_deleted", "changed_files",
                    "ai_points", "ai_estimated_hours", "ai_analysis_notes",
                    "complexity_score", "risk_level", "risk_factor",
                    "point_calculation"
                ]
                
                for field in update_fields:
                    if field in data:
                        setattr(existing_commit, field, data[field])
                
                commits.append(existing_commit)
            else:
                # Create new commit
                commit = Commit(**data)
                self.db.add(commit)
                commits.append(commit)
        
        self.db.flush()
        return commits
    
    def get_total_points_in_range(self, author_id: str, 
                                 start_date: datetime,
                                 end_date: datetime) -> int:
        """Get total AI points for a user within a date range."""
        result = self.db.query(
            func.sum(Commit.ai_points)
        ).filter(
            Commit.author_id == author_id,
            Commit.commit_timestamp >= start_date,
            Commit.commit_timestamp <= end_date,
            Commit.ai_points != None
        ).scalar()
        
        return result or 0
    
    def get_total_estimated_hours_in_range(self, author_id: str,
                                          start_date: datetime,
                                          end_date: datetime) -> float:
        """Get total estimated hours for a user within a date range."""
        result = self.db.query(
            func.sum(Commit.ai_estimated_hours)
        ).filter(
            Commit.author_id == author_id,
            Commit.commit_timestamp >= start_date,
            Commit.commit_timestamp <= end_date,
            Commit.ai_estimated_hours != None
        ).scalar()
        
        return float(result or 0)
    
    def get_commit_stats_in_range(self, author_id: str,
                                start_date: datetime,
                                end_date: datetime) -> Dict[str, Any]:
        """Get detailed commit statistics for a user within a date range."""
        commits = self.get_commits_by_user_in_range(author_id, start_date, end_date)
        
        stats = {
            "total_commits": len(commits),
            "total_points": sum(c.ai_points or 0 for c in commits),
            "total_estimated_hours": sum(c.ai_estimated_hours or 0 for c in commits),
            "total_lines_added": sum(c.lines_added or 0 for c in commits),
            "total_lines_deleted": sum(c.lines_deleted or 0 for c in commits),
            "average_complexity": sum(c.complexity_score or 0 for c in commits) / len(commits) if commits else 0,
            "risk_level_distribution": {
                "low": len([c for c in commits if c.risk_level == "low"]),
                "medium": len([c for c in commits if c.risk_level == "medium"]),
                "high": len([c for c in commits if c.risk_level == "high"])
            }
        }
        
        return stats