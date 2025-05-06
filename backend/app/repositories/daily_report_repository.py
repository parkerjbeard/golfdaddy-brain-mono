from typing import List, Dict, Optional, Union
from uuid import UUID
from datetime import datetime, timezone
from supabase import Client
from app.config.supabase_client import get_supabase_client
from app.models.daily_report import DailyReport, DailyReportCreate, DailyReportUpdate, AiAnalysis, ClarificationRequest
import logging
import json
import asyncio

logger = logging.getLogger(__name__)

class DailyReportRepository:
    def __init__(self, client: Client = get_supabase_client()):
        self._client = client
        self._table_name = "daily_reports"

    def _db_to_model(self, db_data: Dict[str, Any]) -> DailyReport:
        """Converts database row (dict) to DailyReport Pydantic model."""
        if db_data.get('ai_analysis') and isinstance(db_data['ai_analysis'], str):
            try:
                ai_analysis_dict = json.loads(db_data['ai_analysis'])
                # Parse clarification requests within ai_analysis if they exist
                if 'clarification_requests' in ai_analysis_dict and isinstance(ai_analysis_dict['clarification_requests'], list):
                    parsed_reqs = []
                    for req_item in ai_analysis_dict['clarification_requests']:
                        if isinstance(req_item, dict):
                            try:
                                parsed_reqs.append(ClarificationRequest(**req_item))
                            except Exception as e_parse_req:
                                logger.warning(f"Could not parse clarification_request item {req_item}: {e_parse_req}")
                        else:
                             parsed_reqs.append(req_item) # If already model instance (unlikely from DB directly)
                    ai_analysis_dict['clarification_requests'] = parsed_reqs
                db_data['ai_analysis'] = AiAnalysis(**ai_analysis_dict)
            except json.JSONDecodeError as e_json:
                logger.error(f"Error decoding ai_analysis JSON from DB: {e_json} for report ID {db_data.get('id')}")
                db_data['ai_analysis'] = None # Set to None if parsing fails
        elif db_data.get('ai_analysis') and isinstance(db_data['ai_analysis'], dict):
             # If it's already a dict (e.g. from some direct Supabase responses), try to parse to model
            try:
                # Similar parsing logic for clarification_requests as above
                if 'clarification_requests' in db_data['ai_analysis'] and isinstance(db_data['ai_analysis']['clarification_requests'], list):
                    parsed_reqs = []
                    for req_item in db_data['ai_analysis']['clarification_requests']:
                        if isinstance(req_item, dict):
                            try:
                                parsed_reqs.append(ClarificationRequest(**req_item))
                            except Exception as e_parse_req:
                                logger.warning(f"Could not parse clarification_request item from dict: {req_item}: {e_parse_req}")
                        else:
                            parsed_reqs.append(req_item)
                    db_data['ai_analysis']['clarification_requests'] = parsed_reqs
                db_data['ai_analysis'] = AiAnalysis(**db_data['ai_analysis'])
            except Exception as e_dict_parse:
                logger.error(f"Error parsing ai_analysis dict to model: {e_dict_parse} for report ID {db_data.get('id')}")
                db_data['ai_analysis'] = None
        
        # Ensure linked_commit_ids is a list (it's text[] in DB)
        if 'linked_commit_ids' in db_data and db_data['linked_commit_ids'] is None:
            db_data['linked_commit_ids'] = []
            
        return DailyReport(**db_data)

    def _model_to_db_dict(self, report: Union[DailyReport, DailyReportCreate, DailyReportUpdate]) -> Dict[str, Any]:
        """Converts DailyReport Pydantic model to a dict suitable for Supabase, handling serializations."""
        db_dict = report.model_dump(exclude_unset=True) # exclude_unset for updates
        
        # Serialize AiAnalysis to JSON string if it's an AiAnalysis object
        if 'ai_analysis' in db_dict and isinstance(db_dict['ai_analysis'], AiAnalysis):
            ai_analysis_obj = db_dict['ai_analysis']
            # Convert ClarificationRequest objects within ai_analysis to dicts
            clar_req_dicts = []
            if ai_analysis_obj.clarification_requests:
                for req in ai_analysis_obj.clarification_requests:
                    if isinstance(req, ClarificationRequest):
                        clar_req_dicts.append(req.model_dump())
                    else: # Already a dict
                        clar_req_dicts.append(req)
            ai_analysis_data_for_json = ai_analysis_obj.model_dump()
            ai_analysis_data_for_json['clarification_requests'] = clar_req_dicts
            db_dict['ai_analysis'] = json.dumps(ai_analysis_data_for_json)
        elif 'ai_analysis' in db_dict and db_dict['ai_analysis'] is None and isinstance(report, DailyReportUpdate) and 'ai_analysis' in report.model_fields_set:
            db_dict['ai_analysis'] = None # Explicitly set to null if that's the intent
        elif 'ai_analysis' in db_dict and isinstance(db_dict['ai_analysis'], dict):
            # If it's already a dict (e.g. from AI service), just dump it to JSON string
            db_dict['ai_analysis'] = json.dumps(db_dict['ai_analysis'])

        for key in ['report_date', 'created_at', 'updated_at']:
            if key in db_dict and isinstance(db_dict[key], datetime):
                # Ensure datetime is timezone-aware before to_isoformat, or handle naive datetimes
                if db_dict[key].tzinfo is None:
                    db_dict[key] = db_dict[key].replace(tzinfo=timezone.utc).isoformat()
                else:
                    db_dict[key] = db_dict[key].isoformat()
        
        if 'id' in db_dict and db_dict['id'] is None:
            del db_dict['id'] # Let DB generate ID on create
        if 'user_id' in db_dict and isinstance(db_dict['user_id'], UUID):
            db_dict['user_id'] = str(db_dict['user_id'])
            
        return db_dict

    async def create_daily_report(self, report_create: DailyReportCreate) -> Optional[DailyReport]:
        report_dict = self._model_to_db_dict(report_create)
        # Ensure report_date is set for new reports if not provided by model_dump (though DailyReportCreate doesn't have it directly)
        # The DailyReport model sets default_factory for report_date, created_at, updated_at. DB also has defaults.
        # For create, we primarily rely on the Pydantic model defaults if not in report_create, then DB defaults.
        # report_dict['report_date'] = report_dict.get('report_date', datetime.now(timezone.utc).isoformat())
        # report_dict['created_at'] = report_dict.get('created_at', datetime.now(timezone.utc).isoformat())
        # report_dict['updated_at'] = report_dict.get('updated_at', datetime.now(timezone.utc).isoformat())
        if 'user_id' not in report_dict or not report_dict['user_id']:
             logger.error("Cannot create daily report without user_id")
             return None

        try:
            response = await asyncio.to_thread(
                self._client.table(self._table_name).insert(report_dict).execute
            )
            if response.data:
                logger.info(f"Successfully created daily report: {response.data[0]['id']}")
                return self._db_to_model(response.data[0])
            else:
                logger.error(f"Failed to create daily report: {response.error.message if response.error else 'Unknown error'}")
                return None
        except Exception as e:
            logger.exception(f"Exception creating daily report: {e}")
            return None

    async def get_daily_report_by_id(self, report_id: UUID) -> Optional[DailyReport]:
        try:
            response = await asyncio.to_thread(
                self._client.table(self._table_name).select("*").eq("id", str(report_id)).maybe_single().execute
            )
            if response.data:
                return self._db_to_model(response.data)
            return None
        except Exception as e:
            logger.exception(f"Exception getting daily report by ID {report_id}: {e}")
            return None

    async def get_daily_reports_by_user_id(self, user_id: UUID) -> List[DailyReport]:
        try:
            response = await asyncio.to_thread(
                self._client.table(self._table_name).select("*").eq("user_id", str(user_id)).order("report_date", desc=True).execute
            )
            if response.data:
                return [self._db_to_model(row) for row in response.data]
            return []
        except Exception as e:
            logger.exception(f"Exception getting daily reports for user {user_id}: {e}")
            return []
    
    async def get_daily_reports_by_user_and_date(
        self, user_id: UUID, report_date: datetime
    ) -> Optional[DailyReport]:
        report_date_str = report_date.strftime('%Y-%m-%d')
        try:
            response = await asyncio.to_thread(
                self._client.table(self._table_name)
                .select("*")
                .eq("user_id", str(user_id))
                .eq("report_date", report_date_str) # Querying by date part
                .maybe_single()
                .execute
            ) # Note: Supabase/PostgREST might need specific function for date part comparison on timestamp field like .eq("report_date::date", report_date_str)
              # For now, this assumes direct date string match works or report_date is stored as DATE in DB (which it is not, it's TIMESTAMPTZ)
              # More robust: .gte("report_date", report_date.replace(hour=0, minute=0, second=0, microsecond=0).isoformat())
              #              .lt("report_date", (report_date + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat())
            if response.data:
                return self._db_to_model(response.data)
            return None
        except Exception as e:
            logger.exception(f"Exception getting daily report for user {user_id} on date {report_date_str}: {e}")
            return None

    async def get_reports_by_user_and_date_range(
        self, user_id: UUID, start_date: datetime, end_date: datetime
    ) -> List[DailyReport]:
        start_date_iso = start_date.isoformat()
        end_date_iso = end_date.isoformat()
        try:
            response = await asyncio.to_thread(
                self._client.table(self._table_name)
                .select("*")
                .eq("user_id", str(user_id))
                .gte("report_date", start_date_iso)
                .lte("report_date", end_date_iso) # Inclusive of end_date
                .order("report_date", desc=True)
                .execute
            )
            if response.data:
                return [self._db_to_model(row) for row in response.data]
            return []
        except Exception as e:
            logger.exception(f"Exception getting reports for user {user_id} in range {start_date_iso} - {end_date_iso}: {e}")
            return []

    async def update_daily_report(self, report_id: UUID, report_update: DailyReportUpdate) -> Optional[DailyReport]:
        update_dict = self._model_to_db_dict(report_update)
        if not update_dict: # If only an ID was passed or something, nothing to update
            # Fetch current and return? Or error?
            # For now, assume update_dict will have fields if called correctly
            current_report = await self.get_daily_report_by_id(report_id)
            return current_report

        # Ensure updated_at is always set on update
        update_dict['updated_at'] = datetime.now(timezone.utc).isoformat()

        try:
            response = await asyncio.to_thread(
                self._client.table(self._table_name).update(update_dict).eq("id", str(report_id)).execute
            )
            if response.data:
                logger.info(f"Successfully updated daily report: {report_id}")
                return self._db_to_model(response.data[0])
            else:
                logger.error(f"Failed to update daily report {report_id}: {response.error.message if response.error else 'Unknown error or report not found'}")
                return None
        except Exception as e:
            logger.exception(f"Exception updating daily report {report_id}: {e}")
            return None

    async def delete_daily_report(self, report_id: UUID) -> bool:
        try:
            response = await asyncio.to_thread(
                self._client.table(self._table_name).delete().eq("id", str(report_id)).execute
            )
            # Delete often returns no data on success, check for error
            if response.error:
                logger.error(f"Failed to delete daily report {report_id}: {response.error.message}")
                return False
            # Consider if response.count > 0 check is needed/reliable for delete
            logger.info(f"Successfully initiated delete for daily report: {report_id}")
            return True
        except Exception as e:
            logger.exception(f"Exception deleting daily report {report_id}: {e}")
            return False

    async def get_all_daily_reports(self, limit: int = 100, offset: int = 0) -> List[DailyReport]:
        """Retrieves all daily reports with pagination (for admin/debugging)."""
        try:
            response = await asyncio.to_thread(
                 self._client.table(self._table_name).select("*").order("report_date", desc=True).range(offset, offset + limit - 1).execute
            )
            if response.data:
                return [self._db_to_model(row) for row in response.data]
            return []
        except Exception as e:
            logger.exception(f"Exception getting all daily reports: {e}")
            return [] 