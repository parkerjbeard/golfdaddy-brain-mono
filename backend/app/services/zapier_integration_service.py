import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

import requests

from app.config.settings import settings
from app.core.exceptions import ConfigurationError
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

    async def _run_supabase(self, fn):
        """Run blocking Supabase calls in a thread to keep async endpoints responsive."""
        return await asyncio.to_thread(fn)

    @staticmethod
    def _iso(dt: datetime) -> str:
        return dt.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        if isinstance(value, str):
            try:
                # Support timestamps with or without timezone/Z suffix
                if value.endswith("Z"):
                    value = value.replace("Z", "+00:00")
                dt = datetime.fromisoformat(value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                return None
        return None

    @staticmethod
    def _average(numbers: Sequence[float]) -> Optional[float]:
        nums = [n for n in numbers if isinstance(n, (int, float))]
        return sum(nums) / len(nums) if nums else None

    @staticmethod
    def _percent_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
        if previous and previous != 0 and current is not None:
            return ((current - previous) / previous) * 100
        return None

    @staticmethod
    def _extract_numeric_metric(metric_value: Any) -> Optional[float]:
        """Attempt to pull a numeric value from the analytics.metric_value JSON."""
        if isinstance(metric_value, (int, float)):
            return float(metric_value)
        if isinstance(metric_value, dict):
            for key in ["value", "average", "avg", "metric", "number"]:
                if isinstance(metric_value.get(key), (int, float)):
                    return float(metric_value[key])
        return None

    async def get_dashboard_overview(self) -> Dict[str, Any]:
        """Builds dashboard overview data from Supabase tables with sensible fallbacks."""
        try:
            now = datetime.now(timezone.utc)

            # Active projects from objectives (status active)
            active_resp = await self._run_supabase(
                lambda: self.supabase
                .table("objectives")
                .select("id,title,owner,team,due_date,progress,status,updated_at")
                .eq("status", "active")
                .order("updated_at", desc=True)
                .limit(50)
                .execute()
            )

            archived_resp = await self._run_supabase(
                lambda: self.supabase
                .table("objectives")
                .select("id,title,owner,team,due_date,progress,status,updated_at,original_due_date")
                .eq("status", "archived")
                .order("updated_at", desc=True)
                .limit(50)
                .execute()
            )

            def map_objectives(rows):
                projects = []
                for row in rows or []:
                    projects.append(
                        {
                            "id": str(row.get("id")),
                            "name": row.get("title") or "Untitled objective",
                            "owner": {
                                "name": row.get("owner") or "Unassigned",
                                "initials": ((row.get("owner") or "")[:2].upper()),
                            },
                            "team": row.get("team") or "General",
                            "progress": row.get("progress") or 0,
                            "status": row.get("status") or "working on it",
                            "dueDate": row.get("due_date") or None,
                            "originalDueDate": row.get("original_due_date") or row.get("due_date"),
                            "keyResults": [],
                        }
                    )
                return projects

            active_projects = map_objectives(getattr(active_resp, "data", [])) if active_resp else []
            archived_projects = map_objectives(getattr(archived_resp, "data", [])) if archived_resp else []

            # Issues list from analytics metric "issues" (expects list of strings)
            issues_resp = await self._run_supabase(
                lambda: self.supabase
                .table("analytics")
                .select("metric_value,timestamp")
                .eq("metric_name", "issues")
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )
            issues_list: List[str] = []
            if issues_resp and issues_resp.data:
                mv = issues_resp.data[0].get("metric_value")
                if isinstance(mv, list):
                    issues_list = [str(x) for x in mv]
                elif isinstance(mv, dict):
                    issues_list = [str(v) for v in mv.values()]

            # Insights
            insights_resp = await self._run_supabase(
                lambda: self.supabase
                .table("analytics")
                .select("metric_value,timestamp")
                .eq("metric_name", "insights_weekly")
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )
            weekly_insights = None
            if insights_resp and insights_resp.data:
                mv = insights_resp.data[0].get("metric_value")
                if isinstance(mv, str):
                    weekly_insights = mv
                elif isinstance(mv, dict):
                    weekly_insights = mv.get("text") or mv.get("value")

            # Team stats derived from active/archived objectives per team
            team_stats: Dict[str, Dict[str, int]] = {}
            for proj in active_projects:
                team = proj.get("team", "General")
                team_stats.setdefault(team, {"active": 0, "archived": 0})
                team_stats[team]["active"] += 1
            for proj in archived_projects:
                team = proj.get("team", "General")
                team_stats.setdefault(team, {"active": 0, "archived": 0})
                team_stats[team]["archived"] += 1

            return {
                "dashboard": {
                    "lastUpdated": now.isoformat(),
                    "kpis": {
                        "csat": {"current": 0, "previous": 0, "trend": "neutral", "change": 0},
                        "socialMedia": {"totalViews": 0, "platforms": []},
                        "retention": {"week0": 100, "week1": 0, "week2": 0, "week1Target": 17.0},
                    },
                    "projects": {"active": active_projects, "archived": archived_projects},
                    "issues": {"customerSupport": issues_list},
                    "insights": {"weekly": weekly_insights or ""},
                    "teamStats": team_stats,
                }
            }
        except Exception as e:
            logger.error(f"Error building dashboard overview: {e}")
            return {}

    def _mock_week_data(self) -> ZapierWeeklyData:
        """Fallback mock data to keep the dashboard usable if Supabase/Zapier data is unavailable."""
        return ZapierWeeklyData(
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

    async def get_current_week_data(self) -> Optional[ZapierWeeklyData]:
        """
        Retrieves current week's data from Zapier Weekly Analytics Report table
        """
        try:
            if not self.supabase:
                raise ConfigurationError("Supabase client not configured")

            today = datetime.now(timezone.utc)
            # Normalize week boundaries to midnight to avoid dropping early-week data
            week_start = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            prev_week_start = week_start - timedelta(days=7)
            week_end = week_start + timedelta(days=7)

            week_start_iso = self._iso(week_start)
            week_end_iso = self._iso(week_end)
            prev_week_start_iso = self._iso(prev_week_start)
            prev_week_end_iso = week_start_iso

            # Wins (latest titles/descriptions this week)
            wins_resp = await self._run_supabase(
                lambda: self.supabase
                .table("wins")
                .select("title,description,timestamp")
                .gte("timestamp", week_start_iso)
                .lt("timestamp", week_end_iso)
                .order("timestamp", desc=True)
                .limit(10)
                .execute()
            )
            wins = []
            if wins_resp and getattr(wins_resp, "data", None):
                for row in wins_resp.data:
                    title = row.get("title") or row.get("description")
                    if title:
                        wins.append(title)

            # CSAT scores
            current_csat_resp = await self._run_supabase(
                lambda: self.supabase
                .table("user_feedback")
                .select("csat_score,timestamp")
                .gte("timestamp", week_start_iso)
                .lt("timestamp", week_end_iso)
                .execute()
            )
            previous_csat_resp = await self._run_supabase(
                lambda: self.supabase
                .table("user_feedback")
                .select("csat_score,timestamp")
                .gte("timestamp", prev_week_start_iso)
                .lt("timestamp", prev_week_end_iso)
                .execute()
            )
            current_csat = self._average([row.get("csat_score") for row in (current_csat_resp.data or [])])
            previous_csat = self._average([row.get("csat_score") for row in (previous_csat_resp.data or [])])
            csat_change_percentage = self._percent_change(current_csat, previous_csat)

            # Feedback summary (latest snippets)
            feedback_resp = await self._run_supabase(
                lambda: self.supabase
                .table("user_feedback")
                .select("feedback_text,timestamp")
                .order("timestamp", desc=True)
                .limit(5)
                .execute()
            )
            feedback_texts = [row.get("feedback_text") for row in (feedback_resp.data or []) if row.get("feedback_text")]
            user_feedback_summary = " \u2022 ".join(feedback_texts) if feedback_texts else "No feedback yet"

            # Social media views (current vs previous week)
            social_resp = await self._run_supabase(
                lambda: self.supabase
                .table("social_media_metrics")
                .select("views,timestamp")
                .gte("timestamp", week_start_iso)
                .lt("timestamp", week_end_iso)
                .execute()
            )
            prev_social_resp = await self._run_supabase(
                lambda: self.supabase
                .table("social_media_metrics")
                .select("views,timestamp")
                .gte("timestamp", prev_week_start_iso)
                .lt("timestamp", prev_week_end_iso)
                .execute()
            )
            social_media_views = sum([row.get("views", 0) or 0 for row in (social_resp.data or [])])
            prev_social_views = sum([row.get("views", 0) or 0 for row in (prev_social_resp.data or [])])
            social_views_change_percentage = self._percent_change(social_media_views, prev_social_views)

            # Retention data from analytics table
            weekly_retention_resp = await self._run_supabase(
                lambda: self.supabase
                .table("analytics")
                .select("metric_value,timestamp")
                .eq("metric_name", "weekly_retention")
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )
            weekly_retention = {}
            if weekly_retention_resp and weekly_retention_resp.data:
                value = weekly_retention_resp.data[0].get("metric_value")
                if isinstance(value, dict):
                    weekly_retention = value

            monthly_retention_resp = await self._run_supabase(
                lambda: self.supabase
                .table("analytics")
                .select("metric_value,timestamp")
                .eq("metric_name", "monthly_retention")
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )
            monthly_retention = {}
            if monthly_retention_resp and monthly_retention_resp.data:
                value = monthly_retention_resp.data[0].get("metric_value")
                if isinstance(value, dict):
                    monthly_retention = value

            # Shipping metrics
            shipping_resp = await self._run_supabase(
                lambda: self.supabase
                .table("analytics")
                .select("metric_value,timestamp")
                .eq("metric_name", "average_shipping_time")
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )
            average_shipping_time = None
            if shipping_resp and shipping_resp.data:
                average_shipping_time = self._extract_numeric_metric(shipping_resp.data[0].get("metric_value"))

            # Weeks since last logistics mistake (uses analytics metric_name "logistics_mistake")
            logistics_resp = await self._run_supabase(
                lambda: self.supabase
                .table("analytics")
                .select("timestamp")
                .eq("metric_name", "logistics_mistake")
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )
            weeks_since_logistics_mistake = 0
            logistics_ts = None
            if logistics_resp and logistics_resp.data:
                logistics_ts = self._parse_datetime(logistics_resp.data[0].get("timestamp"))
            if logistics_ts:
                delta_days = (today - logistics_ts).days
                weeks_since_logistics_mistake = max(delta_days // 7, 0)

            # Social platform breakdown placeholders (can be extended when data present)
            tiktok_views = instagram_views = youtube_views = facebook_views = 0

            return ZapierWeeklyData(
                wins=wins,
                csat_score=current_csat or 0,
                csat_change_percentage=csat_change_percentage,
                user_feedback_summary=user_feedback_summary,
                social_media_views=social_media_views,
                social_views_change_percentage=social_views_change_percentage,
                tiktok_views=tiktok_views,
                instagram_views=instagram_views,
                youtube_views=youtube_views,
                facebook_views=facebook_views,
                average_shipping_time=average_shipping_time or 0,
                weeks_since_logistics_mistake=weeks_since_logistics_mistake,
                logistics_mistake_notes=None,
                weekly_retention=weekly_retention,
                monthly_retention=monthly_retention,
            )

        except Exception as e:
            logger.error(f"Error fetching current week data from Zapier/Supabase: {e}")
            return self._mock_week_data()

    async def get_current_objectives(self) -> List[ZapierObjectiveData]:
        """
        Retrieves current objectives from ClickUp via Zapier integration
        """
        try:
            if not self.supabase:
                raise ConfigurationError("Supabase client not configured")

            objectives_resp = await self._run_supabase(
                lambda: self.supabase
                .table("objectives")
                .select("id,title,owner,due_date,progress,updated_at")
                .eq("status", "active")
                .order("updated_at", desc=True)
                .limit(20)
                .execute()
            )

            objectives: List[ZapierObjectiveData] = []
            for row in (objectives_resp.data or []):
                due_date = row.get("due_date") or row.get("timestamp") or ""
                objectives.append(
                    ZapierObjectiveData(
                        id=str(row.get("id")),
                        name=row.get("title") or "Untitled objective",
                        completion_percentage=float(row.get("progress") or 0),
                        due_date=str(due_date),
                        owner=row.get("owner") or "Unassigned",
                        sparkline_data=[float(row.get("progress") or 0)],
                    )
                )

            if objectives:
                return objectives

        except Exception as e:
            logger.error(f"Error fetching objectives from Supabase/Zapier: {e}")

        # Fallback to the previous static set to avoid breaking the UI
        return [
            ZapierObjectiveData(
                id="obj_1",
                name="Double Week 1 retention to 17% via App improvements",
                completion_percentage=75.0,
                due_date="2025-07-04",
                owner="Ryan Cassidy",
                sparkline_data=[0, 10, 25, 40, 60, 75],
            ),
            ZapierObjectiveData(
                id="obj_2",
                name="Double Week 1 retention to 17% via ML improvements",
                completion_percentage=17.0,
                due_date="2025-05-28",
                owner="Jonathan Cefalu",
                sparkline_data=[0, 5, 8, 12, 15, 17],
            ),
        ]

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
