import logging
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.auth.dependencies import get_current_user  # Import the standardized dependency
from app.core.exceptions import (  # New import
    BadRequestError,
    DatabaseError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from app.models.daily_report import DailyReport, DailyReportCreate, DailyReportUpdate
from app.models.user import User, UserRole  # Assuming you have a User model for current_user
from app.services.daily_report_service import DailyReportService


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
    current_user: User = Depends(get_current_user),  # Updated dependency
    report_service: DailyReportService = Depends(get_daily_report_service),
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
    except ValueError as ve:  # Example: If report_in has bad data not caught by Pydantic but by service logic
        logger.error(f"Validation error submitting EOD report: {ve}", exc_info=True)
        raise BadRequestError(message=str(ve))
    except Exception as e:  # General catch for other unexpected service errors
        logger.error(f"Error submitting EOD report: {e}", exc_info=True)
        raise DatabaseError(message=f"An unexpected error occurred while submitting the report: {str(e)}")


@router.get("/me", response_model=Dict[str, Any])
async def get_my_daily_reports(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    current_user: User = Depends(get_current_user),  # Updated dependency
    report_service: DailyReportService = Depends(get_daily_report_service),
):
    """Get EOD reports for the currently authenticated user with pagination."""
    reports = await report_service.get_reports_for_user_paginated(
        user_id=current_user.id, page=page, page_size=page_size
    )
    return reports


@router.get("/me/{report_date_str}", response_model=Optional[DailyReport])
async def get_my_daily_report_for_date(
    report_date_str: str,  # Expecting YYYY-MM-DD
    current_user: User = Depends(get_current_user),  # Updated dependency
    report_service: DailyReportService = Depends(get_daily_report_service),
):
    """Get the authenticated user's EOD report for a specific date."""
    try:
        report_date = datetime.strptime(report_date_str, "%Y-%m-%d")
    except ValueError:
        raise BadRequestError(message="Invalid date format. Use YYYY-MM-DD.")

    report = await report_service.get_user_report_for_date(current_user.id, report_date)
    if report is None:  # Explicitly check if service returns None for not found
        # Service could also raise ResourceNotFoundError directly
        raise ResourceNotFoundError(
            resource_name=f"Daily report for user {current_user.id}", resource_id=report_date_str
        )
    return report


@router.get("/{report_id}", response_model=DailyReport)
async def get_daily_report(
    report_id: UUID,
    current_user: User = Depends(get_current_user),  # Uncommented and activated dependency
    report_service: DailyReportService = Depends(get_daily_report_service),
):
    """Get a specific EOD report by its ID."""
    report = await report_service.get_report_by_id(report_id)
    if not report:
        raise ResourceNotFoundError(resource_name="Daily Report", resource_id=str(report_id))

    # Authorization logic
    # Replace with actual role-based access control if applicable
    is_owner = report.user_id == current_user.id
    # is_manager = # Placeholder: Implement logic to check if current_user is a manager
    # For now, only owners can access. Add manager logic when roles are defined.
    if not is_owner:  # and not is_manager: # Add is_manager check when implemented
        raise PermissionDeniedError(message="Not authorized to access this report")

    return report


# Admin endpoint to view all reports
@router.get("/admin/all", response_model=Dict[str, Any])
async def get_all_daily_reports_admin(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    current_user: User = Depends(get_current_user),
    report_service: DailyReportService = Depends(get_daily_report_service),
):
    """(Admin) Get all EOD reports with pagination."""
    # Placeholder for admin check
    # Replace with actual admin role check
    if current_user.role != UserRole.ADMIN:  # Assumes an is_admin attribute on User model
        raise PermissionDeniedError(message="User does not have admin privileges")
    return await report_service.get_all_reports_paginated(page=page, page_size=page_size)


@router.put("/{report_id}", response_model=DailyReport)
async def update_my_daily_report(
    report_id: UUID,
    report_update: DailyReportUpdate,
    current_user: User = Depends(get_current_user),
    report_service: DailyReportService = Depends(get_daily_report_service),
):
    """Update an EOD report owned by the current user."""
    report = await report_service.get_report_by_id(report_id)
    if not report:
        raise ResourceNotFoundError(resource_name="Daily Report", resource_id=str(report_id))

    if report.user_id != current_user.id:
        raise PermissionDeniedError(message="Not authorized to update this report")

    try:
        updated_report = await report_service.update_daily_report(report_id, report_update, current_user.id)
        if not updated_report:
            # This case might occur if the update fails for some reason after initial checks
            logger.error(
                f"Update for report {report_id} by user {current_user.id} returned no object despite passing checks."
            )
            raise DatabaseError(message="Report update failed or report became unavailable after authorization.")
        return updated_report
    except ValueError as ve:  # E.g. if report_update contains invalid data for the service
        logger.error(f"Validation error updating report {report_id}: {ve}", exc_info=True)
        raise BadRequestError(message=str(ve))
    except Exception as e:  # Catch-all for other service layer issues
        logger.error(f"Unexpected error updating report {report_id}: {e}", exc_info=True)
        raise DatabaseError(message=f"An unexpected error occurred while updating the report: {str(e)}")


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_daily_report(
    report_id: UUID,
    current_user: User = Depends(get_current_user),
    report_service: DailyReportService = Depends(get_daily_report_service),
):
    """Delete an EOD report owned by the current user."""
    report = await report_service.get_report_by_id(report_id)
    if not report:
        # Allowing idempotent deletes, so not finding it could be considered success by some.
        # However, for clarity and to prevent accidental calls to non-existent IDs, we'll raise 404.
        raise ResourceNotFoundError(resource_name="Daily Report", resource_id=str(report_id))

    if report.user_id != current_user.id:
        raise PermissionDeniedError(message="Not authorized to delete this report")

    try:
        success = await report_service.delete_daily_report(report_id, current_user.id)
        if not success:
            # This could mean the report was not found (race condition) or delete failed for other reasons
            # despite passing earlier checks.
            logger.error(f"Deletion of report {report_id} by user {current_user.id} failed after passing checks.")
            raise DatabaseError(message="Report deletion failed or report became unavailable after authorization.")
    except Exception as e:
        logger.error(f"Unexpected error deleting report {report_id}: {e}", exc_info=True)
        raise DatabaseError(message=f"An unexpected error occurred while deleting the report: {str(e)}")
    # No content to return on successful delete, per HTTP 204
    return


@router.get("/user/{user_id}", response_model=Dict[str, Any])
async def get_user_daily_reports(
    user_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    current_user: User = Depends(get_current_user),
    report_service: DailyReportService = Depends(get_daily_report_service),
):
    """Get daily reports for a specific user with pagination. For managers to view their team's reports."""
    # Check if current user is a manager or admin
    # For now, we'll assume managers have a specific role
    if current_user.role not in [UserRole.MANAGER, UserRole.ADMIN]:
        raise PermissionDeniedError(message="Only managers and admins can view other users' reports")

    # TODO: Add check that the requested user is actually in the manager's team

    reports = await report_service.get_reports_for_user_paginated(user_id=user_id, page=page, page_size=page_size)
    return reports


# Add more endpoints as needed, e.g., for admins to view reports, or for users to update/delete.
