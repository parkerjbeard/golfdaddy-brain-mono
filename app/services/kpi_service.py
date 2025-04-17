from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from uuid import UUID
import logging

from app.models.task import Task, TaskStatus
from app.models.user import User, UserRole
from app.models.commit import Commit
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.repositories.commit_repository import CommitRepository

logger = logging.getLogger(__name__)

class KpiService:
    """Service for calculating performance metrics."""
    
    def __init__(self):
        self.task_repo = TaskRepository()
        self.user_repo = UserRepository()
        self.commit_repo = CommitRepository()
    
    def calculate_commit_metrics_for_user(self, user_id: UUID, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Calculates commit-based KPIs for a specific user in a date range."""
        commits = self.commit_repo.get_commits_by_user_in_range(user_id, start_date, end_date)
        
        total_commits = len(commits)
        total_points = sum(c.ai_points or 0 for c in commits)
        total_hours = sum(float(c.ai_estimated_hours or 0) for c in commits)
        
        return {
            "user_id": user_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_commits": total_commits,
            "total_ai_points": total_points,
            "total_ai_estimated_hours": round(total_hours, 2),
            "avg_points_per_commit": round(total_points / total_commits, 2) if total_commits else 0,
        }
    
    def calculate_task_velocity(self, user_id: UUID, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Calculates task velocity (e.g., completed tasks) for a user. 
           Note: This is a simple example; velocity often uses story points.
        """
        # This requires tasks to have completion dates or updated_at to be reliable for date range filtering
        # Supabase filtering might need adjustment based on actual schema for completion date
        # Assuming filtering on updated_at for completed tasks for now
        tasks = self.task_repo.find_tasks_by_assignee(user_id)
        completed_tasks_in_range = [
            task for task in tasks 
            if task.status == TaskStatus.COMPLETED and 
               task.updated_at and 
               start_date <= task.updated_at.date() <= end_date
        ]
        
        # Alternative: If you have a dedicated `completed_at` field:
        # response = self.task_repo._client.table("tasks")\
        #              .select("*")\
        #              .eq("assignee_id", str(user_id))\
        #              .eq("status", TaskStatus.COMPLETED.value)\
        #              .gte("completed_at", start_date.isoformat())\
        #              .lte("completed_at", (end_date + timedelta(days=1)).isoformat())\
        #              .execute()
        # completed_tasks_in_range = [Task(**t) for t in response.data] if response.data else []

        return {
            "user_id": user_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "completed_tasks": len(completed_tasks_in_range),
            # Add point calculation if tasks have points
        }
    
    def generate_weekly_kpis_for_user(self, user_id: UUID) -> Dict[str, Any]:
        """Generates a consolidated weekly KPI report for a user."""
        today = datetime.today()
        start_of_week = today - timedelta(days=today.weekday()) # Monday
        end_of_week = start_of_week + timedelta(days=6) # Sunday
        
        commit_metrics = self.calculate_commit_metrics_for_user(user_id, start_of_week, end_of_week)
        task_velocity = self.calculate_task_velocity(user_id, start_of_week, end_of_week)
        
        # Combine metrics
        kpis = {
            "user_id": user_id,
            "week_start": start_of_week.isoformat(),
            "week_end": end_of_week.isoformat(),
            "commit_metrics": commit_metrics,
            "task_velocity": task_velocity,
            # Add burndown or other KPIs as needed
        }
        logger.info(f"Generated weekly KPIs for user {user_id}")
        return kpis
    
    # Add methods for team KPIs, burndown charts, etc.