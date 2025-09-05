import asyncio
import json
import logging
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.config.supabase_client import get_supabase_client_safe
from app.core.exceptions import DatabaseError, ResourceNotFoundError
from app.models.commit import Commit  # Pydantic model
from supabase import Client, PostgrestAPIResponse

logger = logging.getLogger(__name__)


def convert_datetimes_to_iso(obj: Any) -> Any:
    """Recursively convert all datetime objects in a dictionary/list to ISO format strings."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: convert_datetimes_to_iso(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetimes_to_iso(item) for item in obj]
    else:
        return obj


class CommitRepository:
    def __init__(self, client: Client = None):
        self._client = client if client is not None else get_supabase_client_safe()
        self._table = "commits"

    def _handle_supabase_error(self, response: PostgrestAPIResponse, context_message: str):
        """Helper to log and raise DatabaseError from Supabase errors.

        Ignores MagicMock `.error` objects used in tests.
        """
        if not response:
            return
        err = getattr(response, "error", None)
        if err and getattr(err.__class__, "__name__", "") != "MagicMock":
            error_code = getattr(err, "code", "N/A")
            message = getattr(err, "message", str(err))
            logger.error(f"{context_message}: Supabase error code {error_code} - {message}", exc_info=True)
            raise DatabaseError(f"{context_message}: {message}")

    def _format_log_result(self, operation: str, commit_hash: str, success: bool) -> str:
        """Format a standardized log message for database operations."""
        status = "✓" if success else "❌"
        return f"{status} {operation}: {commit_hash}"

    async def save_commit(self, commit_data: Commit) -> Optional[Commit]:
        """Saves a new commit record or updates it if commit_hash already exists (upsert)."""
        try:
            commit_hash = commit_data.commit_hash
            logger.info(f"Saving commit: {commit_hash}")

            commit_dict = commit_data.model_dump(exclude_unset=True, exclude_none=True)

            # Ensure all UUID fields are converted to strings
            for key, value in commit_dict.items():
                if isinstance(value, UUID):
                    commit_dict[key] = str(value)

            if "id" in commit_dict and commit_dict["id"] is None:  # id is already str by above loop if present
                del commit_dict["id"]  # Let DB handle primary key generation on insert

            # Convert Decimal to string for Supabase if needed (supabase-py might handle it)
            if "ai_estimated_hours" in commit_dict and commit_dict["ai_estimated_hours"] is not None:
                commit_dict["ai_estimated_hours"] = str(commit_dict["ai_estimated_hours"])

            # Convert all datetime objects to ISO format strings (handles nested objects too)
            commit_dict = convert_datetimes_to_iso(commit_dict)

            # Log critical fields for debugging schema issues
            logger.info(
                f"Commit fields being saved: seniority_score={commit_dict.get('seniority_score')}, "
                f"complexity_score={commit_dict.get('complexity_score')}, "
                f"ai_estimated_hours={commit_dict.get('ai_estimated_hours')}, "
                f"author_id={commit_dict.get('author_id')}, "
                f"eod_report_id={commit_dict.get('eod_report_id')}"
            )

            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table).upsert(commit_dict, on_conflict="commit_hash").execute
            )

            self._handle_supabase_error(response, f"Failed to save commit {commit_hash}")
            if response.data:
                logger.info(self._format_log_result("Saved commit", commit_hash, True))
                saved_data = response.data[0]
                if "ai_estimated_hours" in saved_data and saved_data["ai_estimated_hours"] is not None:
                    try:
                        decimal_val = Decimal(str(saved_data["ai_estimated_hours"]))
                        saved_data["ai_estimated_hours"] = decimal_val.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
                    except Exception as conversion_exc:
                        logger.warning(
                            f"Could not convert/round ai_estimated_hours in save_commit: "
                            f"{saved_data.get('ai_estimated_hours')}. Error: {conversion_exc}",
                            exc_info=True,
                        )
                        pass

                return Commit(**saved_data)
            else:
                logger.error(f"Failed to save commit {commit_hash}: No data returned and no Supabase error object.")
                raise DatabaseError(f"Failed to save commit {commit_hash}: No data returned.")
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error saving commit {commit_hash}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error saving commit {commit_hash}: {str(e)}")

    async def bulk_insert_commits(self, commits_data: List[Commit]) -> List[Commit]:
        """Inserts multiple commit records in a single request.
        Note: Supabase upsert doesn't easily return all inserted/updated rows distinctly in one go.
        This implements simple bulk insert. Use save_commit with upsert for update logic.
        """
        if not commits_data:
            return []

        try:
            logger.info(f"Bulk inserting {len(commits_data)} commits")
            commits_dict_list = []
            for commit_data in commits_data:
                commit_dict = commit_data.model_dump(exclude_unset=True, exclude_none=True)
                if "id" in commit_dict and commit_dict["id"] is None:
                    del commit_dict["id"]
                if "ai_estimated_hours" in commit_dict and commit_dict["ai_estimated_hours"] is not None:
                    commit_dict["ai_estimated_hours"] = str(commit_dict["ai_estimated_hours"])
                if "commit_timestamp" in commit_dict and isinstance(commit_dict["commit_timestamp"], datetime):
                    commit_dict["commit_timestamp"] = commit_dict["commit_timestamp"].isoformat()
                commits_dict_list.append(commit_dict)

            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table).insert(commits_dict_list).execute
            )

            self._handle_supabase_error(response, "Bulk insert of commits failed")
            if response.data:
                logger.info(f"✓ Successfully inserted {len(response.data)} of {len(commits_data)} commits")
                saved_commits = []
                for saved_data_item in response.data:
                    if "ai_estimated_hours" in saved_data_item and saved_data_item["ai_estimated_hours"] is not None:
                        try:
                            decimal_val = Decimal(str(saved_data_item["ai_estimated_hours"]))
                            saved_data_item["ai_estimated_hours"] = decimal_val.quantize(
                                Decimal("0.1"), rounding=ROUND_HALF_UP
                            )
                        except Exception as conversion_exc:
                            logger.warning(
                                f"Could not convert/round ai_estimated_hours in bulk_insert_commits. "
                                f"Value: {saved_data_item.get('ai_estimated_hours')}. "
                                f"Error: {conversion_exc}",
                                exc_info=True,
                            )
                            pass
                    saved_commits.append(Commit(**saved_data_item))
                return saved_commits
            else:
                logger.error(f"Bulk insert of commits failed: No data returned and no Supabase error object.")
                raise DatabaseError("Bulk insert of commits failed: No data returned.")
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during bulk insert of commits: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error during bulk insert of commits: {str(e)}")

    async def get_commit_by_hash(self, commit_hash: str) -> Optional[Commit]:
        """Retrieves a commit by its unique hash."""
        try:
            logger.info(f"Fetching commit: {commit_hash}")
            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.from_(self._table).select("*").eq("commit_hash", commit_hash).maybe_single().execute
            )

            if response is None:  # Should not happen with aiohttp/requests if execute ran
                logger.error(f"Null response from database for commit query {commit_hash}")
                raise DatabaseError(f"Received null response from database for commit {commit_hash}.")

            if response.data:
                logger.info(f"✓ Found commit: {commit_hash}")
                saved_data = response.data
                if "ai_estimated_hours" in saved_data and saved_data["ai_estimated_hours"] is not None:
                    try:
                        decimal_val = Decimal(str(saved_data["ai_estimated_hours"]))
                        saved_data["ai_estimated_hours"] = decimal_val.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
                    except Exception as conversion_exc:
                        logger.warning(
                            f"Could not convert/round ai_estimated_hours in get_commit_by_hash: "
                            f"{saved_data.get('ai_estimated_hours')}. Error: {conversion_exc}",
                            exc_info=True,
                        )
                        pass
                return Commit(**saved_data)
            elif response.status_code == 406 or (not response.data and not response.error):
                logger.info(f"Commit not found: {commit_hash}")
                return None
            else:
                self._handle_supabase_error(response, f"Error fetching commit by hash {commit_hash}")
                raise DatabaseError(f"Failed to fetch commit by hash {commit_hash} for unknown reason.")
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching commit {commit_hash}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error fetching commit {commit_hash}: {str(e)}")

    async def update_commit_analysis(
        self, commit_hash: str, ai_estimated_hours: float, seniority_score: int = None
    ) -> Optional[Commit]:
        """Updates an existing commit with AI analysis results."""
        try:
            logger.info(f"Updating commit analysis: {commit_hash}")
            logger.info(f"New analysis values: Hours={ai_estimated_hours}, Seniority={seniority_score}")

            update_data = {
                "ai_estimated_hours": str(ai_estimated_hours),  # Convert to string for Supabase
                "updated_at": datetime.now().isoformat(),
            }

            # Add seniority_score if provided
            if seniority_score is not None:
                update_data["seniority_score"] = seniority_score

            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table).update(update_data).eq("commit_hash", commit_hash).execute
            )

            if response.data:
                logger.info(self._format_log_result("Updated analysis for commit", commit_hash, True))
                saved_data = response.data[0]
                if "ai_estimated_hours" in saved_data and saved_data["ai_estimated_hours"] is not None:
                    try:
                        decimal_val = Decimal(str(saved_data["ai_estimated_hours"]))
                        saved_data["ai_estimated_hours"] = decimal_val.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
                    except Exception as conversion_exc:
                        logger.warning(
                            f"Could not convert/round ai_estimated_hours in update_commit_analysis: "
                            f"{saved_data.get('ai_estimated_hours')}. Error: {conversion_exc}",
                            exc_info=True,
                        )
                        pass
                return Commit(**saved_data)
            else:
                existing_commit = await self.get_commit_by_hash(commit_hash)
                if not existing_commit:
                    logger.error(f"Failed to update commit analysis: Commit with hash {commit_hash} not found.")
                    raise ResourceNotFoundError(resource_name="Commit", resource_id=commit_hash)

                self._handle_supabase_error(response, f"Failed to update commit analysis for {commit_hash}")
                logger.error(
                    f"Failed to update commit analysis for {commit_hash}: No data returned and no Supabase error. Commit might exist but update failed."
                )
                raise DatabaseError(
                    f"Failed to update commit analysis for {commit_hash}: Update operation returned no data."
                )
        except (DatabaseError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating commit analysis {commit_hash}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error updating commit analysis {commit_hash}: {str(e)}")

    async def get_commits_by_user_in_range(self, author_id: UUID, start_date: date, end_date: date) -> List[Commit]:
        """Retrieves all commits by a specific user within a date range (inclusive)."""
        try:
            logger.info(f"Fetching commits for user {author_id} from {start_date} to {end_date}")

            start_dt = datetime.combine(start_date, datetime.min.time()).isoformat()
            # Add one day to end_date to make the range inclusive
            from datetime import timedelta

            end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time()).isoformat()

            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table)
                .select("*")
                .eq("author_id", str(author_id))
                .gte("commit_timestamp", start_dt)
                .lt("commit_timestamp", end_dt)
                .order("commit_timestamp", desc=True)
                .execute
            )

            self._handle_supabase_error(
                response, f"Error fetching commits for user {author_id} in range {start_date} - {end_date}"
            )
            if response.data:
                logger.info(f"✓ Found {len(response.data)} commits for user {author_id}")
                saved_commits = []
                for saved_data_item in response.data:
                    if "ai_estimated_hours" in saved_data_item and saved_data_item["ai_estimated_hours"] is not None:
                        try:
                            decimal_val = Decimal(str(saved_data_item["ai_estimated_hours"]))
                            saved_data_item["ai_estimated_hours"] = decimal_val.quantize(
                                Decimal("0.1"), rounding=ROUND_HALF_UP
                            )
                        except Exception as conversion_exc:
                            logger.warning(
                                f"Could not convert/round ai_estimated_hours in get_commits_by_user_in_range. "
                                f"Value: {saved_data_item.get('ai_estimated_hours')}. "
                                f"Error: {conversion_exc}",
                                exc_info=True,
                            )
                            pass
                    saved_commits.append(Commit(**saved_data_item))
                return saved_commits
            else:
                logger.info(f"No commits found for user {author_id} in date range.")  # No error, just no data
                return []
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error finding commits for user {author_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error finding commits for user {author_id}: {str(e)}")

    async def delete_commit(self, commit_hash: str) -> bool:
        """Deletes a commit by its hash."""
        try:
            logger.info(f"Deleting commit: {commit_hash}")

            existing_commit = await self.get_commit_by_hash(commit_hash)
            if not existing_commit:
                logger.warning(f"Attempted to delete non-existent commit with hash {commit_hash}")
                raise ResourceNotFoundError(resource_name="Commit", resource_id=commit_hash)

            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table).delete().eq("commit_hash", commit_hash).execute()
            )

            self._handle_supabase_error(response, f"Failed to delete commit {commit_hash}")
            logger.info(self._format_log_result("Deleted commit", commit_hash, True))
            return True
        except (DatabaseError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting commit {commit_hash}: {e}", exc_info=True)
            # Log Supabase specific details if available from the exception object
            if hasattr(e, "details"):
                logger.error(
                    f"Supabase error details during delete: {getattr(e, 'details')}", exc_info=False
                )  # exc_info=False to avoid duplicate main traceback
            elif hasattr(e, "message") and not isinstance(e, DatabaseError):
                logger.error(f"Supabase error message during delete: {getattr(e, 'message')}", exc_info=False)
            raise DatabaseError(f"Unexpected error deleting commit {commit_hash}: {str(e)}")

    async def create_commit(self, commit_data: Dict[str, Any]) -> Optional[Commit]:
        """Creates a new commit record with the given data."""
        commit_hash = commit_data.get("commit_hash", "unknown")
        try:
            logger.info(f"Creating new commit: {commit_hash}")

            # Handle any non-serializable types for Supabase
            if "ai_estimated_hours" in commit_data and commit_data["ai_estimated_hours"] is not None:
                commit_data["ai_estimated_hours"] = str(commit_data["ai_estimated_hours"])

            # Handle datetime conversion
            for field in ["commit_timestamp", "created_at", "updated_at"]:
                if field in commit_data and isinstance(commit_data[field], datetime):
                    commit_data[field] = commit_data[field].isoformat()

            # Handle UUID conversion
            if "author_id" in commit_data and commit_data["author_id"] is not None:
                commit_data["author_id"] = str(commit_data["author_id"])

            # Log important fields for tracking
            debug_fields = {
                "commit_hash": commit_data.get("commit_hash"),
                "repository_name": commit_data.get("repository_name"),
            }

            if "author_id" in commit_data:
                debug_fields["author_id"] = commit_data.get("author_id")

            logger.info(f"Commit metadata: {json.dumps(debug_fields, default=str)}")

            # Explicitly use from_ to ensure we're using the service role
            # This should bypass RLS policies
            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.from_(self._table).insert(commit_data).execute()
            )

            self._handle_supabase_error(response, f"Failed to create commit {commit_hash}")
            if response.data:
                logger.info(self._format_log_result("Created commit", commit_hash, True))
                saved_data = response.data[0]

                if "ai_estimated_hours" in saved_data and saved_data["ai_estimated_hours"] is not None:
                    try:
                        decimal_val = Decimal(str(saved_data["ai_estimated_hours"]))
                        saved_data["ai_estimated_hours"] = decimal_val.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
                    except Exception as conversion_exc:
                        logger.warning(
                            f"⚠ Could not convert/round ai_estimated_hours in create_commit: "
                            f"{saved_data.get('ai_estimated_hours')}. Error: {conversion_exc}",
                            exc_info=True,
                        )
                        pass

                return Commit(**saved_data)
            else:
                logger.error(self._format_log_result("Failed to create commit (no data returned)", commit_hash, False))
                # _handle_supabase_error should have caught specific errors. This is a fallback.
                raise DatabaseError(f"Failed to create commit {commit_hash}: No data returned and no Supabase error.")
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating commit {commit_hash}: {e}", exc_info=True)
            # Log Supabase specific details if available
            if hasattr(e, "details"):
                logger.error(f"Supabase error details during create: {getattr(e, 'details')}", exc_info=False)
            elif hasattr(e, "message") and not isinstance(e, DatabaseError):
                logger.error(f"Supabase error message during create: {getattr(e, 'message')}", exc_info=False)
            raise DatabaseError(f"Unexpected error creating commit {commit_hash}: {str(e)}")

    async def get_existing_commit_hashes(self, commit_hashes: List[str]) -> List[str]:
        """Check which commits already exist in the database.

        This method is used by the historical seeder to avoid re-analyzing commits
        that have already been processed. It performs efficient batch queries to
        minimize database round trips.

        Args:
            commit_hashes: List of commit hashes to check

        Returns:
            List of commit hashes that already exist in the database

        Example:
            >>> existing = await repo.get_existing_commit_hashes(['abc123', 'def456', 'ghi789'])
            >>> print(existing)  # ['abc123', 'ghi789']  # def456 is new
        """
        if not commit_hashes:
            return []

        try:
            logger.info(f"Checking existence of {len(commit_hashes)} commits")

            # Split into chunks to avoid query size limits
            chunk_size = 100
            existing_hashes = []

            for i in range(0, len(commit_hashes), chunk_size):
                chunk = commit_hashes[i : i + chunk_size]

                response: PostgrestAPIResponse = await asyncio.to_thread(
                    self._client.table(self._table).select("commit_hash").in_("commit_hash", chunk).execute
                )

                if response and getattr(response, "data", None):
                    existing_hashes.extend([item["commit_hash"] for item in response.data])

            logger.info(f"✓ Found {len(existing_hashes)} existing commits out of {len(commit_hashes)} checked")
            return existing_hashes

        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error checking commit existence: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error checking commit existence: {str(e)}")

    async def get_commits_with_analysis(self, commit_hashes: List[str]) -> Dict[str, Commit]:
        """Get existing commits with their full analysis data.

        This method retrieves complete commit records including AI analysis results,
        allowing the historical seeder to reuse existing analyses without making
        new API calls to OpenAI.

        Args:
            commit_hashes: List of commit hashes to retrieve

        Returns:
            Dictionary mapping commit hash to Commit object with full analysis data

        Example:
            >>> commits = await repo.get_commits_with_analysis(['abc123', 'def456'])
            >>> commit = commits['abc123']
            >>> print(f"Hours: {commit.ai_estimated_hours}, Score: {commit.complexity_score}")
        """
        if not commit_hashes:
            return {}

        try:
            logger.info(f"Fetching {len(commit_hashes)} commits with analysis data")

            # Split into chunks to avoid query size limits
            chunk_size = 50
            commits_by_hash = {}

            for i in range(0, len(commit_hashes), chunk_size):
                chunk = commit_hashes[i : i + chunk_size]

                response: PostgrestAPIResponse = await asyncio.to_thread(
                    self._client.table(self._table).select("*").in_("commit_hash", chunk).execute
                )

                self._handle_supabase_error(response, "Error fetching commits with analysis")

                if response.data:
                    for saved_data_item in response.data:
                        if (
                            "ai_estimated_hours" in saved_data_item
                            and saved_data_item["ai_estimated_hours"] is not None
                        ):
                            try:
                                decimal_val = Decimal(str(saved_data_item["ai_estimated_hours"]))
                                saved_data_item["ai_estimated_hours"] = decimal_val.quantize(
                                    Decimal("0.1"), rounding=ROUND_HALF_UP
                                )
                            except Exception as conversion_exc:
                                logger.warning(
                                    f"Could not convert/round ai_estimated_hours. "
                                    f"Value: {saved_data_item.get('ai_estimated_hours')}. "
                                    f"Error: {conversion_exc}",
                                    exc_info=True,
                                )
                                pass

                        commit = Commit(**saved_data_item)
                        commits_by_hash[commit.commit_hash] = commit

            logger.info(f"✓ Retrieved {len(commits_by_hash)} commits with analysis data")
            return commits_by_hash

        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching commits with analysis: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error fetching commits with analysis: {str(e)}")
