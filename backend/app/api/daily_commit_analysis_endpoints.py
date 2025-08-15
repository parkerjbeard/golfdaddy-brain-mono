from datetime import date, datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.auth.dependencies import get_current_user
from app.models.daily_commit_analysis import DailyCommitAnalysis
from app.models.user import User
from app.services.daily_commit_analysis_service import DailyCommitAnalysisService
from app.services.scheduled_tasks import scheduled_tasks

router = APIRouter(prefix="/api/daily-analysis", tags=["daily-analysis"])


@router.get("/user/{user_id}/history", response_model=List[DailyCommitAnalysis])
async def get_user_analysis_history(
    user_id: UUID,
    start_date: date = Query(..., description="Start date for analysis history"),
    end_date: date = Query(..., description="End date for analysis history"),
    current_user: User = Depends(get_current_user),
    service: DailyCommitAnalysisService = Depends(DailyCommitAnalysisService),
):
    """Get daily commit analysis history for a user within a date range"""

    # Users can only access their own data unless they're admin
    if current_user.id != user_id and current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Can only view your own analysis history"
        )

    try:
        analyses = await service.get_user_analysis_history(user_id, start_date, end_date)
        return analyses
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error retrieving analysis history: {str(e)}"
        )


@router.get("/user/{user_id}/date/{analysis_date}", response_model=Optional[DailyCommitAnalysis])
async def get_analysis_for_date(
    user_id: UUID,
    analysis_date: date,
    current_user: User = Depends(get_current_user),
    service: DailyCommitAnalysisService = Depends(DailyCommitAnalysisService),
):
    """Get daily commit analysis for a specific user and date"""

    # Users can only access their own data unless they're admin
    if current_user.id != user_id and current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Can only view your own analysis"
        )

    try:
        analysis = await service.repository.get_by_user_and_date(user_id, analysis_date)
        return analysis
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error retrieving analysis: {str(e)}"
        )


@router.get("/me/history", response_model=List[DailyCommitAnalysis])
async def get_my_analysis_history(
    start_date: date = Query(..., description="Start date for analysis history"),
    end_date: date = Query(..., description="End date for analysis history"),
    current_user: User = Depends(get_current_user),
    service: DailyCommitAnalysisService = Depends(DailyCommitAnalysisService),
):
    """Get daily commit analysis history for the current user"""
    try:
        analyses = await service.get_user_analysis_history(current_user.id, start_date, end_date)
        return analyses
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error retrieving analysis history: {str(e)}"
        )


@router.get("/me/current-week", response_model=List[DailyCommitAnalysis])
async def get_my_current_week_analysis(
    current_user: User = Depends(get_current_user),
    service: DailyCommitAnalysisService = Depends(DailyCommitAnalysisService),
):
    """Get daily commit analysis for the current user's current week"""
    try:
        # Calculate current week (Monday to Sunday)
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())  # Monday
        end_of_week = start_of_week + timedelta(days=6)  # Sunday

        analyses = await service.get_user_analysis_history(current_user.id, start_of_week, end_of_week)
        return analyses
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error retrieving weekly analysis: {str(e)}"
        )


@router.get("/me/today", response_model=Optional[DailyCommitAnalysis])
async def get_my_today_analysis(
    current_user: User = Depends(get_current_user),
    service: DailyCommitAnalysisService = Depends(DailyCommitAnalysisService),
):
    """Get daily commit analysis for the current user's today"""
    try:
        today = date.today()
        analysis = await service.repository.get_by_user_and_date(current_user.id, today)
        return analysis
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error retrieving today's analysis: {str(e)}"
        )


@router.post("/trigger-analysis/{user_id}")
async def trigger_manual_analysis(
    user_id: UUID,
    analysis_date: date = Query(..., description="Date to analyze"),
    current_user: User = Depends(get_current_user),
    service: DailyCommitAnalysisService = Depends(DailyCommitAnalysisService),
):
    """Manually trigger daily analysis for a specific user and date"""

    # Only admins or the user themselves can trigger analysis
    if current_user.id != user_id and current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Can only trigger analysis for yourself"
        )

    try:
        analysis = await service.analyze_for_date(user_id, analysis_date)
        if analysis:
            return {
                "message": "Analysis completed successfully",
                "analysis_id": analysis.id,
                "total_hours": analysis.total_estimated_hours,
            }
        else:
            return {"message": "No commits found for analysis on this date", "analysis_id": None, "total_hours": 0}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error triggering analysis: {str(e)}"
        )


@router.post("/admin/batch-analysis")
async def trigger_batch_analysis(
    analysis_date: date = Query(..., description="Date to analyze for all users"),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger batch analysis for all users on a specific date (admin only)"""

    if current_user.role != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Admin privileges required")

    try:
        results = await scheduled_tasks.run_analysis_for_date(datetime.combine(analysis_date, datetime.min.time()))
        return {"message": "Batch analysis completed", "results": results}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error running batch analysis: {str(e)}"
        )


@router.get("/admin/stats")
async def get_analysis_stats(
    start_date: date = Query(..., description="Start date for stats"),
    end_date: date = Query(..., description="End date for stats"),
    current_user: User = Depends(get_current_user),
    service: DailyCommitAnalysisService = Depends(DailyCommitAnalysisService),
):
    """Get analysis statistics for admin dashboard"""

    if current_user.role != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Admin privileges required")

    try:
        # This would need to be implemented in the service
        # For now, return a placeholder
        return {
            "total_analyses": 0,
            "total_hours_estimated": 0,
            "average_hours_per_day": 0,
            "users_analyzed": 0,
            "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error retrieving stats: {str(e)}"
        )
