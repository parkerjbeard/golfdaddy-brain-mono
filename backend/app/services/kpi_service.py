import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.exceptions import ResourceNotFoundError
from app.models.pull_request import PullRequest
from app.models.user import User, UserRole
from app.repositories.daily_report_repository import DailyReportRepository
from app.repositories.pull_request_repository import PullRequestRepository
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class UserWidgetSummary(BaseModel):
    """Lightweight aggregate used to render manager dashboard tiles."""

    user_id: UUID
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    total_prs: int
    merged_prs: int
    total_ai_estimated_pr_hours: float
    total_business_points: float
    efficiency_points_per_hour: float
    normalized_efficiency_points_per_hour: Optional[float] = None
    efficiency_provisional: Optional[bool] = None
    efficiency_baseline_source: Optional[str] = None
    activity_score: float
    day_off: bool = False
    daily_prs_series: List[Dict[str, Any]] = Field(default_factory=list)
    daily_hours_series: List[Dict[str, Any]] = Field(default_factory=list)
    daily_points_series: List[Dict[str, Any]] = Field(default_factory=list)
    latest_activity_timestamp: Optional[str] = None
    latest_pr_title: Optional[str] = None


class KpiService:
    """Service for calculating pull-request centric performance metrics."""

    def __init__(self):
        self.user_repo = UserRepository()
        self.pull_request_repo = PullRequestRepository()
        self.daily_report_repo = DailyReportRepository()
        # Normalization config (maps points-per-hour to qualitative baselines)
        self.norm_h_min = 2.0
        self.baseline_window_days = 60
        self.baseline_min_hours = 10.0
        self.norm_ratio_min = 0.25
        self.norm_ratio_max = 4.0
        self.category_default_pph = {
            "capability": 3.0,
            "improvement": 2.5,
            "fix": 2.0,
            "foundation": 1.2,
            "maintenance": 1.0,
        }

    # ------------------------------------------------------------------
    # AI note + classification helpers
    # ------------------------------------------------------------------
    def _parse_ai_notes(self, record: PullRequest) -> Dict[str, Any]:
        raw_notes = getattr(record, "ai_analysis_notes", None)
        if raw_notes is None:
            return {}
        if isinstance(raw_notes, dict):
            return raw_notes
        if isinstance(raw_notes, str) and raw_notes.strip():
            try:
                return json.loads(raw_notes)
            except json.JSONDecodeError:
                logger.debug("Failed to decode ai_analysis_notes for PR %s", record.pr_number)
        return {}

    def _get_category(self, notes: Dict[str, Any], fallback: Optional[str] = None) -> str:
        if fallback:
            return fallback.lower()
        classification = notes.get("impact_classification") or {}
        if isinstance(classification, dict):
            candidate = (
                classification.get("primary_category")
                or classification.get("primary")
                or classification.get("category")
            )
            if isinstance(candidate, str) and candidate:
                return candidate.lower()
        dominant = notes.get("impact_dominant_category")
        if isinstance(dominant, str) and dominant:
            return dominant.lower()
        return "maintenance"

    def _extract_impact_score(self, record: PullRequest, notes: Dict[str, Any]) -> float:
        candidate = getattr(record, "impact_score", None)
        if candidate is not None:
            try:
                return float(candidate)
            except (TypeError, ValueError):
                logger.debug("Unable to cast impact_score for PR %s", record.pr_number)
        raw = notes.get("impact_score")
        if raw is None:
            raw = notes.get("impact", {}).get("score") if isinstance(notes.get("impact"), dict) else None
        try:
            return float(raw or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _sum_points_hours_by_category(self, records: List[PullRequest]) -> Dict[str, Dict[str, float]]:
        aggregates: Dict[str, Dict[str, float]] = {}
        for record in records:
            notes = self._parse_ai_notes(record)
            category = self._get_category(notes, getattr(record, "impact_category", None))
            points = self._extract_impact_score(record, notes)
            hours = float(record.ai_estimated_hours or 0.0)
            bucket = aggregates.setdefault(category, {"points": 0.0, "hours": 0.0})
            bucket["points"] += points
            bucket["hours"] += hours
        return aggregates

    async def _compute_personal_baselines(self, user_id: UUID, baseline_end: datetime) -> Dict[str, float]:
        try:
            baseline_start = (baseline_end - timedelta(days=self.baseline_window_days)).date()
            baseline_end_date = baseline_end.date()
            prs = await self.pull_request_repo.get_pull_requests_by_user_in_range(
                user_id, baseline_start, baseline_end_date
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning("Failed to load baseline PRs for user %s: %s", user_id, exc, exc_info=True)
            prs = []

        aggregates = self._sum_points_hours_by_category(prs)
        baselines: Dict[str, float] = dict(self.category_default_pph)
        for category, values in aggregates.items():
            hours = values.get("hours", 0.0) or 0.0
            points = values.get("points", 0.0) or 0.0
            if hours >= self.baseline_min_hours and hours > 0:
                baselines[category] = max(points / hours, 0.01)
        return baselines

    def _compute_normalized_efficiency(
        self,
        period_agg: Dict[str, Dict[str, float]],
        baselines: Dict[str, float],
    ) -> Tuple[float, bool, str]:
        total_hours = 0.0
        weighted_sum = 0.0
        used_default = False

        for values in period_agg.values():
            hours = values.get("hours", 0.0) or 0.0
            points = values.get("points", 0.0) or 0.0
            if hours <= 0 and points <= 0:
                continue
            total_hours += hours

        if total_hours <= 0:
            return (0.0, False, "personal")

        for category, values in period_agg.items():
            hours = values.get("hours", 0.0) or 0.0
            points = values.get("points", 0.0) or 0.0
            if hours <= 0:
                continue
            pph = points / max(hours, self.norm_h_min)
            baseline = baselines.get(category)
            if baseline is None:
                baseline = self.category_default_pph.get(category, 1.0)
                used_default = True
            elif abs(baseline - self.category_default_pph.get(category, baseline)) < 1e-9:
                used_default = True
            ratio = pph / max(baseline, 0.01)
            ratio = max(self.norm_ratio_min, min(self.norm_ratio_max, ratio))
            weighted_sum += ratio * hours

        normalized = weighted_sum / total_hours if total_hours > 0 else 0.0
        return (round(normalized, 2), used_default, "default" if used_default else "personal")

    # ------------------------------------------------------------------
    # Metric helpers
    # ------------------------------------------------------------------
    def _resolve_activity_timestamp(self, record: PullRequest) -> Optional[datetime]:
        for attr in ("activity_timestamp", "merged_at", "closed_at", "opened_at"):
            ts = getattr(record, attr, None)
            if ts:
                if isinstance(ts, datetime):
                    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
                if isinstance(ts, str):
                    try:
                        parsed = datetime.fromisoformat(ts)
                        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
                    except ValueError:
                        continue
        return None

    def _collect_daily_rollups(
        self, records: List[PullRequest]
    ) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, int]]:
        daily_hours: Dict[str, float] = {}
        daily_points: Dict[str, float] = {}
        daily_counts: Dict[str, int] = {}
        for record in records:
            ts = self._resolve_activity_timestamp(record)
            if not ts:
                continue
            date_key = ts.date().strftime("%Y-%m-%d")
            hours = float(record.ai_estimated_hours or 0.0)
            notes = self._parse_ai_notes(record)
            points = self._extract_impact_score(record, notes)
            daily_hours[date_key] = daily_hours.get(date_key, 0.0) + hours
            daily_points[date_key] = daily_points.get(date_key, 0.0) + points
            daily_counts[date_key] = daily_counts.get(date_key, 0) + 1
        return daily_hours, daily_points, daily_counts

    def _compute_average_turnaround_hours(self, records: List[PullRequest]) -> float:
        durations: List[float] = []
        for record in records:
            opened = getattr(record, "opened_at", None)
            merged = getattr(record, "merged_at", None)
            if opened and merged:
                try:
                    opened_dt = opened if isinstance(opened, datetime) else datetime.fromisoformat(str(opened))
                    merged_dt = merged if isinstance(merged, datetime) else datetime.fromisoformat(str(merged))
                except ValueError:
                    continue
                if merged_dt < opened_dt:
                    continue
                durations.append((merged_dt - opened_dt).total_seconds() / 3600.0)
        if not durations:
            return 0.0
        return round(sum(durations) / len(durations), 1)

    def _serialize_pr_detail(self, record: PullRequest) -> Dict[str, Any]:
        notes = self._parse_ai_notes(record)
        ts = self._resolve_activity_timestamp(record)
        prompts = getattr(record, "ai_prompts", None)
        if prompts is None and "prompts" in notes:
            prompts_candidate = notes["prompts"]
            if isinstance(prompts_candidate, list):
                prompts = [str(p) for p in prompts_candidate]
            elif isinstance(prompts_candidate, str):
                prompts = [prompts_candidate]
        prompts = prompts or []

        return {
            "pr_number": record.pr_number,
            "title": record.title,
            "status": getattr(record, "status", "unknown"),
            "activity_timestamp": ts.isoformat() if ts else None,
            "ai_summary": getattr(record, "ai_summary", None) or notes.get("summary"),
            "ai_prompts": prompts,
            "impact_score": round(self._extract_impact_score(record, notes), 2),
            "ai_estimated_hours": round(float(record.ai_estimated_hours or 0.0), 2),
            "url": getattr(record, "url", None),
            "repository_name": getattr(record, "repository_name", None),
            "review_comments": getattr(record, "review_comments", None),
        }

    def _compute_activity_score(self, total_prs: int, total_points: float, total_hours: float) -> float:
        score = (total_points * 1.5) + (total_prs * 2.0) + (total_hours * 1.0)
        return round(score, 2)

    def _calculate_day_off_dates(self, start_date: date, end_date: date, activity_dates: List[date]) -> List[date]:
        activity_set = set(activity_dates)
        cursor = start_date
        results: List[date] = []
        while cursor <= end_date:
            if cursor not in activity_set:
                results.append(cursor)
            cursor += timedelta(days=1)
        return results

    # ------------------------------------------------------------------
    # Public API used by routes
    # ------------------------------------------------------------------
    async def get_user_performance_summary(self, user_id: UUID, period_days: int = 7) -> Dict[str, Any]:
        user = await self.user_repo.get_user_by_id(user_id)
        if not user:
            logger.warning("User %s not found when building KPI summary", user_id)
            raise ResourceNotFoundError(resource_name="User", resource_id=str(user_id))

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=period_days)
        logger.info("Building PR performance summary for user %s over %s days", user_id, period_days)

        return await self._build_user_summary(user_id, start_date, end_date)

    async def get_user_performance_summary_range(
        self, user_id: UUID, start_dt: datetime, end_dt: datetime
    ) -> Dict[str, Any]:
        user = await self.user_repo.get_user_by_id(user_id)
        if not user:
            logger.warning("User %s not found when building KPI summary", user_id)
            raise ResourceNotFoundError(resource_name="User", resource_id=str(user_id))

        logger.info(
            "Building PR performance summary for user %s from %s to %s",
            user_id,
            start_dt.isoformat(),
            end_dt.isoformat(),
        )

        return await self._build_user_summary(user_id, start_dt, end_dt)

    async def _build_user_summary(self, user_id: UUID, start_dt: datetime, end_dt: datetime) -> Dict[str, Any]:
        daily_reports = await self.daily_report_repo.get_reports_by_user_and_date_range(user_id, start_dt, end_dt)
        total_eod_reported_hours = sum(dr.final_estimated_hours or 0.0 for dr in daily_reports)
        eod_report_details = [
            {
                "report_date": dr.report_date.strftime("%Y-%m-%d"),
                "reported_hours": dr.final_estimated_hours or 0.0,
                "ai_summary": dr.ai_analysis.summary if dr.ai_analysis else "N/A",
                "ai_estimated_hours": (
                    dr.ai_analysis.estimated_hours
                    if dr.ai_analysis and dr.ai_analysis.estimated_hours is not None
                    else 0.0
                ),
                "clarification_requests_count": len(dr.ai_analysis.clarification_requests) if dr.ai_analysis else 0,
            }
            for dr in daily_reports
        ]

        prs_in_period = await self.pull_request_repo.get_pull_requests_by_user_in_range(
            user_id, start_dt.date(), end_dt.date()
        )

        total_prs = len(prs_in_period)
        merged_prs = len(
            [pr for pr in prs_in_period if str(getattr(pr, "status", "")).lower() == "merged" or pr.merged_at]
        )
        total_hours = sum(float(pr.ai_estimated_hours or 0.0) for pr in prs_in_period)
        total_points = sum(self._extract_impact_score(pr, self._parse_ai_notes(pr)) for pr in prs_in_period)

        daily_hours, daily_points, daily_counts = self._collect_daily_rollups(prs_in_period)
        daily_hours_series = [{"date": day, "hours": round(value, 2)} for day, value in sorted(daily_hours.items())]
        daily_points_series = [{"date": day, "points": round(value, 2)} for day, value in sorted(daily_points.items())]
        daily_prs_series = [{"date": day, "count": count} for day, count in sorted(daily_counts.items())]

        efficiency_pph = round(total_points / total_hours, 2) if total_hours > 0 else 0.0
        try:
            period_agg = self._sum_points_hours_by_category(prs_in_period)
            baselines = await self._compute_personal_baselines(user_id, end_dt)
            normalized_pph, used_default, baseline_source = self._compute_normalized_efficiency(period_agg, baselines)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning("Failed to compute normalized efficiency for user %s: %s", user_id, exc, exc_info=True)
            normalized_pph = 0.0
            used_default = True
            baseline_source = "default"

        pr_details = [self._serialize_pr_detail(pr) for pr in prs_in_period]
        pr_details.sort(key=lambda item: item.get("activity_timestamp") or "", reverse=True)
        top_prs_by_impact = sorted(
            pr_details,
            key=lambda item: item.get("impact_score", 0.0),
            reverse=True,
        )[:5]

        average_turnaround = self._compute_average_turnaround_hours(prs_in_period)
        activity_dates = [
            self._resolve_activity_timestamp(pr).date() for pr in prs_in_period if self._resolve_activity_timestamp(pr)
        ]
        day_off_dates = self._calculate_day_off_dates(start_dt.date(), end_dt.date(), activity_dates)

        summary = {
            "user_id": str(user_id),
            "period_start_date": start_dt.date().isoformat(),
            "period_end_date": end_dt.date().isoformat(),
            "total_prs_in_period": total_prs,
            "merged_prs_in_period": merged_prs,
            "total_ai_estimated_pr_hours": round(total_hours, 2),
            "total_business_points": round(total_points, 2),
            "efficiency_points_per_hour": efficiency_pph,
            "normalized_efficiency_points_per_hour": normalized_pph,
            "efficiency_provisional": used_default,
            "efficiency_baseline_source": baseline_source,
            "activity_score": self._compute_activity_score(total_prs, total_points, total_hours),
            "average_pr_turnaround_hours": average_turnaround,
            "daily_hours_series": daily_hours_series,
            "daily_points_series": daily_points_series,
            "daily_prs_series": daily_prs_series,
            "pr_details": pr_details,
            "top_prs_by_impact": top_prs_by_impact,
            "day_off_dates": [d.isoformat() for d in day_off_dates],
            "total_eod_reported_hours": total_eod_reported_hours,
            "eod_report_details": eod_report_details,
        }

        return summary

    async def get_bulk_widget_summaries(
        self, start_date_dt: datetime, end_date_dt: datetime
    ) -> List[UserWidgetSummary]:
        try:
            relevant_users: List[User] = await self.user_repo.list_users_by_role(UserRole.EMPLOYEE)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error("Unable to fetch users for widget summaries: %s", exc, exc_info=True)
            return []

        if not relevant_users:
            return []

        user_ids = [user.id for user in relevant_users]
        pr_map = await self.pull_request_repo.get_pull_requests_for_users_in_range(
            user_ids, start_date_dt.date(), end_date_dt.date()
        )

        summaries: List[UserWidgetSummary] = []
        for user in relevant_users:
            prs = pr_map.get(user.id, []) or []
            if not prs:
                summaries.append(
                    UserWidgetSummary(
                        user_id=user.id,
                        name=user.name,
                        avatar_url=user.avatar_url,
                        total_prs=0,
                        merged_prs=0,
                        total_ai_estimated_pr_hours=0.0,
                        total_business_points=0.0,
                        efficiency_points_per_hour=0.0,
                        normalized_efficiency_points_per_hour=0.0,
                        efficiency_provisional=True,
                        efficiency_baseline_source="default",
                        activity_score=0.0,
                        day_off=True,
                    )
                )
                continue

            total_hours = 0.0
            total_points = 0.0
            merged_prs = 0
            latest_ts: Optional[datetime] = None
            latest_title: Optional[str] = None
            daily_hours: Dict[str, float] = {}
            daily_points: Dict[str, float] = {}
            daily_counts: Dict[str, int] = {}

            for pr in prs:
                hours = float(pr.ai_estimated_hours or 0.0)
                notes = self._parse_ai_notes(pr)
                points = self._extract_impact_score(pr, notes)
                ts = self._resolve_activity_timestamp(pr)
                if ts:
                    date_key = ts.date().strftime("%Y-%m-%d")
                    daily_hours[date_key] = daily_hours.get(date_key, 0.0) + hours
                    daily_points[date_key] = daily_points.get(date_key, 0.0) + points
                    daily_counts[date_key] = daily_counts.get(date_key, 0) + 1
                    if not latest_ts or ts > latest_ts:
                        latest_ts = ts
                        latest_title = pr.title
                total_hours += hours
                total_points += points
                if str(getattr(pr, "status", "")).lower() == "merged" or pr.merged_at:
                    merged_prs += 1

            efficiency_pph = round(total_points / total_hours, 2) if total_hours > 0 else 0.0
            try:
                period_agg = self._sum_points_hours_by_category(prs)
                baselines = await self._compute_personal_baselines(user.id, end_date_dt)
                normalized_pph, used_default, baseline_source = self._compute_normalized_efficiency(
                    period_agg, baselines
                )
            except Exception as exc:  # pragma: no cover
                logger.debug("Failed to compute normalized PPH for user %s: %s", user.id, exc)
                normalized_pph = 0.0
                used_default = True
                baseline_source = "default"

            summaries.append(
                UserWidgetSummary(
                    user_id=user.id,
                    name=user.name,
                    avatar_url=user.avatar_url,
                    total_prs=len(prs),
                    merged_prs=merged_prs,
                    total_ai_estimated_pr_hours=round(total_hours, 2),
                    total_business_points=round(total_points, 2),
                    efficiency_points_per_hour=efficiency_pph,
                    normalized_efficiency_points_per_hour=normalized_pph,
                    efficiency_provisional=used_default,
                    efficiency_baseline_source=baseline_source,
                    activity_score=self._compute_activity_score(len(prs), total_points, total_hours),
                    day_off=False,
                    daily_prs_series=[{"date": day, "count": count} for day, count in sorted(daily_counts.items())],
                    daily_hours_series=[
                        {"date": day, "hours": round(value, 2)} for day, value in sorted(daily_hours.items())
                    ],
                    daily_points_series=[
                        {"date": day, "points": round(value, 2)} for day, value in sorted(daily_points.items())
                    ],
                    latest_activity_timestamp=latest_ts.isoformat() if latest_ts else None,
                    latest_pr_title=latest_title,
                )
            )

        summaries.sort(key=lambda summary: summary.activity_score, reverse=True)
        logger.info("Generated %s widget summaries", len(summaries))
        return summaries
