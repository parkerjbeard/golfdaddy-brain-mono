import logging
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from postgrest import APIResponse as PostgrestResponse

from app.config.supabase_client import get_supabase_client
from app.core.exceptions import DatabaseError
from app.models.daily_commit_analysis import DailyCommitAnalysis, DailyCommitAnalysisCreate, DailyCommitAnalysisUpdate

logger = logging.getLogger(__name__)


class DailyCommitAnalysisRepository:
    """Repository for daily commit analysis operations"""

    def __init__(self):
        self._client = get_supabase_client()
        self._table = "daily_commit_analysis"

    def _handle_supabase_error(self, response: PostgrestResponse, context_message: str):
        """Helper to log and raise DatabaseError from Supabase errors."""
        if response and hasattr(response, "error") and response.error:
            logger.error(
                f"{context_message}: Supabase error code {response.error.code if hasattr(response.error, 'code') else 'N/A'} - {response.error.message}",
                exc_info=True,
            )
            raise DatabaseError(f"{context_message}: {response.error.message}")

    async def create(self, analysis_data: DailyCommitAnalysisCreate) -> DailyCommitAnalysis:
        """Create a new daily commit analysis record"""
        try:
            logger.info(f"Creating daily analysis for user {analysis_data.user_id} on {analysis_data.analysis_date}")

            data_dict = analysis_data.model_dump(exclude_unset=True, exclude_none=True)

            # Convert Decimal to string for Supabase
            if "total_estimated_hours" in data_dict:
                data_dict["total_estimated_hours"] = str(data_dict["total_estimated_hours"])

            # Convert date to ISO format string
            if "analysis_date" in data_dict:
                data_dict["analysis_date"] = data_dict["analysis_date"].isoformat()

            response: PostgrestResponse = self._client.table(self._table).insert(data_dict).execute()

            self._handle_supabase_error(response, "Failed to create daily commit analysis")

            if response.data:
                logger.info(f"✓ Created daily analysis: {response.data[0]['id']}")
                return DailyCommitAnalysis(**response.data[0])
            else:
                raise DatabaseError("Failed to create daily commit analysis: No data returned")

        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating daily analysis: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error creating daily analysis: {str(e)}")

    async def get_by_id(self, analysis_id: UUID) -> Optional[DailyCommitAnalysis]:
        """Get a daily commit analysis by ID"""
        try:
            logger.info(f"Fetching daily analysis: {analysis_id}")

            response: PostgrestResponse = (
                self._client.table(self._table).select("*").eq("id", str(analysis_id)).maybe_single().execute()
            )

            if response.data:
                logger.info(f"✓ Found daily analysis: {analysis_id}")
                return DailyCommitAnalysis(**response.data)
            else:
                logger.info(f"No daily analysis found with ID: {analysis_id}")
                return None

        except Exception as e:
            logger.error(f"Error fetching daily analysis {analysis_id}: {e}", exc_info=True)
            raise DatabaseError(f"Error fetching daily analysis: {str(e)}")

    async def get_by_user_and_date(self, user_id: UUID, analysis_date: date) -> Optional[DailyCommitAnalysis]:
        """Get daily analysis for a specific user and date"""
        try:
            logger.info(f"Fetching daily analysis for user {user_id} on {analysis_date}")

            response: PostgrestResponse = (
                self._client.table(self._table)
                .select("*")
                .eq("user_id", str(user_id))
                .eq("analysis_date", analysis_date.isoformat())
                .maybe_single()
                .execute()
            )

            if response.data:
                logger.info(f"✓ Found daily analysis for user {user_id} on {analysis_date}")
                return DailyCommitAnalysis(**response.data)
            else:
                logger.info(f"No daily analysis found for user {user_id} on {analysis_date}")
                return None

        except Exception as e:
            logger.error(f"Error fetching daily analysis: {e}", exc_info=True)
            raise DatabaseError(f"Error fetching daily analysis: {str(e)}")

    async def get_user_analyses_in_range(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> List[DailyCommitAnalysis]:
        """Get all daily analyses for a user within a date range"""
        try:
            logger.info(f"Fetching daily analyses for user {user_id} from {start_date} to {end_date}")

            response: PostgrestResponse = (
                self._client.table(self._table)
                .select("*")
                .eq("user_id", str(user_id))
                .gte("analysis_date", start_date.isoformat())
                .lte("analysis_date", end_date.isoformat())
                .order("analysis_date", desc=True)
                .execute()
            )

            self._handle_supabase_error(response, f"Error fetching analyses for user {user_id}")

            if response.data:
                logger.info(f"✓ Found {len(response.data)} daily analyses")
                return [DailyCommitAnalysis(**item) for item in response.data]
            else:
                logger.info("No daily analyses found in date range")
                return []

        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching daily analyses: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error fetching daily analyses: {str(e)}")

    async def get_users_without_analysis(self, analysis_date: date) -> List[UUID]:
        """Get list of users who have commits but no analysis for a given date"""
        try:
            logger.info(f"Finding users without analysis for {analysis_date}")

            # Query to find users with commits on the date but no analysis
            query = f"""
            SELECT DISTINCT c.author_id
            FROM commits c
            LEFT JOIN daily_commit_analysis dca 
                ON c.author_id = dca.user_id 
                AND dca.analysis_date = '{analysis_date.isoformat()}'
            WHERE DATE(c.commit_timestamp) = '{analysis_date.isoformat()}'
                AND dca.id IS NULL
                AND c.author_id IS NOT NULL
            """

            # Execute raw SQL query via RPC if available, otherwise use a workaround
            # For now, we'll use a different approach with existing Supabase client

            # Get all commits for the date
            commits_response = (
                self._client.table("commits")
                .select("author_id")
                .gte("commit_timestamp", f"{analysis_date.isoformat()}T00:00:00")
                .lt("commit_timestamp", f"{analysis_date.isoformat()}T23:59:59")
                .execute()
            )

            if not commits_response.data:
                return []

            # Get unique author IDs from commits
            author_ids = list(set(commit["author_id"] for commit in commits_response.data if commit.get("author_id")))

            if not author_ids:
                return []

            # Get existing analyses for these users on this date
            analyses_response = (
                self._client.table(self._table)
                .select("user_id")
                .eq("analysis_date", analysis_date.isoformat())
                .in_("user_id", author_ids)
                .execute()
            )

            analyzed_user_ids = set(analysis["user_id"] for analysis in (analyses_response.data or []))

            # Return users who have commits but no analysis
            unanalyzed_users = [UUID(user_id) for user_id in author_ids if user_id not in analyzed_user_ids]

            logger.info(f"✓ Found {len(unanalyzed_users)} users without analysis")
            return unanalyzed_users

        except Exception as e:
            logger.error(f"Error finding users without analysis: {e}", exc_info=True)
            raise DatabaseError(f"Error finding users without analysis: {str(e)}")

    async def update(self, analysis_id: UUID, update_data: DailyCommitAnalysisUpdate) -> Optional[DailyCommitAnalysis]:
        """Update an existing daily commit analysis"""
        try:
            logger.info(f"Updating daily analysis: {analysis_id}")

            data_dict = update_data.model_dump(exclude_unset=True, exclude_none=True)

            if not data_dict:
                logger.warning("No fields to update")
                return await self.get_by_id(analysis_id)

            # Convert Decimal to string
            if "total_estimated_hours" in data_dict:
                data_dict["total_estimated_hours"] = str(data_dict["total_estimated_hours"])

            response: PostgrestResponse = (
                self._client.table(self._table).update(data_dict).eq("id", str(analysis_id)).execute()
            )

            self._handle_supabase_error(response, f"Failed to update daily analysis {analysis_id}")

            if response.data:
                logger.info(f"✓ Updated daily analysis: {analysis_id}")
                return DailyCommitAnalysis(**response.data[0])
            else:
                logger.warning(f"No data returned after updating analysis {analysis_id}")
                return None

        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating daily analysis: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error updating daily analysis: {str(e)}")

    async def delete(self, analysis_id: UUID) -> bool:
        """Delete a daily commit analysis"""
        try:
            logger.info(f"Deleting daily analysis: {analysis_id}")

            response: PostgrestResponse = (
                self._client.table(self._table).delete().eq("id", str(analysis_id)).execute()
            )

            self._handle_supabase_error(response, f"Failed to delete daily analysis {analysis_id}")

            logger.info(f"✓ Deleted daily analysis: {analysis_id}")
            return True

        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting daily analysis: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error deleting daily analysis: {str(e)}")
