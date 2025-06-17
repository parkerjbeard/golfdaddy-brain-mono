"""
API endpoints for weekly hours summary and reporting.
Combines data from commits and daily reports with deduplication.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, date, timedelta
import logging

from app.auth.dependencies import get_current_user
from app.models.user import User
from app.services.daily_report_service import DailyReportService
from app.core.exceptions import ResourceNotFoundError, PermissionDeniedError

router = APIRouter(prefix="/api/v1/weekly-hours", tags=["weekly-hours"])
logger = logging.getLogger(__name__)


@router.get("/summary/{user_id}")
async def get_weekly_hours_summary(
    user_id: UUID,
    week_start: Optional[date] = Query(
        None, 
        description="Start date of the week (Monday). If not provided, uses current week."
    ),
    current_user: User = Depends(get_current_user),
    report_service: DailyReportService = Depends(lambda: DailyReportService())
) -> Dict[str, Any]:
    """
    Get weekly hours summary for a user, combining commits and daily reports.
    
    Permissions:
    - Users can view their own data
    - Managers can view their direct reports' data
    - Admins can view anyone's data
    """
    try:
        # Check permissions
        if (
            current_user.id != user_id 
            and current_user.role != "admin"
            and not (current_user.role == "manager" and await _is_direct_report(user_id, current_user.id))
        ):
            raise PermissionDeniedError("You don't have permission to view this user's hours")
        
        # Calculate week start if not provided
        if not week_start:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())  # Monday of current week
        
        # Convert to datetime for service
        week_start_dt = datetime.combine(week_start, datetime.min.time())
        
        # Get weekly summary
        summary = await report_service.get_weekly_hours_summary(user_id, week_start_dt)
        
        return {
            "user_id": str(user_id),
            "week_start": week_start.isoformat(),
            "week_end": (week_start + timedelta(days=6)).isoformat(),
            **summary
        }
        
    except PermissionDeniedError:
        raise
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting weekly hours summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get weekly hours summary")


@router.get("/team-summary")
async def get_team_weekly_hours(
    week_start: Optional[date] = Query(
        None, 
        description="Start date of the week (Monday). If not provided, uses current week."
    ),
    current_user: User = Depends(get_current_user),
    report_service: DailyReportService = Depends(lambda: DailyReportService())
) -> Dict[str, Any]:
    """
    Get weekly hours summary for a manager's entire team.
    
    Permissions:
    - Managers can view their team's data
    - Admins can view all data
    """
    try:
        if current_user.role not in ["manager", "admin"]:
            raise PermissionDeniedError("Only managers and admins can view team summaries")
        
        # Calculate week start if not provided
        if not week_start:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
        
        week_start_dt = datetime.combine(week_start, datetime.min.time())
        
        # Get direct reports for the manager
        from app.repositories.user_repository import UserRepository
        user_repo = UserRepository()
        
        if current_user.role == "manager":
            team_members = await user_repo.get_direct_reports(current_user.id)
        else:  # admin
            # For admin, get all users
            team_members, _ = await user_repo.list_all_users(limit=1000)
        
        # Get summary for each team member
        team_summaries = []
        total_commit_hours = 0.0
        total_report_hours = 0.0
        total_combined_hours = 0.0
        
        for member in team_members:
            try:
                summary = await report_service.get_weekly_hours_summary(member.id, week_start_dt)
                member_summary = {
                    "user_id": str(member.id),
                    "user_name": member.name,
                    "user_email": member.email,
                    **summary
                }
                team_summaries.append(member_summary)
                
                # Accumulate totals
                total_commit_hours += summary.get("total_commit_hours", 0.0)
                total_report_hours += summary.get("total_report_hours", 0.0)
                total_combined_hours += summary.get("total_combined_hours", 0.0)
                
            except Exception as e:
                logger.warning(f"Failed to get summary for user {member.id}: {e}")
                # Continue with other team members
        
        return {
            "week_start": week_start.isoformat(),
            "week_end": (week_start + timedelta(days=6)).isoformat(),
            "team_count": len(team_summaries),
            "team_summaries": team_summaries,
            "team_totals": {
                "total_commit_hours": total_commit_hours,
                "total_report_hours": total_report_hours,
                "total_combined_hours": total_combined_hours,
                "average_hours_per_person": total_combined_hours / len(team_summaries) if team_summaries else 0
            }
        }
        
    except PermissionDeniedError:
        raise
    except Exception as e:
        logger.error(f"Error getting team weekly hours: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get team weekly hours")


@router.get("/trends/{user_id}")
async def get_hours_trends(
    user_id: UUID,
    weeks: int = Query(4, ge=1, le=12, description="Number of weeks to include"),
    current_user: User = Depends(get_current_user),
    report_service: DailyReportService = Depends(lambda: DailyReportService())
) -> Dict[str, Any]:
    """
    Get hours trends over multiple weeks for a user.
    
    Permissions: Same as get_weekly_hours_summary
    """
    try:
        # Check permissions (same as weekly summary)
        if (
            current_user.id != user_id 
            and current_user.role != "admin"
            and not (current_user.role == "manager" and await _is_direct_report(user_id, current_user.id))
        ):
            raise PermissionDeniedError("You don't have permission to view this user's hours")
        
        # Calculate week starts
        today = date.today()
        current_week_start = today - timedelta(days=today.weekday())
        
        weekly_data = []
        for i in range(weeks):
            week_start = current_week_start - timedelta(days=7 * i)
            week_start_dt = datetime.combine(week_start, datetime.min.time())
            
            try:
                summary = await report_service.get_weekly_hours_summary(user_id, week_start_dt)
                weekly_data.append({
                    "week_start": week_start.isoformat(),
                    "week_end": (week_start + timedelta(days=6)).isoformat(),
                    **summary
                })
            except Exception as e:
                logger.warning(f"Failed to get summary for week {week_start}: {e}")
                # Continue with other weeks
        
        # Calculate trends
        if weekly_data:
            avg_commit_hours = sum(w.get("total_commit_hours", 0) for w in weekly_data) / len(weekly_data)
            avg_report_hours = sum(w.get("total_report_hours", 0) for w in weekly_data) / len(weekly_data)
            avg_combined_hours = sum(w.get("total_combined_hours", 0) for w in weekly_data) / len(weekly_data)
        else:
            avg_commit_hours = avg_report_hours = avg_combined_hours = 0
        
        return {
            "user_id": str(user_id),
            "weeks_analyzed": len(weekly_data),
            "weekly_data": sorted(weekly_data, key=lambda x: x["week_start"]),
            "averages": {
                "avg_commit_hours_per_week": avg_commit_hours,
                "avg_report_hours_per_week": avg_report_hours,
                "avg_combined_hours_per_week": avg_combined_hours
            }
        }
        
    except PermissionDeniedError:
        raise
    except Exception as e:
        logger.error(f"Error getting hours trends: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get hours trends")


async def _is_direct_report(user_id: UUID, manager_id: UUID) -> bool:
    """Check if a user is a direct report of a manager."""
    from app.repositories.user_repository import UserRepository
    user_repo = UserRepository()
    
    user = await user_repo.get_user_by_id(user_id)
    return user and user.reports_to_id == manager_id