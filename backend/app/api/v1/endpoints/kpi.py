import logging  # For logging
import os
from datetime import date, datetime, timedelta, timezone  # Ensure timezone is imported for utcnow()
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

# from app.services.auth_service import get_current_active_user # Placeholder for auth
from app.core.exceptions import (  # New import
    BadRequestError,
    DatabaseError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from app.models.user import User, UserRole  # For dependency injection and auth roles
from app.services.kpi_service import KpiService, UserWidgetSummary  # Added UserWidgetSummary

logger = logging.getLogger(__name__)  # For logging
router = APIRouter()


# Create a function to get KpiService instance
def get_kpi_service():
    return KpiService()


@router.get("/test-kpi")  # New test endpoint
async def test_kpi_endpoint():
    return {"message": "KPI router is working!"}


@router.get("/performance/widget-summaries", response_model=List[UserWidgetSummary])
async def get_all_user_widget_summaries(
    startDate: date = Query(..., description="Start date for the summary period (YYYY-MM-DD)."),
    endDate: date = Query(..., description="End date for the summary period (YYYY-MM-DD)."),
    kpi_service: KpiService = Depends(get_kpi_service),
    # current_user: User = Depends(get_current_active_user) # TODO: Add auth, ensure manager can view
):
    """
    Retrieve widget summaries (pull-request based activity metrics) for all relevant users
    within a specified date range.
    """
    if startDate > endDate:
        raise HTTPException(status_code=400, detail="Start date cannot be after end date.")

    # KpiService expects datetime objects for its internal logic.
    start_datetime = datetime.combine(startDate, datetime.min.time(), tzinfo=timezone.utc)
    end_datetime = datetime.combine(endDate, datetime.max.time(), tzinfo=timezone.utc)  # Use max time for inclusivity

    try:
        summaries = await kpi_service.get_bulk_widget_summaries(start_datetime, end_datetime)
        return summaries
    except Exception as e:
        logger.error(f"Error fetching bulk widget summaries: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred while fetching widget summaries.")


@router.get("/user-summary/{user_id}", response_model=Dict[str, Any])  # Path updated for clarity
async def get_user_kpi_summary(
    user_id: UUID,
    periodDays: Optional[int] = Query(
        7, ge=1, le=90, description="Number of days for the summary period, ending today."
    ),
    startDate: Optional[date] = Query(
        None, description="Start date for the summary period (YYYY-MM-DD). Overrides periodDays if provided."
    ),
    endDate: Optional[date] = Query(
        None,
        description="End date for the summary period (YYYY-MM-DD). Defaults to today if startDate is provided without endDate.",
    ),
    kpi_service: KpiService = Depends(get_kpi_service),
    # current_user: User = Depends(get_current_active_user) # TODO: Add auth, ensure manager can view this data
):
    """
    Retrieve a pull-request centric Key Performance Indicator (KPI) summary for a specific user.
    Allows specifying a period in days (e.g., last 7 days) or a specific date range.
    """
    # Authorization check placeholder:
    # Example: Assuming current_user has roles and a way to check team membership
    # if not current_user or (current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]):
    #     raise PermissionDeniedError(message="Not authorized to view this KPI summary")
    # if current_user.role == UserRole.MANAGER and not kpi_service.is_user_in_manager_team(current_user.id, user_id):
    #     # (Requires KpiService or another service to have such a method)
    #     raise PermissionDeniedError(message="Not authorized: user is not in your team")

    try:
        # The KpiService.get_user_performance_summary expects period_days.
        # If startDate and endDate are provided, we need to calculate period_days.
        # Or, refactor KpiService to directly accept startDate and endDate.

        actual_period_days: int

        if startDate:
            summary_end_date_naive = endDate if endDate else datetime.now(timezone.utc).date()
            if startDate > summary_end_date_naive:
                raise BadRequestError(message="Start date cannot be after end date.")

            actual_period_days = (summary_end_date_naive - startDate).days + 1
            if actual_period_days <= 0:
                raise BadRequestError(message="Invalid date range resulting in non-positive period days.")
        elif periodDays:
            actual_period_days = periodDays
        else:
            # This case should be prevented by FastAPI/Pydantic if periodDays has a default and is required.
            # However, if periodDays was Optional without a default, this would be necessary.
            logger.error("KPI user-summary endpoint called without periodDays or startDate.")
            raise BadRequestError(message="You must provide either periodDays or startDate.")

        logger.info(f"Fetching KPI summary for user {user_id} for {actual_period_days} days.")
        summary_data = await kpi_service.get_user_performance_summary(user_id, period_days=actual_period_days)

        if summary_data is None:  # Assuming service returns None if user_id not found or no data
            logger.warning(
                f"No KPI summary data found for user {user_id} for the period. User might not exist or has no data."
            )
            # This could indicate the user_id itself was not found by the service.
            raise ResourceNotFoundError(resource_name="User KPI Summary", resource_id=str(user_id))

        return summary_data

    except (
        HTTPException
    ):  # Re-raise HTTPExceptions from FastAPI/Pydantic or explicitly raised custom ones that inherit from it.
        raise
    except (
        ResourceNotFoundError,
        BadRequestError,
        PermissionDeniedError,
    ) as app_base_exc:  # Re-raise our known app exceptions
        raise app_base_exc
    except (
        ValueError
    ) as ve:  # Catch specific errors like date parsing or bad values from service if not caught by Pydantic
        logger.warning(f"ValueError during KPI summary for user {user_id}: {ve}", exc_info=True)
        raise BadRequestError(message=f"Invalid input or data for KPI summary: {str(ve)}")
    except Exception as e:
        logger.error(f"Unexpected error fetching KPI summary for user {user_id}: {e}", exc_info=True)
        raise DatabaseError(message=f"An unexpected error occurred while fetching KPI summary.")



@router.post("/backfill/github-analysis")
async def backfill_github_analysis(
    file_path: str = Query(..., description="Absolute path to a github_analysis_*.json file on server"),
    kpi_service: KpiService = Depends(get_kpi_service),
):
    """Load an exported GitHub analysis JSON and persist pull-request level analytics.

    The legacy implementation stored commit-level data. This version maps the historical analysis
    export to the new pull request centric metrics so the manager dashboard can be backfilled.
    """
    try:
        if not file_path or not os.path.isfile(file_path):
            raise HTTPException(status_code=400, detail="File not found")

        import json
        import re
        from datetime import datetime as _dt, timezone as _tz
        from decimal import Decimal

        from app.config.supabase_client import get_supabase_client_safe
        from app.models.pull_request import PullRequest
        from app.repositories.pull_request_repository import PullRequestRepository

        def _parse_datetime(value: str | None) -> _dt | None:
            if not value:
                return None
            try:
                dt = _dt.fromisoformat(value.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=_tz.utc)
                return dt
            except Exception:
                return None

        def _ensure_list(value):
            if value is None:
                return []
            if isinstance(value, list):
                return [str(v) for v in value]
            return [str(value)]

        def _extract_pr_number(candidate: dict) -> int | None:
            for key in ("pr_number", "number", "id"):
                val = candidate.get(key)
                if isinstance(val, int):
                    return val
                if isinstance(val, str) and val.isdigit():
                    return int(val)
            message = candidate.get("title") or candidate.get("message") or ""
            match = re.search(r"#(\d+)", message)
            if match:
                return int(match.group(1))
            return None

        with open(file_path, "r") as f:
            data = json.load(f)

        daily_summaries = (data or {}).get("summary", {}).get("daily_summaries", []) or []
        if not daily_summaries:
            return {"status": "ok", "message": "No daily summaries found in JSON.", "inserted": 0}

        repo = PullRequestRepository(get_supabase_client_safe())
        inserted = 0

        for day in daily_summaries:
            pr_candidates = (
                day.get("pull_requests")
                or day.get("pull_request_summaries")
                or day.get("prs")
                or day.get("commit_summaries")
                or []
            )
            if not isinstance(pr_candidates, list):
                continue

            total_hours_for_day = (
                day.get("total_hours")
                or day.get("daily_analysis", {}).get("total_estimated_hours")
                or 0.0
            )
            hours_per_candidate = (
                (float(total_hours_for_day) / len(pr_candidates))
                if pr_candidates and total_hours_for_day
                else 0.0
            )

            for candidate in pr_candidates:
                try:
                    if not isinstance(candidate, dict):
                        continue

                    pr_number = _extract_pr_number(candidate)
                    if pr_number is None:
                        continue

                    status = candidate.get("status") or (
                        "merged"
                        if candidate.get("merged_at") or "Merged" in str(candidate.get("message", ""))
                        else "closed" if candidate.get("closed_at") else "open"
                    )

                    hours_value = candidate.get("ai_estimated_hours") or candidate.get("estimated_hours")
                    if hours_value is None:
                        hours_value = hours_per_candidate

                    summary = PullRequest(
                        pr_number=pr_number,
                        title=candidate.get("title") or candidate.get("summary") or candidate.get("message"),
                        description=candidate.get("description"),
                        author_github_username=candidate.get("author_github_username")
                        or candidate.get("author")
                        or day.get("github_username"),
                        author_email=candidate.get("author_email") or day.get("author_email"),
                        repository_name=candidate.get("repository") or (data or {}).get("repository"),
                        repository_url=candidate.get("repository_url"),
                        url=candidate.get("url") or candidate.get("html_url"),
                        status=status,
                        opened_at=_parse_datetime(candidate.get("opened_at") or candidate.get("created_at")),
                        closed_at=_parse_datetime(candidate.get("closed_at")),
                        merged_at=_parse_datetime(candidate.get("merged_at")),
                        activity_timestamp=_parse_datetime(
                            candidate.get("activity_timestamp")
                            or candidate.get("merged_at")
                            or candidate.get("closed_at")
                            or candidate.get("updated_at")
                            or candidate.get("timestamp")
                            or day.get("date")
                        ),
                        ai_estimated_hours=Decimal(str(hours_value or 0.0)),
                        ai_summary=candidate.get("ai_summary")
                        or candidate.get("summary")
                        or day.get("daily_analysis", {}).get("work_summary"),
                        ai_prompts=_ensure_list(
                            candidate.get("ai_prompts")
                            or candidate.get("prompts")
                            or day.get("daily_analysis", {}).get("recommendations")
                        ),
                        ai_analysis_notes=candidate,
                        impact_score=float(candidate.get("impact_score"))
                        if candidate.get("impact_score") is not None
                        else None,
                        impact_category=candidate.get("impact_category"),
                        review_comments=candidate.get("review_comments") or candidate.get("comments"),
                    )

                    await repo.save_pull_request(summary)
                    inserted += 1
                except Exception as item_exc:
                    logger.warning(f"Skipping PR entry due to error: {item_exc}")
                    continue

        return {"status": "ok", "inserted": inserted}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Backfill failed")
# TODO: Consider adding a main router in backend/app/api/v1/api.py to include this kpi_router
# e.g.:
# from fastapi import APIRouter
# from .endpoints import kpi, users # ... and other endpoint routers
# api_v1_router = APIRouter()
# api_v1_router.include_router(users.router, prefix="/users", tags=["Users"])
# api_v1_router.include_router(kpi.router, prefix="/kpi", tags=["KPIs"])
