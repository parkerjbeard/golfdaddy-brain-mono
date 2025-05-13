from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, date
from decimal import ROUND_HALF_UP
from supabase import Client
from app.config.supabase_client import get_supabase_client_safe
from app.models.commit import Commit # Pydantic model
import logging
import json

logger = logging.getLogger(__name__)

class CommitRepository:
    def __init__(self, client: Client = None):
        self._client = client if client is not None else get_supabase_client_safe()
        self._table = "commits"
        
    def _format_log_result(self, operation: str, commit_hash: str, success: bool) -> str:
        """Format a standardized log message for database operations."""
        status = "✓" if success else "❌"
        return f"{status} {operation}: {commit_hash}"

    def save_commit(self, commit_data: Commit) -> Optional[Commit]:
        """Saves a new commit record or updates it if commit_hash already exists (upsert)."""
        try:
            commit_hash = commit_data.commit_hash
            logger.info(f"Saving commit: {commit_hash}")
            
            commit_dict = commit_data.model_dump(exclude_unset=True, exclude_none=True)
            
            # Ensure all UUID fields are converted to strings
            for key, value in commit_dict.items():
                if isinstance(value, UUID):
                    commit_dict[key] = str(value)
            
            if 'id' in commit_dict and commit_dict['id'] is None: # id is already str by above loop if present
                 del commit_dict['id'] # Let DB handle primary key generation on insert
            
            # Convert Decimal to string for Supabase if needed (supabase-py might handle it)
            if 'ai_estimated_hours' in commit_dict and commit_dict['ai_estimated_hours'] is not None:
                 commit_dict['ai_estimated_hours'] = str(commit_dict['ai_estimated_hours'])
                 
            # Ensure commit_timestamp is timezone-aware or in ISO format string
            if 'commit_timestamp' in commit_dict and isinstance(commit_dict['commit_timestamp'], datetime):
                 commit_dict['commit_timestamp'] = commit_dict['commit_timestamp'].isoformat()
                 
            # Log critical fields for debugging schema issues
            logger.info(f"Commit fields being saved: seniority_score={commit_dict.get('seniority_score')}, " 
                        f"complexity_score={commit_dict.get('complexity_score')}, "
                        f"ai_estimated_hours={commit_dict.get('ai_estimated_hours')}, "
                        f"author_id={commit_dict.get('author_id')}, "
                        f"eod_report_id={commit_dict.get('eod_report_id')}")

            response = self._client.table(self._table).upsert(commit_dict, on_conflict='commit_hash').execute()
            
            if response.data:
                logger.info(self._format_log_result("Saved commit", commit_hash, True))
                # Convert back certain scalar fields that might have been converted for storage
                saved_data = response.data[0]
                if 'ai_estimated_hours' in saved_data and saved_data['ai_estimated_hours'] is not None:
                    from decimal import Decimal
                    try:
                        decimal_val = Decimal(str(saved_data['ai_estimated_hours']))
                        saved_data['ai_estimated_hours'] = decimal_val.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
                    except Exception as conversion_exc:
                        logger.warning(f"Could not convert/round ai_estimated_hours in save_commit: {saved_data.get('ai_estimated_hours')}. Error: {conversion_exc}")
                        pass # Let Pydantic handle potential errors if conversion fails
                
                return Commit(**saved_data)
            else:
                if hasattr(response, 'error') and response.error:
                    logger.error(f"❌ Exception saving commit {commit_hash}: {response.error}")
                else:
                    logger.error(f"❌ Failed to save commit {commit_hash} but no error was provided")
                return None
        except Exception as e:
            logger.error(f"❌ Exception saving commit {commit_hash}: {e}")
            logger.exception("Traceback for commit save exception:")
            return None

    def bulk_insert_commits(self, commits_data: List[Commit]) -> List[Commit]:
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
                 if 'id' in commit_dict and commit_dict['id'] is None:
                     del commit_dict['id']
                 if 'ai_estimated_hours' in commit_dict and commit_dict['ai_estimated_hours'] is not None:
                     commit_dict['ai_estimated_hours'] = str(commit_dict['ai_estimated_hours'])
                 if 'commit_timestamp' in commit_dict and isinstance(commit_dict['commit_timestamp'], datetime):
                      commit_dict['commit_timestamp'] = commit_dict['commit_timestamp'].isoformat()
                 commits_dict_list.append(commit_dict)
                 
            response = self._client.table(self._table).insert(commits_dict_list).execute()
            
            if response.data:
                logger.info(f"✓ Successfully inserted {len(response.data)} of {len(commits_data)} commits")
                # Convert back decimals if needed
                saved_commits = []
                for saved_data_item in response.data:
                     if 'ai_estimated_hours' in saved_data_item and saved_data_item['ai_estimated_hours'] is not None:
                         from decimal import Decimal
                         try:
                             decimal_val = Decimal(str(saved_data_item['ai_estimated_hours']))
                             saved_data_item['ai_estimated_hours'] = decimal_val.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
                         except Exception as conversion_exc:
                             logger.warning(f"Could not convert/round ai_estimated_hours in bulk_insert_commits for an item. Value: {saved_data_item.get('ai_estimated_hours')}. Error: {conversion_exc}")
                             pass # Let Pydantic handle
                     saved_commits.append(Commit(**saved_data_item))
                return saved_commits
            else:
                error_message = response.error.message if response.error else "Unknown error during bulk insert"
                logger.error(f"❌ Bulk insert failed: {error_message}")
                return []
        except Exception as e:
            logger.exception(f"❌ Exception during bulk insert: {e}")
            return []

    def get_commit_by_hash(self, commit_hash: str) -> Optional[Commit]:
        """Retrieves a commit by its unique hash."""
        try:
            logger.info(f"Fetching commit: {commit_hash}")
            # Use from_ instead of table() to help bypass RLS
            response = self._client.from_(self._table).select("*").eq("commit_hash", commit_hash).maybe_single().execute()
            
            # Check if response itself is None before trying to access response.data
            if response is None:
                logger.error(f"❌ Null response from database for commit {commit_hash}")
                return None
                
            if response.data:
                logger.info(f"✓ Found commit: {commit_hash}")
                saved_data = response.data
                if 'ai_estimated_hours' in saved_data and saved_data['ai_estimated_hours'] is not None:
                    from decimal import Decimal
                    try:
                         decimal_val = Decimal(str(saved_data['ai_estimated_hours']))
                         saved_data['ai_estimated_hours'] = decimal_val.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
                    except Exception as conversion_exc:
                        logger.warning(f"Could not convert/round ai_estimated_hours in get_commit_by_hash: {saved_data.get('ai_estimated_hours')}. Error: {conversion_exc}")
                        pass # Let Pydantic handle
                return Commit(**saved_data)
            else:
                if response.error and response.status_code != 406: 
                     logger.error(f"❌ Error fetching commit: {response.error.message}")
                else:
                     logger.info(f"Commit not found: {commit_hash}")
                return None
        except Exception as e:
            logger.exception(f"❌ Exception fetching commit {commit_hash}: {e}")
            return None

    def update_commit_analysis(self, commit_hash: str, ai_estimated_hours: float, seniority_score: int = None) -> Optional[Commit]:
        """Updates an existing commit with AI analysis results."""
        try:
            logger.info(f"Updating commit analysis: {commit_hash}")
            logger.info(f"New analysis values: Hours={ai_estimated_hours}, Seniority={seniority_score}")
            
            update_data = {
                "ai_estimated_hours": str(ai_estimated_hours),  # Convert to string for Supabase
                "updated_at": datetime.now().isoformat()
            }
            
            # Add seniority_score if provided
            if seniority_score is not None:
                update_data["seniority_score"] = seniority_score
            
            response = self._client.table(self._table).update(update_data).eq("commit_hash", commit_hash).execute()
            
            if response.data:
                logger.info(self._format_log_result("Updated analysis for commit", commit_hash, True))
                saved_data = response.data[0]
                if 'ai_estimated_hours' in saved_data and saved_data['ai_estimated_hours'] is not None:
                    from decimal import Decimal
                    try:
                        decimal_val = Decimal(str(saved_data['ai_estimated_hours']))
                        saved_data['ai_estimated_hours'] = decimal_val.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
                    except Exception as conversion_exc:
                        logger.warning(f"Could not convert/round ai_estimated_hours in update_commit_analysis: {saved_data.get('ai_estimated_hours')}. Error: {conversion_exc}")
                        pass # Let Pydantic handle
                return Commit(**saved_data)
            else:
                error_message = response.error.message if response.error else "Unknown error or commit not found"
                logger.error(self._format_log_result("Failed to update analysis", commit_hash, False))
                logger.error(f"Error: {error_message}")
                return None
        except Exception as e:
            logger.exception(f"❌ Exception updating commit analysis {commit_hash}: {e}")
            return None

    def get_commits_by_user_in_range(self, author_id: UUID, start_date: date, end_date: date) -> List[Commit]:
        """Retrieves all commits by a specific user within a date range (inclusive)."""
        try:
            logger.info(f"Fetching commits for user {author_id} from {start_date} to {end_date}")
            
            start_dt = datetime.combine(start_date, datetime.min.time()).isoformat()
            # Add one day to end_date to make the range inclusive
            from datetime import timedelta
            end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time()).isoformat()
            
            response = self._client.table(self._table).select("*")\
                         .eq("author_id", str(author_id))\
                         .gte("commit_timestamp", start_dt)\
                         .lt("commit_timestamp", end_dt)\
                         .order("commit_timestamp", desc=True)\
                         .execute()
                         
            if response.data:
                logger.info(f"✓ Found {len(response.data)} commits for user {author_id}")
                saved_commits = []
                for saved_data_item in response.data:
                     if 'ai_estimated_hours' in saved_data_item and saved_data_item['ai_estimated_hours'] is not None:
                         from decimal import Decimal
                         try:
                             decimal_val = Decimal(str(saved_data_item['ai_estimated_hours']))
                             saved_data_item['ai_estimated_hours'] = decimal_val.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
                         except Exception as conversion_exc:
                             logger.warning(f"Could not convert/round ai_estimated_hours in get_commits_by_user_in_range for an item. Value: {saved_data_item.get('ai_estimated_hours')}. Error: {conversion_exc}")
                             pass # Let Pydantic handle
                     saved_commits.append(Commit(**saved_data_item))
                return saved_commits
            else:
                logger.info(f"No commits found for user {author_id} in date range, or an unexpected issue occurred.")
                return []
        except Exception as e:
            logger.exception(f"❌ Exception finding commits for user {author_id}: {e}")
            return []

    def delete_commit(self, commit_hash: str) -> bool:
        """Deletes a commit by its hash."""
        try:
            logger.info(f"Deleting commit: {commit_hash}")
            response = self._client.table(self._table).delete().eq("commit_hash", commit_hash).execute()
            
            logger.info(self._format_log_result("Deleted commit", commit_hash, True))
            return True
        except Exception as e:
            logger.exception(f"❌ Exception deleting commit {commit_hash}: {e}")
            if hasattr(e, 'details'):
                logger.error(f"Supabase error details: {getattr(e, 'details')}")
            elif hasattr(e, 'message'):
                 logger.error(f"Supabase error message: {getattr(e, 'message')}")
            return False

    def create_commit(self, commit_data: Dict[str, Any]) -> Optional[Commit]:
        """Creates a new commit record with the given data."""
        try:
            commit_hash = commit_data.get('commit_hash', 'unknown')
            logger.info(f"Creating new commit: {commit_hash}")
            
            # Handle any non-serializable types for Supabase
            if 'ai_estimated_hours' in commit_data and commit_data['ai_estimated_hours'] is not None:
                commit_data['ai_estimated_hours'] = str(commit_data['ai_estimated_hours'])
                
            # Handle datetime conversion
            for field in ['commit_timestamp', 'created_at', 'updated_at']:
                if field in commit_data and isinstance(commit_data[field], datetime):
                    commit_data[field] = commit_data[field].isoformat()
                    
            # Handle UUID conversion
            if 'author_id' in commit_data and commit_data['author_id'] is not None:
                commit_data['author_id'] = str(commit_data['author_id'])
            
            # Log important fields for tracking
            debug_fields = {
                'commit_hash': commit_data.get('commit_hash'),
                'repository_name': commit_data.get('repository_name'),
            }
            
            if 'author_id' in commit_data:
                debug_fields['author_id'] = commit_data.get('author_id')
                
            logger.info(f"Commit metadata: {json.dumps(debug_fields, default=str)}")
            
            # Explicitly use from_ to ensure we're using the service role
            # This should bypass RLS policies
            response = self._client.from_(self._table).insert(commit_data).execute()
            
            if response.data:
                logger.info(self._format_log_result("Created commit", commit_hash, True))
                saved_data = response.data[0]
                
                # Convert any string values back to their proper types
                if 'ai_estimated_hours' in saved_data and saved_data['ai_estimated_hours'] is not None:
                    from decimal import Decimal
                    try:
                        decimal_val = Decimal(str(saved_data['ai_estimated_hours']))
                        saved_data['ai_estimated_hours'] = decimal_val.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
                    except Exception as conversion_exc:
                        logger.warning(f"⚠ Could not convert/round ai_estimated_hours in create_commit: {saved_data.get('ai_estimated_hours')}. Error: {conversion_exc}")
                        pass
                        
                return Commit(**saved_data)
            else:
                logger.error(self._format_log_result("Failed to create commit (no data returned)", commit_hash, False))
                return None
        except Exception as e:
            commit_hash = commit_data.get('commit_hash', 'unknown')
            logger.exception(f"❌ Exception creating commit {commit_hash}: {e}")
            if hasattr(e, 'details'):
                logger.error(f"Supabase error details: {getattr(e, 'details')}")
            elif hasattr(e, 'message'):
                 logger.error(f"Supabase error message: {getattr(e, 'message')}")
            return None