import asyncio
import logging
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from postgrest import APIResponse as PostgrestResponse
from supabase import Client

from app.config.supabase_client import get_supabase_client_safe
from app.core.exceptions import DatabaseError
from app.models.pull_request import PullRequest

logger = logging.getLogger(__name__)


class PullRequestRepository:
    """Repository wrapper for interacting with pull_requests stored in Supabase."""

    def __init__(self, client: Optional[Client] = None):
        self._client = client or get_supabase_client_safe()
        self._table = "pull_requests"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _handle_supabase_error(self, response: Optional[PostgrestResponse], context_message: str) -> None:
        if not response:
            return
        err = getattr(response, "error", None)
        if err:
            logger.error(
                "%s: Supabase error code %s - %s",
                context_message,
                getattr(err, "code", "N/A"),
                getattr(err, "message", str(err)),
                exc_info=True,
            )
            raise DatabaseError(f"{context_message}: {getattr(err, 'message', str(err))}")

    def _normalize_hours(self, raw_value: Optional[float]) -> Optional[Decimal]:
        if raw_value is None:
            return None
        try:
            decimal_val = Decimal(str(raw_value))
            return decimal_val.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        except Exception as exc:
            logger.warning("Failed to normalize ai_estimated_hours value %s: %s", raw_value, exc)
            return None

    def _infer_activity_timestamp(self, payload: Dict[str, Any]) -> None:
        if payload.get("activity_timestamp"):
            return
        for candidate_key in ("merged_at", "closed_at", "opened_at"):
            candidate = payload.get(candidate_key)
            if candidate:
                payload["activity_timestamp"] = candidate
                return

    def _date_bounds(self, start_date: date, end_date: date) -> Dict[str, str]:
        start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        return {
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
        }

    def _materialize_pull_requests(self, records: List[Dict[str, Any]]) -> List[PullRequest]:
        prs: List[PullRequest] = []
        for record in records:
            if record.get("ai_estimated_hours") is not None:
                record["ai_estimated_hours"] = self._normalize_hours(record["ai_estimated_hours"])
            self._infer_activity_timestamp(record)
            try:
                prs.append(PullRequest(**record))
            except Exception as exc:
                logger.warning("Skipping pull request record due to validation error: %s", exc, exc_info=True)
        return prs

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def get_pull_requests_by_user_in_range(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> List[PullRequest]:
        bounds = self._date_bounds(start_date, end_date)
        try:
            response: PostgrestResponse = await asyncio.to_thread(
                self._client.table(self._table)
                .select("*")
                .eq("author_id", str(user_id))
                .gte("activity_timestamp", bounds["start"])
                .lte("activity_timestamp", bounds["end"])
                .order("activity_timestamp", desc=False)
                .execute
            )
            self._handle_supabase_error(response, "Failed to fetch pull requests for user")
            if response and response.data:
                return self._materialize_pull_requests(list(response.data))
            return []
        except DatabaseError:
            raise
        except Exception as exc:
            logger.error("Unexpected error fetching pull requests for %s: %s", user_id, exc, exc_info=True)
            raise DatabaseError(f"Unexpected error fetching pull requests: {exc}")

    async def get_pull_requests_for_users_in_range(
        self, user_ids: List[UUID], start_date: date, end_date: date
    ) -> Dict[UUID, List[PullRequest]]:
        if not user_ids:
            return {}
        bounds = self._date_bounds(start_date, end_date)
        try:
            response: PostgrestResponse = await asyncio.to_thread(
                self._client.table(self._table)
                .select("*")
                .in_("author_id", [str(uid) for uid in user_ids])
                .gte("activity_timestamp", bounds["start"])
                .lte("activity_timestamp", bounds["end"])
                .order("activity_timestamp", desc=False)
                .execute
            )
            self._handle_supabase_error(response, "Failed to fetch pull requests for users")
            grouped: Dict[UUID, List[PullRequest]] = {uid: [] for uid in user_ids}
            if response and response.data:
                for record in response.data:
                    author_id = record.get("author_id")
                    if not author_id:
                        continue
                    try:
                        author_uuid = UUID(author_id)
                    except Exception:
                        logger.warning("Invalid author_id on pull request record: %s", author_id)
                        continue
                    if author_uuid not in grouped:
                        grouped[author_uuid] = []
                    grouped[author_uuid].extend(self._materialize_pull_requests([record]))
            return grouped
        except DatabaseError:
            raise
        except Exception as exc:
            logger.error("Unexpected error fetching pull requests for users: %s", exc, exc_info=True)
            raise DatabaseError(f"Unexpected error fetching pull requests for users: {exc}")

    async def save_pull_request(self, pull_request: PullRequest) -> PullRequest:
        payload = pull_request.model_dump(exclude_unset=True, exclude_none=True)
        # Ensure UUIDs are strings for Supabase
        for key, value in list(payload.items()):
            if isinstance(value, UUID):
                payload[key] = str(value)
            elif isinstance(value, Decimal):
                payload[key] = str(value)
        if not payload.get("activity_timestamp"):
            self._infer_activity_timestamp(payload)
        if not payload.get("repository_name"):
            payload["repository_name"] = pull_request.repository_name or "unknown"
        try:
            response: PostgrestResponse = await asyncio.to_thread(
                self._client.table(self._table).upsert(payload, on_conflict="repository_name,pr_number").execute
            )
            self._handle_supabase_error(response, "Failed to upsert pull request")
            if response and response.data:
                materialized = self._materialize_pull_requests(list(response.data))
                return materialized[0]
            raise DatabaseError("Upsert pull request returned no data")
        except DatabaseError:
            raise
        except Exception as exc:
            logger.error("Unexpected error saving pull request %s: %s", pull_request.pr_number, exc, exc_info=True)
            raise DatabaseError(f"Unexpected error saving pull request: {exc}")
