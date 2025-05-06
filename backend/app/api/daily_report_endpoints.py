from fastapi import APIRouter, Depends, HTTPException, Body, status
from typing import List, Optional
from uuid import UUID
from datetime import datetime
import logging

from app.models.daily_report import DailyReport, DailyReportCreate, DailyReportUpdate
from app.services.daily_report_service import DailyReportService
from app.models.user import User, UserRole # Assuming you have a User model for current_user
from app.auth.dependencies import get_current_user # Import the standardized dependency

# Placeholder for FastAPI's Depends for current user - replace with your actual dependency
async def get_current_active_user() -> User: 
    # This is a placeholder. Replace with your actual authentication logic.
    # Example: raise HTTPException(status_code=401, detail="Not authenticated") if no user.
    # Return a dummy user for now.
    return User(id=UUID("00000000-0000-0000-0000-000000000000"), email="test@example.com", name="Test User")

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/reports/daily", 
    tags=["Daily Reports"],
    # dependencies=[Depends(get_current_user)] # Updated dependency
)

# Dependency for DailyReportService
# Using a function allows FastAPI to manage its lifecycle if needed, though for simple cases direct instantiation is fine.
def get_daily_report_service():
    return DailyReportService()

@router.post("/", response_model=DailyReport, status_code=status.HTTP_201_CREATED)
async def submit_eod_report(
    report_in: DailyReportCreate,
    current_user: User = Depends(get_current_user), # Updated dependency
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
        logger.error(f"Error submitting EOD report: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/me", response_model=List[DailyReport])
async def get_my_daily_reports(
    current_user: User = Depends(get_current_user), # Updated dependency
    report_service: DailyReportService = Depends(get_daily_report_service)
):
    """Get all EOD reports for the currently authenticated user."""
    return await report_service.get_reports_for_user(current_user.id)

@router.get("/me/{report_date_str}", response_model=Optional[DailyReport])
async def get_my_daily_report_for_date(
    report_date_str: str, # Expecting YYYY-MM-DD
    current_user: User = Depends(get_current_user), # Updated dependency
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
    current_user: User = Depends(get_current_user), # Uncommented and activated dependency
    report_service: DailyReportService = Depends(get_daily_report_service)
):
    """Get a specific EOD report by its ID."""
    report = await report_service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    # Authorization logic
    # Replace with actual role-based access control if applicable
    is_owner = report.user_id == current_user.id 
    # is_manager = # Placeholder: Implement logic to check if current_user is a manager
    # For now, only owners can access. Add manager logic when roles are defined.
    if not is_owner: # and not is_manager: # Add is_manager check when implemented
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this report")

    return report

# Admin endpoint to view all reports
@router.get("/admin/all", response_model=List[DailyReport])
async def get_all_daily_reports_admin(
    current_user: User = Depends(get_current_user),
    report_service: DailyReportService = Depends(get_daily_report_service)
):
    """(Admin) Get all EOD reports."""
    # Placeholder for admin check
    # Replace with actual admin role check
    if current_user.role != UserRole.ADMIN: # Assumes an is_admin attribute on User model
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User does not have admin privileges")
    return await report_service.get_all_reports()

@router.put("/{report_id}", response_model=DailyReport)
async def update_my_daily_report(
    report_id: UUID,
    report_update: DailyReportUpdate,
    current_user: User = Depends(get_current_user),
    report_service: DailyReportService = Depends(get_daily_report_service)
):
    """Update an EOD report owned by the current user."""
    report = await report_service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    if report.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this report")

    updated_report = await report_service.update_daily_report(report_id, report_update, current_user.id)
    if not updated_report:
        # This case might occur if the update fails for some reason, or if the report_id was valid but no longer exists
        # Or if the service layer itself handles the user_id check and returns None if not authorized.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found or update failed")
    return updated_report

@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_daily_report(
    report_id: UUID,
    current_user: User = Depends(get_current_user),
    report_service: DailyReportService = Depends(get_daily_report_service)
):
    """Delete an EOD report owned by the current user."""
    report = await report_service.get_report_by_id(report_id)
    if not report:
        # Allowing idempotent deletes, so not finding it could be considered success by some.
        # However, for clarity and to prevent accidental calls to non-existent IDs, we'll raise 404.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    if report.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this report")

    success = await report_service.delete_daily_report(report_id, current_user.id)
    if not success:
        # This could mean the report was not found (race condition) or delete failed for other reasons
        # despite passing earlier checks.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found or delete failed")
    # No content to return on successful delete, per HTTP 204
    return

# Add more endpoints as needed, e.g., for admins to view reports, or for users to update/delete. 