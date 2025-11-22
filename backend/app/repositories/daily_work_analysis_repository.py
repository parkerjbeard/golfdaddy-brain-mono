import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from app.config.supabase_client import get_supabase_client
from app.core.exceptions import DatabaseError
from app.models.daily_work_analysis import DailyWorkAnalysis

logger = logging.getLogger(__name__)


class DailyWorkAnalysisRepository:
    """Supabase-backed repository for daily work analyses (no SQLAlchemy)."""

    def __init__(self):
        self._client = get_supabase_client()
        self._table = "daily_work_analyses"
        self._work_items_table = "work_items"
        self._dedup_table = "deduplication_results"

    def _handle_supabase_error(self, response: Any, context_message: str):
        if response and hasattr(response, "error") and response.error:
            logger.error(
                f"{context_message}: Supabase error code "
                f"{getattr(response.error, 'code', 'N/A')} - {response.error.message}",
                exc_info=True,
            )
            raise DatabaseError(f"{context_message}: {response.error.message}")

    def _iso(self, v: Any) -> Any:
        if isinstance(v, (datetime, date)):
            return v.isoformat()
        if isinstance(v, UUID):
            return str(v)
        if isinstance(v, Decimal):
            return str(v)
        return v

    def _serialize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {k: self._iso(v) for k, v in data.items()}

    async def create(self, analysis_data: Dict[str, Any]) -> DailyWorkAnalysis:
        try:
            data_dict = self._serialize(analysis_data)
            work_items = data_dict.pop("work_items", [])
            dedup_results = data_dict.pop("deduplication_results", [])

            resp = self._client.table(self._table).insert(data_dict).execute()
            self._handle_supabase_error(resp, "Failed to create daily work analysis")
            if not resp.data:
                raise DatabaseError("Failed to create daily work analysis: No data returned")

            analysis_id = resp.data[0]["id"]

            if work_items:
                for wi in work_items:
                    wi["daily_analysis_id"] = analysis_id
                wi_resp = self._client.table(self._work_items_table).insert(work_items).execute()
                self._handle_supabase_error(wi_resp, "Failed to create work items")

            if dedup_results:
                for dr in dedup_results:
                    dr["daily_analysis_id"] = analysis_id
                dr_resp = self._client.table(self._dedup_table).insert(dedup_results).execute()
                self._handle_supabase_error(dr_resp, "Failed to create deduplication results")

            return await self.get_by_id(UUID(analysis_id))
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating daily work analysis: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error creating daily work analysis: {str(e)}")

    async def get_by_id(self, analysis_id: UUID) -> Optional[DailyWorkAnalysis]:
        try:
            resp = self._client.table(self._table).select("*").eq("id", str(analysis_id)).maybe_single().execute()
            if not resp.data:
                return None

            analysis_data = dict(resp.data)

            wi_resp = (
                self._client.table(self._work_items_table)
                .select("*")
                .eq("daily_analysis_id", str(analysis_id))
                .execute()
            )
            if wi_resp.data:
                analysis_data["work_items"] = wi_resp.data

            dr_resp = (
                self._client.table(self._dedup_table).select("*").eq("daily_analysis_id", str(analysis_id)).execute()
            )
            if dr_resp.data:
                analysis_data["deduplication_results"] = dr_resp.data

            return DailyWorkAnalysis(**analysis_data)
        except Exception as e:
            logger.error(f"Error fetching daily work analysis {analysis_id}: {e}", exc_info=True)
            raise DatabaseError(f"Error fetching daily work analysis: {str(e)}")

    async def get_by_user_and_date(self, user_id: UUID, analysis_date: date) -> Optional[DailyWorkAnalysis]:
        try:
            resp = (
                self._client.table(self._table)
                .select("*")
                .eq("user_id", str(user_id))
                .eq("analysis_date", analysis_date.isoformat())
                .maybe_single()
                .execute()
            )
            if resp.data:
                return DailyWorkAnalysis(**resp.data)
            return None
        except Exception as e:
            logger.error(f"Error fetching daily work analysis for user {user_id}: {e}", exc_info=True)
            raise DatabaseError(f"Error fetching daily work analysis: {str(e)}")
