import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import requests

from app.config.settings import settings
from app.core.exceptions import ConfigurationError, ExternalServiceError
from supabase import Client

logger = logging.getLogger(__name__)


@dataclass
class ZapierWeeklyData:
    """Data structure for weekly analytics from Zapier"""

    wins: List[str]
    csat_score: float
    csat_change_percentage: Optional[float]
    user_feedback_summary: str
    social_media_views: int
    social_views_change_percentage: Optional[float]
    tiktok_views: int
    instagram_views: int
    youtube_views: int
    facebook_views: int
    average_shipping_time: float
    weeks_since_logistics_mistake: int
    logistics_mistake_notes: Optional[str]
    weekly_retention: Dict[str, float]
    monthly_retention: Dict[str, float]


@dataclass
class ZapierObjectiveData:
    """Data structure for ClickUp objectives"""

    id: str
    name: str
    completion_percentage: float
    due_date: str
    owner: str
    sparkline_data: List[float]


class ZapierIntegrationService:
    """Service for integrating data from Zapier flows"""

    def __init__(self, supabase: Client):
        self.supabase = supabase
        self.zapier_webhook_urls = {
            "weekly_analytics": getattr(settings, "ZAPIER_WEEKLY_ANALYTICS_URL", None),
            "objectives": getattr(settings, "ZAPIER_OBJECTIVES_URL", None),
        }

    async def get_current_week_data(self) -> Optional[ZapierWeeklyData]:
        """
        Retrieves current week's data from Zapier Weekly Analytics Report table
        """
        try:
            # Get current week start (Monday)
            today = datetime.now()
            week_start = today - timedelta(days=today.weekday())
            week_start_str = week_start.strftime("%Y-%m-%d")

            # Query Zapier table via webhook or direct API call
            # This assumes you have a way to query the Zapier table
            # You might need to create a Zapier webhook that returns current week data

            # For now, we'll simulate the data structure based on your flows
            # In production, this would be an actual API call to Zapier

            # This is a placeholder - replace with actual Zapier API integration
            mock_data = ZapierWeeklyData(
                wins=[
                    "Great job Breno for nailing those bugs!",
                    "Well done Leandro for your awesome contributions!",
                    "Kudos to Ravi for being our reliable rock!",
                ],
                csat_score=4.91,
                csat_change_percentage=5.0,
                user_feedback_summary=(
                    "Swing Analysis Time Swing Simulation Issues Inaccurate Distances "
                    "Unable to Change Home SitDS Code Issues Delayed Orders "
                    "Requests for Cancellation or Address Change"
                ),
                social_media_views=29243000,
                social_views_change_percentage=7.0,
                tiktok_views=5000000,
                instagram_views=8000000,
                youtube_views=10000000,
                facebook_views=6243000,
                average_shipping_time=3.6,
                weeks_since_logistics_mistake=10,
                logistics_mistake_notes=None,
                weekly_retention={
                    "Day 0": 100.0,
                    "Day 1": 7.69,
                    "Day 2": 4.85,
                    "Day 3": 3.39,
                    "Day 4": 3.59,
                    "Day 5": 2.79,
                    "Day 6": 2.63,
                },
                monthly_retention={"Week 0": 94.87, "Week 1": 7.74, "Week 2": 4.65},
            )

            return mock_data

        except Exception as e:
            logger.error(f"Error fetching current week data from Zapier: {e}")
            return None

    async def get_current_objectives(self) -> List[ZapierObjectiveData]:
        """
        Retrieves current objectives from ClickUp via Zapier integration
        """
        try:
            # This would be actual ClickUp API calls via Zapier
            # For now, returning mock data based on your dashboard

            objectives = [
                ZapierObjectiveData(
                    id="obj_1",
                    name="Double Week 1 retention to 17% via App improvements",
                    completion_percentage=75.0,
                    due_date="04/07/25",
                    owner="Ryan Cassidy",
                    sparkline_data=[0, 10, 25, 40, 60, 75],
                ),
                ZapierObjectiveData(
                    id="obj_2",
                    name="Double Week 1 retention to 17% via ML improvements",
                    completion_percentage=17.0,
                    due_date="05/28/25",
                    owner="Jonathan Cefalu",
                    sparkline_data=[0, 5, 8, 12, 15, 17],
                ),
                ZapierObjectiveData(
                    id="obj_3",
                    name="Debrief Daniel about Tariffs supply chain effects and mitigation strategy",
                    completion_percentage=100.0,
                    due_date="05/15/25",
                    owner="Laura Obregon",
                    sparkline_data=[0, 20, 50, 75, 90, 100],
                ),
                ZapierObjectiveData(
                    id="obj_4",
                    name="Conquer Our Digital Customer Acquisition Funnel",
                    completion_percentage=100.0,
                    due_date="05/07/25",
                    owner="Paul Boranian",
                    sparkline_data=[0, 15, 35, 60, 85, 100],
                ),
                ZapierObjectiveData(
                    id="obj_5",
                    name="Meeting new KPIs, Increase AI automation, & user flow descriptions",
                    completion_percentage=40.0,
                    due_date="05/09/25",
                    owner="Jon Cruz",
                    sparkline_data=[0, 8, 15, 25, 35, 40],
                ),
            ]

            return objectives

        except Exception as e:
            logger.error(f"Error fetching objectives from ClickUp: {e}")
            return []

    async def get_business_goals(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieves business goals data
        """
        try:
            return {
                "short_term": [
                    {
                        "id": "st_1",
                        "name": "Improve onboarding experience and customer obsession company culture",
                        "tags": ["Product Improvement"],
                    },
                    {
                        "id": "st_2",
                        "name": "Achieve faster iteration & smooth cadence of game development and releases",
                        "tags": ["Product Improvement"],
                    },
                    {
                        "id": "st_3",
                        "name": "Improve organisation of operations to increase leverage of CEO to execute on long term vision",
                        "tags": ["Organizational"],
                    },
                ],
                "long_term": [
                    {"id": "lt_1", "name": "Accurate simulation AI", "tags": ["Product Improvement"]},
                    {
                        "id": "lt_2",
                        "name": "New golf at home product design & experience",
                        "tags": ["Product Improvement"],
                    },
                    {"id": "lt_3", "name": "New Golf Club Prototype", "tags": ["Product Improvement"]},
                ],
            }
        except Exception as e:
            logger.error(f"Error fetching business goals: {e}")
            return {"short_term": [], "long_term": []}

    async def get_company_mission(self) -> List[str]:
        """
        Returns the company mission points
        """
        return [
            "Achieve realistic golf simulation in an aesthetic at home experience.",
            "Support the improvement of golfers.",
            "Provide it at a fraction of the cost of other golf practice options.",
            "Support entertaining competitive golf gamemodes.",
            "Achieve realistic golf simulation in an aesthetic at home experience.",
            "Golf anywhere, anytime, anyone.",
        ]

    async def trigger_zapier_webhook(self, webhook_type: str, data: Dict[str, Any]) -> bool:
        """
        Triggers a Zapier webhook with the provided data
        """
        try:
            webhook_url = self.zapier_webhook_urls.get(webhook_type)
            if not webhook_url:
                logger.warning(f"No webhook URL configured for type: {webhook_type}")
                return False

            response = requests.post(webhook_url, json=data, headers={"Content-Type": "application/json"}, timeout=30)

            if response.status_code == 200:
                logger.info(f"Successfully triggered Zapier webhook: {webhook_type}")
                return True
            else:
                logger.error(f"Zapier webhook failed with status {response.status_code}: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error triggering Zapier webhook {webhook_type}: {e}")
            return False

    async def refresh_dashboard_data(self) -> bool:
        """
        Triggers a full refresh of dashboard data from all Zapier sources
        """
        try:
            # This would trigger all your Zapier flows to refresh data
            success = True

            # Trigger weekly analytics refresh
            if not await self.trigger_zapier_webhook("weekly_analytics", {"action": "refresh"}):
                success = False

            # Trigger objectives refresh
            if not await self.trigger_zapier_webhook("objectives", {"action": "refresh"}):
                success = False

            return success

        except Exception as e:
            logger.error(f"Error refreshing dashboard data: {e}")
            return False
