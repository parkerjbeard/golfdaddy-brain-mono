"""
API endpoints for Zapier dashboard data integration.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.config.supabase_client import get_supabase_client_safe as get_db
from app.core.exceptions import ExternalServiceError
from app.models.user import User
from app.services.zapier_integration_service import ZapierIntegrationService
from supabase import Client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/zapier", tags=["zapier"])


# Response models
class WeeklyDataResponse(BaseModel):
    wins: List[str]
    csat_score: float
    csat_change_percentage: float | None
    user_feedback_summary: str
    social_media_views: int
    social_views_change_percentage: float | None
    average_shipping_time: float
    weeks_since_logistics_mistake: int
    weekly_retention: Dict[str, float]
    monthly_retention: Dict[str, float]


class ObjectiveResponse(BaseModel):
    id: str
    name: str
    completion_percentage: float
    due_date: str
    owner: str
    sparkline_data: List[float]


class BusinessGoalsResponse(BaseModel):
    short_term: List[Dict[str, Any]]
    long_term: List[Dict[str, Any]]


class DashboardRefreshResponse(BaseModel):
    success: bool
    message: str
    timestamp: datetime


def get_zapier_service(db: Client = Depends(get_db)) -> ZapierIntegrationService:
    """Dependency to get Zapier integration service."""
    return ZapierIntegrationService(db)


@router.get("/weekly-data", response_model=WeeklyDataResponse)
async def get_weekly_data(
    zapier_service: ZapierIntegrationService = Depends(get_zapier_service),
    current_user: User = Depends(get_current_user),
):
    """
    Get current week's analytics data from Zapier flows.

    Returns data from:
    - Employee acknowledgments (Wins)
    - CSAT scores and user feedback
    - Social media views
    - Shipping/logistics metrics
    - App retention data
    """
    try:
        weekly_data = await zapier_service.get_current_week_data()

        if not weekly_data:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to fetch weekly data from Zapier"
            )

        return WeeklyDataResponse(
            wins=weekly_data.wins,
            csat_score=weekly_data.csat_score,
            csat_change_percentage=weekly_data.csat_change_percentage,
            user_feedback_summary=weekly_data.user_feedback_summary,
            social_media_views=weekly_data.social_media_views,
            social_views_change_percentage=weekly_data.social_views_change_percentage,
            average_shipping_time=weekly_data.average_shipping_time,
            weeks_since_logistics_mistake=weekly_data.weeks_since_logistics_mistake,
            weekly_retention=weekly_data.weekly_retention,
            monthly_retention=weekly_data.monthly_retention,
        )

    except Exception as e:
        logger.error(f"Error fetching weekly data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error while fetching weekly data"
        )


@router.get("/objectives", response_model=List[ObjectiveResponse])
async def get_objectives(
    zapier_service: ZapierIntegrationService = Depends(get_zapier_service),
    current_user: User = Depends(get_current_user),
):
    """
    Get current objectives from ClickUp via Zapier integration.

    Returns objective data including:
    - Completion percentages
    - Due dates
    - Owners
    - Progress sparkline data
    """
    try:
        objectives = await zapier_service.get_current_objectives()

        return [
            ObjectiveResponse(
                id=obj.id,
                name=obj.name,
                completion_percentage=obj.completion_percentage,
                due_date=obj.due_date,
                owner=obj.owner,
                sparkline_data=obj.sparkline_data,
            )
            for obj in objectives
        ]

    except Exception as e:
        logger.error(f"Error fetching objectives: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error while fetching objectives"
        )


@router.get("/business-goals", response_model=BusinessGoalsResponse)
async def get_business_goals(
    zapier_service: ZapierIntegrationService = Depends(get_zapier_service),
    current_user: User = Depends(get_current_user),
):
    """
    Get business goals categorized as short-term and long-term.
    """
    try:
        goals = await zapier_service.get_business_goals()

        return BusinessGoalsResponse(short_term=goals["short_term"], long_term=goals["long_term"])

    except Exception as e:
        logger.error(f"Error fetching business goals: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while fetching business goals",
        )


@router.get("/mission", response_model=List[str])
async def get_company_mission(
    zapier_service: ZapierIntegrationService = Depends(get_zapier_service),
    current_user: User = Depends(get_current_user),
):
    """
    Get company mission statement points.
    """
    try:
        mission = await zapier_service.get_company_mission()
        return mission

    except Exception as e:
        logger.error(f"Error fetching mission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error while fetching mission"
        )


@router.post("/refresh", response_model=DashboardRefreshResponse)
async def refresh_dashboard_data(
    zapier_service: ZapierIntegrationService = Depends(get_zapier_service),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger a refresh of all dashboard data from Zapier sources.

    This will trigger all relevant Zapier flows to update:
    - Weekly analytics data
    - Objectives from ClickUp
    - Social media metrics
    - Retention data from Amplitude
    """
    try:
        success = await zapier_service.refresh_dashboard_data()

        return DashboardRefreshResponse(
            success=success,
            message="Dashboard refresh triggered successfully" if success else "Some data sources failed to refresh",
            timestamp=datetime.now(),
        )

    except Exception as e:
        logger.error(f"Error refreshing dashboard data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while refreshing dashboard data",
        )
