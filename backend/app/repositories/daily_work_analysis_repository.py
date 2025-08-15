"""
Daily Work Analysis Repository

This module provides data access operations for the daily work analysis system,
including CRUD operations, aggregation methods, and support for work items and
deduplication results.
"""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from postgrest import APIResponse as PostgrestAPIResponse
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.supabase_client import get_supabase_client
from app.core.exceptions import DatabaseError
from app.models.daily_work_analysis import DailyWorkAnalysis, DeduplicationResult, WorkItem

logger = logging.getLogger(__name__)


class DailyWorkAnalysisRepository:
    """Repository for daily work analysis operations"""

    def __init__(self):
        self._client = get_supabase_client()
        self._table = "daily_work_analyses"
        self._work_items_table = "work_items"
        self._dedup_table = "deduplication_results"

    def _handle_supabase_error(self, response: PostgrestAPIResponse, context_message: str):
        """Helper to log and raise DatabaseError from Supabase errors."""
        if response and hasattr(response, "error") and response.error:
            logger.error(
                f"{context_message}: Supabase error code "
                f"{response.error.code if hasattr(response.error, 'code') else 'N/A'} - "
                f"{response.error.message}",
                exc_info=True,
            )
            raise DatabaseError(f"{context_message}: {response.error.message}")

    def _serialize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize data for Supabase, converting special types"""
        serialized = {}
        for key, value in data.items():
            if isinstance(value, (Decimal, float)):
                serialized[key] = str(value) if isinstance(value, Decimal) else value
            elif isinstance(value, date):
                serialized[key] = value.isoformat()
            elif isinstance(value, datetime):
                serialized[key] = value.isoformat()
            elif isinstance(value, UUID):
                serialized[key] = str(value)
            else:
                serialized[key] = value
        return serialized

    async def create(self, analysis_data: Dict[str, Any]) -> DailyWorkAnalysis:
        """Create a new daily work analysis record"""
        try:
            logger.info(
                f"Creating daily work analysis for user {analysis_data.get('user_id')} "
                f"on {analysis_data.get('analysis_date')}"
            )

            # Serialize the data
            data_dict = self._serialize_data(analysis_data)

            # Extract work items and deduplication results if present
            work_items = data_dict.pop("work_items", [])
            dedup_results = data_dict.pop("deduplication_results", [])

            # Create the main analysis record
            response: PostgrestAPIResponse = self._client.table(self._table).insert(data_dict).execute()

            self._handle_supabase_error(response, "Failed to create daily work analysis")

            if not response.data:
                raise DatabaseError("Failed to create daily work analysis: No data returned")

            analysis_id = response.data[0]["id"]

            # Create work items if provided
            if work_items:
                await self._create_work_items(analysis_id, work_items)

            # Create deduplication results if provided
            if dedup_results:
                await self._create_deduplication_results(analysis_id, dedup_results)

            logger.info(f"✓ Created daily work analysis: {analysis_id}")

            # Fetch and return the complete analysis
            return await self.get_by_id(UUID(analysis_id))

        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating daily work analysis: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error creating daily work analysis: {str(e)}")

    async def _create_work_items(self, analysis_id: str, work_items: List[Dict[str, Any]]):
        """Create work items for an analysis"""
        try:
            if not work_items:
                return

            # Add the analysis ID to each work item
            items_data = []
            for item in work_items:
                item_data = self._serialize_data(item)
                item_data["daily_analysis_id"] = analysis_id
                items_data.append(item_data)

            response = self._client.table(self._work_items_table).insert(items_data).execute()
            self._handle_supabase_error(response, "Failed to create work items")

            logger.info(f"Created {len(items_data)} work items for analysis {analysis_id}")

        except Exception as e:
            logger.error(f"Error creating work items: {e}", exc_info=True)
            raise DatabaseError(f"Error creating work items: {str(e)}")

    async def _create_deduplication_results(self, analysis_id: str, dedup_results: List[Dict[str, Any]]):
        """Create deduplication results for an analysis"""
        try:
            if not dedup_results:
                return

            # Add the analysis ID to each result
            results_data = []
            for result in dedup_results:
                result_data = self._serialize_data(result)
                result_data["daily_analysis_id"] = analysis_id
                results_data.append(result_data)

            response = self._client.table(self._dedup_table).insert(results_data).execute()
            self._handle_supabase_error(response, "Failed to create deduplication results")

            logger.info(f"Created {len(results_data)} deduplication results for analysis {analysis_id}")

        except Exception as e:
            logger.error(f"Error creating deduplication results: {e}", exc_info=True)
            raise DatabaseError(f"Error creating deduplication results: {str(e)}")

    async def get_by_id(self, analysis_id: UUID) -> Optional[DailyWorkAnalysis]:
        """Get a daily work analysis by ID with related data"""
        try:
            logger.info(f"Fetching daily work analysis: {analysis_id}")

            # Get the main analysis record
            response: PostgrestAPIResponse = (
                self._client.table(self._table).select("*").eq("id", str(analysis_id)).maybe_single().execute()
            )

            if not response.data:
                logger.info(f"No daily work analysis found with ID: {analysis_id}")
                return None

            analysis_data = response.data

            # Get work items
            work_items_response = (
                self._client.table(self._work_items_table)
                .select("*")
                .eq("daily_analysis_id", str(analysis_id))
                .execute()
            )

            if work_items_response.data:
                analysis_data["work_items"] = work_items_response.data

            # Get deduplication results
            dedup_response = (
                self._client.table(self._dedup_table).select("*").eq("daily_analysis_id", str(analysis_id)).execute()
            )

            if dedup_response.data:
                analysis_data["deduplication_results"] = dedup_response.data

            logger.info(f"✓ Found daily work analysis: {analysis_id}")
            return DailyWorkAnalysis(**analysis_data)

        except Exception as e:
            logger.error(f"Error fetching daily work analysis {analysis_id}: {e}", exc_info=True)
            raise DatabaseError(f"Error fetching daily work analysis: {str(e)}")

    async def get_by_user_and_date(self, user_id: UUID, analysis_date: date) -> Optional[DailyWorkAnalysis]:
        """Get daily work analysis for a specific user and date"""
        try:
            logger.info(f"Fetching daily work analysis for user {user_id} on {analysis_date}")

            response: PostgrestAPIResponse = (
                self._client.table(self._table)
                .select("*")
                .eq("user_id", str(user_id))
                .eq("analysis_date", analysis_date.isoformat())
                .maybe_single()
                .execute()
            )

            if not response.data:
                logger.info(f"No daily work analysis found for user {user_id} on {analysis_date}")
                return None

            # Get the full analysis with related data
            return await self.get_by_id(UUID(response.data["id"]))

        except Exception as e:
            logger.error(f"Error fetching daily work analysis: {e}", exc_info=True)
            raise DatabaseError(f"Error fetching daily work analysis: {str(e)}")

    async def get_analyses_for_date_range(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> List[DailyWorkAnalysis]:
        """Get all daily work analyses for a user within a date range"""
        try:
            logger.info(f"Fetching daily work analyses for user {user_id} " f"from {start_date} to {end_date}")

            response: PostgrestAPIResponse = (
                self._client.table(self._table)
                .select("*")
                .eq("user_id", str(user_id))
                .gte("analysis_date", start_date.isoformat())
                .lte("analysis_date", end_date.isoformat())
                .order("analysis_date", desc=True)
                .execute()
            )

            self._handle_supabase_error(response, f"Error fetching analyses for user {user_id}")

            if not response.data:
                logger.info("No daily work analyses found in date range")
                return []

            # Get full analyses with related data
            analyses = []
            for analysis_data in response.data:
                full_analysis = await self.get_by_id(UUID(analysis_data["id"]))
                if full_analysis:
                    analyses.append(full_analysis)

            logger.info(f"✓ Found {len(analyses)} daily work analyses")
            return analyses

        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching daily work analyses: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error fetching daily work analyses: {str(e)}")

    async def get_weekly_aggregate(self, user_id: UUID, week_start: date) -> Dict[str, Any]:
        """Get aggregated weekly statistics for a user"""
        try:
            week_end = week_start + timedelta(days=6)
            logger.info(f"Fetching weekly aggregate for user {user_id} " f"from {week_start} to {week_end}")

            # Get all analyses for the week
            analyses = await self.get_analyses_for_date_range(user_id, week_start, week_end)

            # Calculate aggregates
            aggregate = {
                "user_id": str(user_id),
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "total_days_worked": len(analyses),
                "total_work_items": sum(a.total_work_items or 0 for a in analyses),
                "total_commits": sum(a.total_commits or 0 for a in analyses),
                "total_tickets": sum(a.total_tickets or 0 for a in analyses),
                "total_prs": sum(a.total_prs or 0 for a in analyses),
                "total_loc_added": sum(a.total_loc_added or 0 for a in analyses),
                "total_loc_removed": sum(a.total_loc_removed or 0 for a in analyses),
                "total_files_changed": sum(a.total_files_changed or 0 for a in analyses),
                "total_estimated_hours": sum(a.total_estimated_hours or 0.0 for a in analyses),
                "daily_breakdowns": [
                    {
                        "date": a.analysis_date.isoformat(),
                        "work_items": a.total_work_items,
                        "estimated_hours": a.total_estimated_hours,
                    }
                    for a in sorted(analyses, key=lambda x: x.analysis_date)
                ],
            }

            logger.info(f"✓ Generated weekly aggregate for user {user_id}")
            return aggregate

        except Exception as e:
            logger.error(f"Error generating weekly aggregate: {e}", exc_info=True)
            raise DatabaseError(f"Error generating weekly aggregate: {str(e)}")

    async def get_monthly_aggregate(self, user_id: UUID, year: int, month: int) -> Dict[str, Any]:
        """Get aggregated monthly statistics for a user"""
        try:
            # Calculate month boundaries
            month_start = date(year, month, 1)
            if month == 12:
                month_end = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = date(year, month + 1, 1) - timedelta(days=1)

            logger.info(f"Fetching monthly aggregate for user {user_id} " f"for {year}-{month:02d}")

            # Get all analyses for the month
            analyses = await self.get_analyses_for_date_range(user_id, month_start, month_end)

            # Calculate aggregates
            aggregate = {
                "user_id": str(user_id),
                "year": year,
                "month": month,
                "month_start": month_start.isoformat(),
                "month_end": month_end.isoformat(),
                "total_days_worked": len(analyses),
                "total_work_items": sum(a.total_work_items or 0 for a in analyses),
                "total_commits": sum(a.total_commits or 0 for a in analyses),
                "total_tickets": sum(a.total_tickets or 0 for a in analyses),
                "total_prs": sum(a.total_prs or 0 for a in analyses),
                "total_loc_added": sum(a.total_loc_added or 0 for a in analyses),
                "total_loc_removed": sum(a.total_loc_removed or 0 for a in analyses),
                "total_files_changed": sum(a.total_files_changed or 0 for a in analyses),
                "total_estimated_hours": sum(a.total_estimated_hours or 0.0 for a in analyses),
                "weekly_breakdowns": self._calculate_weekly_breakdowns(analyses),
                "data_sources": self._aggregate_data_sources(analyses),
            }

            logger.info(f"✓ Generated monthly aggregate for user {user_id}")
            return aggregate

        except Exception as e:
            logger.error(f"Error generating monthly aggregate: {e}", exc_info=True)
            raise DatabaseError(f"Error generating monthly aggregate: {str(e)}")

    def _calculate_weekly_breakdowns(self, analyses: List[DailyWorkAnalysis]) -> List[Dict[str, Any]]:
        """Calculate weekly breakdowns from daily analyses"""
        weekly_data = {}

        for analysis in analyses:
            # Get the Monday of the week for this date
            days_since_monday = analysis.analysis_date.weekday()
            week_start = analysis.analysis_date - timedelta(days=days_since_monday)
            week_key = week_start.isoformat()

            if week_key not in weekly_data:
                weekly_data[week_key] = {
                    "week_start": week_start.isoformat(),
                    "total_work_items": 0,
                    "total_estimated_hours": 0.0,
                    "days_worked": 0,
                }

            weekly_data[week_key]["total_work_items"] += analysis.total_work_items or 0
            weekly_data[week_key]["total_estimated_hours"] += analysis.total_estimated_hours or 0.0
            weekly_data[week_key]["days_worked"] += 1

        return list(weekly_data.values())

    def _aggregate_data_sources(self, analyses: List[DailyWorkAnalysis]) -> List[str]:
        """Aggregate unique data sources from analyses"""
        sources = set()
        for analysis in analyses:
            if analysis.data_sources:
                sources.update(analysis.data_sources)
        return sorted(list(sources))

    async def update(self, analysis_id: UUID, update_data: Dict[str, Any]) -> Optional[DailyWorkAnalysis]:
        """Update an existing daily work analysis"""
        try:
            logger.info(f"Updating daily work analysis: {analysis_id}")

            # Serialize the update data
            data_dict = self._serialize_data(update_data)

            # Extract work items and deduplication results if present
            work_items = data_dict.pop("work_items", None)
            dedup_results = data_dict.pop("deduplication_results", None)

            # Update the main record if there are fields to update
            if data_dict:
                # Add updated_at timestamp
                data_dict["updated_at"] = datetime.utcnow().isoformat()

                response: PostgrestAPIResponse = (
                    self._client.table(self._table).update(data_dict).eq("id", str(analysis_id)).execute()
                )

                self._handle_supabase_error(response, f"Failed to update daily work analysis {analysis_id}")

            # Update work items if provided
            if work_items is not None:
                await self._update_work_items(str(analysis_id), work_items)

            # Update deduplication results if provided
            if dedup_results is not None:
                await self._update_deduplication_results(str(analysis_id), dedup_results)

            logger.info(f"✓ Updated daily work analysis: {analysis_id}")

            # Return the updated analysis
            return await self.get_by_id(analysis_id)

        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating daily work analysis: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error updating daily work analysis: {str(e)}")

    async def _update_work_items(self, analysis_id: str, work_items: List[Dict[str, Any]]):
        """Update work items for an analysis (replace all)"""
        try:
            # Delete existing work items
            delete_response = (
                self._client.table(self._work_items_table).delete().eq("daily_analysis_id", analysis_id).execute()
            )

            self._handle_supabase_error(delete_response, "Failed to delete existing work items")

            # Create new work items
            if work_items:
                await self._create_work_items(analysis_id, work_items)

        except Exception as e:
            logger.error(f"Error updating work items: {e}", exc_info=True)
            raise DatabaseError(f"Error updating work items: {str(e)}")

    async def _update_deduplication_results(self, analysis_id: str, dedup_results: List[Dict[str, Any]]):
        """Update deduplication results for an analysis (replace all)"""
        try:
            # Delete existing deduplication results
            delete_response = (
                self._client.table(self._dedup_table).delete().eq("daily_analysis_id", analysis_id).execute()
            )

            self._handle_supabase_error(delete_response, "Failed to delete existing deduplication results")

            # Create new deduplication results
            if dedup_results:
                await self._create_deduplication_results(analysis_id, dedup_results)

        except Exception as e:
            logger.error(f"Error updating deduplication results: {e}", exc_info=True)
            raise DatabaseError(f"Error updating deduplication results: {str(e)}")

    async def delete(self, analysis_id: UUID) -> bool:
        """Delete a daily work analysis and all related data"""
        try:
            logger.info(f"Deleting daily work analysis: {analysis_id}")

            # Delete work items first (due to foreign key constraint)
            work_items_response = (
                self._client.table(self._work_items_table).delete().eq("daily_analysis_id", str(analysis_id)).execute()
            )

            self._handle_supabase_error(work_items_response, "Failed to delete work items")

            # Delete deduplication results
            dedup_response = (
                self._client.table(self._dedup_table).delete().eq("daily_analysis_id", str(analysis_id)).execute()
            )

            self._handle_supabase_error(dedup_response, "Failed to delete deduplication results")

            # Delete the main analysis record
            response: PostgrestAPIResponse = (
                self._client.table(self._table).delete().eq("id", str(analysis_id)).execute()
            )

            self._handle_supabase_error(response, f"Failed to delete daily work analysis {analysis_id}")

            logger.info(f"✓ Deleted daily work analysis: {analysis_id}")
            return True

        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting daily work analysis: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error deleting daily work analysis: {str(e)}")

    async def get_pending_analyses(self, limit: int = 10) -> List[DailyWorkAnalysis]:
        """Get analyses that are pending processing"""
        try:
            logger.info(f"Fetching up to {limit} pending analyses")

            response: PostgrestAPIResponse = (
                self._client.table(self._table)
                .select("*")
                .eq("processing_status", "pending")
                .order("created_at", desc=False)
                .limit(limit)
                .execute()
            )

            self._handle_supabase_error(response, "Error fetching pending analyses")

            if not response.data:
                return []

            # Get full analyses with related data
            analyses = []
            for analysis_data in response.data:
                full_analysis = await self.get_by_id(UUID(analysis_data["id"]))
                if full_analysis:
                    analyses.append(full_analysis)

            logger.info(f"✓ Found {len(analyses)} pending analyses")
            return analyses

        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Error fetching pending analyses: {e}", exc_info=True)
            raise DatabaseError(f"Error fetching pending analyses: {str(e)}")

    async def update_processing_status(self, analysis_id: UUID, status: str, error: Optional[str] = None) -> bool:
        """Update the processing status of an analysis"""
        try:
            logger.info(f"Updating processing status for {analysis_id} to {status}")

            update_data = {"processing_status": status, "last_processed_at": datetime.utcnow().isoformat()}

            if error:
                update_data["processing_error"] = error
            elif status == "completed":
                # Clear any previous error on successful completion
                update_data["processing_error"] = None

            response: PostgrestAPIResponse = (
                self._client.table(self._table).update(update_data).eq("id", str(analysis_id)).execute()
            )

            self._handle_supabase_error(response, f"Failed to update processing status for {analysis_id}")

            logger.info(f"✓ Updated processing status for {analysis_id}")
            return True

        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Error updating processing status: {e}", exc_info=True)
            raise DatabaseError(f"Error updating processing status: {str(e)}")
