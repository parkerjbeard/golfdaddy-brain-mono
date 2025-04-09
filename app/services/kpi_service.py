from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.models.task import Task, TaskStatus
from app.models.user import User, UserRole
from app.models.commit import Commit
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.repositories.commit_repository import CommitRepository

class KpiService:
    """Service for calculating performance metrics."""
    
    def __init__(self, db: Session):
        self.db = db
        self.task_repository = TaskRepository(db)
        self.user_repository = UserRepository(db)
        self.commit_repository = CommitRepository(db)
    
    def calculate_velocity(self, user_id: str, start_date: datetime, 
                          end_date: datetime) -> Dict[str, Any]:
        """
        Calculate velocity metrics for a user over a time period.
        
        Returns:
            Dict with velocity metrics
        """
        # Get all completed tasks in the date range
        completed_tasks = self.db.query(Task).filter(
            Task.assignee_id == user_id,
            Task.status == TaskStatus.COMPLETED,
            Task.updated_at >= start_date,
            Task.updated_at <= end_date
        ).all()
        
        # Get all commits in the date range
        commits = self.commit_repository.get_commits_by_user_in_range(
            user_id, start_date, end_date
        )
        
        # Calculate total points from commits
        total_points = sum(c.ai_points or 0 for c in commits)
        
        # Calculate total estimated hours
        total_estimated_hours = sum(c.ai_estimated_hours or 0 for c in commits)
        
        # Days in period
        days_in_period = (end_date - start_date).days + 1
        
        # Calculate metrics
        return {
            "user_id": user_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "completed_tasks_count": len(completed_tasks),
            "total_commit_points": total_points,
            "total_estimated_hours": total_estimated_hours,
            "points_per_day": total_points / days_in_period if days_in_period > 0 else 0,
            "estimated_hours_per_day": total_estimated_hours / days_in_period if days_in_period > 0 else 0,
            "points_per_hour": total_points / total_estimated_hours if total_estimated_hours > 0 else 0
        }
    
    def calculate_burndown(self, user_id: Optional[str] = None, 
                          team: Optional[str] = None,
                          start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Calculate task burndown metrics.
        
        Args:
            user_id: Optional user to filter by
            team: Optional team to filter by
            start_date, end_date: Optional date range
            
        Returns:
            Dict with burndown metrics
        """
        # Build query for tasks
        query = self.db.query(Task)
        
        # Apply filters
        if user_id:
            query = query.filter(Task.assignee_id == user_id)
        
        if team:
            # Join with User to filter by team
            query = query.join(User, Task.assignee_id == User.id).filter(User.team == team)
        
        if start_date:
            query = query.filter(Task.created_at >= start_date)
        
        if end_date:
            query = query.filter(Task.created_at <= end_date)
        
        # Execute query
        tasks = query.all()
        
        # Count tasks by status
        status_counts = {status.value: 0 for status in TaskStatus}
        for task in tasks:
            status_counts[task.status.value] += 1
        
        # Calculate totals
        total_tasks = len(tasks)
        completed_tasks = status_counts[TaskStatus.COMPLETED.value]
        pending_tasks = total_tasks - completed_tasks
        
        # Calculate completion percentage
        completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "pending_tasks": pending_tasks,
            "completion_percentage": completion_percentage,
            "status_breakdown": status_counts,
            "filters": {
                "user_id": user_id,
                "team": team,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None
            }
        }
    
    def commit_efficiency(self, user_id: str, start_date: datetime, 
                         end_date: datetime) -> Dict[str, Any]:
        """
        Calculate efficiency metrics from commit data.
        
        Returns:
            Dict with efficiency metrics
        """
        # Get all commits in the date range
        commits = self.commit_repository.get_commits_by_user_in_range(
            user_id, start_date, end_date
        )
        
        # Calculate metrics
        total_points = sum(c.ai_points or 0 for c in commits)
        total_estimated_hours = sum(c.ai_estimated_hours or 0 for c in commits)
        commit_count = len(commits)
        
        # Points per commit
        points_per_commit = total_points / commit_count if commit_count > 0 else 0
        
        # Hours per commit
        hours_per_commit = total_estimated_hours / commit_count if commit_count > 0 else 0
        
        # Points per hour
        points_per_hour = total_points / total_estimated_hours if total_estimated_hours > 0 else 0
        
        return {
            "user_id": user_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "commit_count": commit_count,
            "total_points": total_points,
            "total_estimated_hours": total_estimated_hours,
            "points_per_commit": points_per_commit,
            "hours_per_commit": hours_per_commit,
            "points_per_hour": points_per_hour
        }
    
    def weekly_kpis(self, user_id: Optional[str] = None, 
                   team: Optional[str] = None,
                   week_start: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Generate weekly KPI report for managers.
        
        Args:
            user_id: Optional user to filter by
            team: Optional team to filter by
            week_start: Start date of the week (defaults to last Monday)
            
        Returns:
            Dict with consolidated weekly KPIs
        """
        # Determine date range for the week
        if not week_start:
            # Default to last Monday
            today = datetime.now()
            week_start = today - timedelta(days=today.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        # Users to analyze
        users = []
        if user_id:
            user = self.user_repository.get_user_by_id(user_id)
            if user:
                users = [user]
        elif team:
            users = self.user_repository.list_users_by_team(team)
        else:
            # Default to all users
            users = self.user_repository.list_users()
        
        # Collect KPIs for each user
        user_kpis = []
        for user in users:
            velocity = self.calculate_velocity(user.id, week_start, week_end)
            efficiency = self.commit_efficiency(user.id, week_start, week_end)
            
            user_kpis.append({
                "user": user.to_dict(),
                "velocity": velocity,
                "efficiency": efficiency
            })
        
        # Calculate team totals
        team_burndown = self.calculate_burndown(
            team=team,
            start_date=week_start,
            end_date=week_end
        )
        
        return {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "team": team,
            "user_kpis": user_kpis,
            "team_burndown": team_burndown
        }