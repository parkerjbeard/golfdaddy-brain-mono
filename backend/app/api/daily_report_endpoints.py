from fastapi import APIRouter, Depends, HTTPException, Body, status
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.models.daily_report import DailyReport, DailyReportCreate, DailyReportUpdate
from app.services.daily_report_service import DailyReportService
# from app.api.auth import get_current_active_user # Placeholder for your actual auth dependency
from app.models.user import User # Assuming you have a User model for current_user

# Placeholder for FastAPI's Depends for current user - replace with your actual dependency
async def get_current_active_user() -> User: 
    # This is a placeholder. Replace with your actual authentication logic.
    # Example: raise HTTPException(status_code=401, detail="Not authenticated") if no user.
    # Return a dummy user for now.
    return User(id=UUID("00000000-0000-0000-0000-000000000000"), email="test@example.com", name="Test User")

router = APIRouter(
    prefix="/reports/daily", 
    tags=["Daily Reports"],
    # dependencies=[Depends(get_current_active_user)] # Add auth dependency to all routes in this router
)

# Dependency for DailyReportService
# Using a function allows FastAPI to manage its lifecycle if needed, though for simple cases direct instantiation is fine.
def get_daily_report_service():
    return DailyReportService()

@router.post("/", response_model=DailyReport, status_code=status.HTTP_201_CREATED)
async def submit_eod_report(
    report_in: DailyReportCreate,
    current_user: User = Depends(get_current_active_user),
    report_service: DailyReportService = Depends(get_daily_report_service)
):
    """
    Submit an End-of-Day (EOD) report.
    The user ID from the token will be used.
    """
    # The service will handle using current_user.id instead of report_in.user_id if needed
    try:
        # Ensure the user_id in the payload matches the authenticated user, or is ignored by the service
        # Forcing current_user.id to be used by the service for security.
        # The service's submit_daily_report is designed to take current_user_id explicitly.
        created_report = await report_service.submit_daily_report(report_in, current_user_id=current_user.id)
        return created_report
    except Exception as e:
        # Log the exception e
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/me", response_model=List[DailyReport])
async def get_my_daily_reports(
    current_user: User = Depends(get_current_active_user),
    report_service: DailyReportService = Depends(get_daily_report_service)
):
    """Get all EOD reports for the currently authenticated user."""
    return await report_service.get_reports_for_user(current_user.id)

@router.get("/me/{report_date_str}", response_model=Optional[DailyReport])
async def get_my_daily_report_for_date(
    report_date_str: str, # Expecting YYYY-MM-DD
    current_user: User = Depends(get_current_active_user),
    report_service: DailyReportService = Depends(get_daily_report_service)
):
    """Get the authenticated user's EOD report for a specific date."""
    try:
        report_date = datetime.strptime(report_date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format. Use YYYY-MM-DD.")
    return await report_service.get_user_report_for_date(current_user.id, report_date)

@router.get("/{report_id}", response_model=DailyReport)
async def get_daily_report(
    report_id: UUID,
    # current_user: User = Depends(get_current_active_user), # Add if only specific users can access
    report_service: DailyReportService = Depends(get_daily_report_service)
):
    """Get a specific EOD report by its ID."""
    # TODO: Add authorization logic if needed (e.g., user can only access their own reports or if they are a manager)
    report = await report_service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report

# Add more endpoints as needed, e.g., for admins to view reports, or for users to update/delete. 