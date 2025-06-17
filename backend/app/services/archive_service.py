"""
Archive Service for managing data lifecycle and retention policies.
Handles soft deletion and archiving of old, irrelevant data.
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from supabase import Client
import logging
from app.config.settings import settings
from app.core.exceptions import DatabaseError, ConfigurationError
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ArchiveStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    PURGED = "purged"

@dataclass
class RetentionPolicy:
    """Configuration for data retention policies."""
    table_name: str
    retention_months: int
    archive_method: str  # 'soft_delete' or 'move_to_archive'
    date_column: str = 'created_at'
    additional_conditions: Optional[str] = None

class ArchiveService:
    """Service for managing data archiving and retention policies."""
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
        
        # Default retention policies (configurable via environment)
        self.retention_policies = {
            'daily_reports': RetentionPolicy(
                table_name='daily_reports',
                retention_months=int(settings.DAILY_REPORTS_RETENTION_MONTHS if hasattr(settings, 'DAILY_REPORTS_RETENTION_MONTHS') else 12),
                archive_method='soft_delete',
                date_column='report_date'
            ),
            'commits': RetentionPolicy(
                table_name='commits', 
                retention_months=int(settings.COMMITS_RETENTION_MONTHS if hasattr(settings, 'COMMITS_RETENTION_MONTHS') else 24),
                archive_method='soft_delete',
                date_column='commit_timestamp'
            ),
            'tasks': RetentionPolicy(
                table_name='tasks',
                retention_months=int(settings.COMPLETED_TASKS_RETENTION_MONTHS if hasattr(settings, 'COMPLETED_TASKS_RETENTION_MONTHS') else 6),
                archive_method='soft_delete',
                date_column='updated_at',
                additional_conditions="status = 'completed'"
            ),
            'docs': RetentionPolicy(
                table_name='docs',
                retention_months=int(settings.DOCS_RETENTION_MONTHS if hasattr(settings, 'DOCS_RETENTION_MONTHS') else 18),
                archive_method='soft_delete',
                date_column='updated_at'
            )
        }
    
    async def archive_old_data(self, table_name: Optional[str] = None, dry_run: bool = True) -> Dict[str, Any]:
        """
        Archive old data based on retention policies.
        
        Args:
            table_name: Optional specific table to archive. If None, archives all tables.
            dry_run: If True, only simulates the archiving process without making changes.
            
        Returns:
            Summary of archiving results
        """
        results = {}
        
        try:
            policies_to_process = [self.retention_policies[table_name]] if table_name else self.retention_policies.values()
            
            for policy in policies_to_process:
                logger.info(f"Processing archiving for table: {policy.table_name}")
                
                # Calculate cutoff date
                cutoff_date = datetime.now() - timedelta(days=policy.retention_months * 30)
                
                if policy.archive_method == 'soft_delete':
                    result = await self._soft_delete_records(policy, cutoff_date, dry_run)
                else:
                    result = await self._move_to_archive_table(policy, cutoff_date, dry_run)
                
                results[policy.table_name] = result
                
        except Exception as e:
            logger.error(f"Error during archiving process: {str(e)}")
            raise DatabaseError(f"Archiving failed: {str(e)}")
            
        return results
    
    async def _soft_delete_records(self, policy: RetentionPolicy, cutoff_date: datetime, dry_run: bool) -> Dict[str, Any]:
        """Soft delete records by setting archived_at timestamp."""
        
        try:
            # First, check if archived_at column exists, if not create it
            await self._ensure_archive_columns_exist(policy.table_name)
            
            # Build the query conditions
            query_conditions = f"{policy.date_column} < '{cutoff_date.isoformat()}' AND archived_at IS NULL"
            if policy.additional_conditions:
                query_conditions += f" AND {policy.additional_conditions}"
            
            if dry_run:
                # Count records that would be archived
                response = self.supabase.table(policy.table_name)\
                    .select("count", count="exact")\
                    .filter(policy.date_column, "lt", cutoff_date.isoformat())\
                    .is_("archived_at", "null")
                
                if policy.additional_conditions and "status = 'completed'" in policy.additional_conditions:
                    response = response.eq("status", "completed")
                    
                result = response.execute()
                count = result.count if result.count else 0
                
                return {
                    "action": "soft_delete",
                    "dry_run": True,
                    "records_to_archive": count,
                    "cutoff_date": cutoff_date.isoformat(),
                    "policy": policy.__dict__
                }
            else:
                # Perform the soft deletion
                update_data = {
                    "archived_at": datetime.now().isoformat(),
                    "archive_status": ArchiveStatus.ARCHIVED.value
                }
                
                response = self.supabase.table(policy.table_name)\
                    .update(update_data)\
                    .filter(policy.date_column, "lt", cutoff_date.isoformat())\
                    .is_("archived_at", "null")
                
                if policy.additional_conditions and "status = 'completed'" in policy.additional_conditions:
                    response = response.eq("status", "completed")
                    
                result = response.execute()
                
                return {
                    "action": "soft_delete",
                    "dry_run": False,
                    "records_archived": len(result.data) if result.data else 0,
                    "cutoff_date": cutoff_date.isoformat(),
                    "policy": policy.__dict__
                }
                
        except Exception as e:
            logger.error(f"Error in soft delete for {policy.table_name}: {str(e)}")
            raise DatabaseError(f"Soft delete failed for {policy.table_name}: {str(e)}")
    
    async def _move_to_archive_table(self, policy: RetentionPolicy, cutoff_date: datetime, dry_run: bool) -> Dict[str, Any]:
        """Move records to a separate archive table."""
        
        archive_table_name = f"{policy.table_name}_archive"
        
        try:
            # Ensure archive table exists
            await self._ensure_archive_table_exists(policy.table_name, archive_table_name)
            
            if dry_run:
                # Count records that would be moved
                response = self.supabase.table(policy.table_name)\
                    .select("count", count="exact")\
                    .filter(policy.date_column, "lt", cutoff_date.isoformat())
                
                if policy.additional_conditions and "status = 'completed'" in policy.additional_conditions:
                    response = response.eq("status", "completed")
                    
                result = response.execute()
                count = result.count if result.count else 0
                
                return {
                    "action": "move_to_archive",
                    "dry_run": True,
                    "records_to_archive": count,
                    "archive_table": archive_table_name,
                    "cutoff_date": cutoff_date.isoformat(),
                    "policy": policy.__dict__
                }
            else:
                # This would require more complex logic to copy and delete records
                # For now, we'll use soft delete as the primary method
                logger.warning(f"Move to archive table not fully implemented for {policy.table_name}")
                return await self._soft_delete_records(policy, cutoff_date, dry_run)
                
        except Exception as e:
            logger.error(f"Error in move to archive for {policy.table_name}: {str(e)}")
            raise DatabaseError(f"Move to archive failed for {policy.table_name}: {str(e)}")
    
    async def _ensure_archive_columns_exist(self, table_name: str):
        """Ensure that archive-related columns exist in the table."""
        
        try:
            # Check if columns exist and add them if they don't
            # This is a simplified approach - in production you'd want proper migrations
            alter_queries = [
                f"ALTER TABLE public.{table_name} ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ",
                f"ALTER TABLE public.{table_name} ADD COLUMN IF NOT EXISTS archive_status TEXT DEFAULT 'active'"
            ]
            
            for query in alter_queries:
                # Note: Supabase client doesn't directly support DDL queries
                # In a real implementation, you'd run these as migration scripts
                logger.info(f"Archive columns should be added via migration: {query}")
                
        except Exception as e:
            logger.error(f"Error ensuring archive columns exist for {table_name}: {str(e)}")
            # Don't raise here as this might be a permissions issue
    
    async def _ensure_archive_table_exists(self, original_table: str, archive_table: str):
        """Ensure that the archive table exists with the same structure as the original."""
        
        try:
            # This would create an archive table with the same structure
            # In practice, this should be handled by database migrations
            logger.info(f"Archive table {archive_table} should be created via migration")
            
        except Exception as e:
            logger.error(f"Error ensuring archive table exists: {str(e)}")
    
    async def restore_archived_data(self, table_name: str, record_ids: List[str]) -> Dict[str, Any]:
        """
        Restore previously archived records.
        
        Args:
            table_name: Name of the table containing archived records
            record_ids: List of record IDs to restore
            
        Returns:
            Summary of restoration results
        """
        
        try:
            if table_name not in self.retention_policies:
                raise ConfigurationError(f"No retention policy found for table: {table_name}")
            
            update_data = {
                "archived_at": None,
                "archive_status": ArchiveStatus.ACTIVE.value
            }
            
            response = self.supabase.table(table_name)\
                .update(update_data)\
                .in_("id", record_ids)\
                .execute()
            
            return {
                "action": "restore",
                "table_name": table_name,
                "records_restored": len(response.data) if response.data else 0,
                "record_ids": record_ids
            }
            
        except Exception as e:
            logger.error(f"Error restoring archived data: {str(e)}")
            raise DatabaseError(f"Restoration failed: {str(e)}")
    
    async def get_archive_statistics(self) -> Dict[str, Any]:
        """Get statistics about archived data across all tables."""
        
        stats = {}
        
        try:
            for policy in self.retention_policies.values():
                # Count active records
                active_response = self.supabase.table(policy.table_name)\
                    .select("count", count="exact")\
                    .is_("archived_at", "null")\
                    .execute()
                
                # Count archived records  
                archived_response = self.supabase.table(policy.table_name)\
                    .select("count", count="exact")\
                    .not_.is_("archived_at", "null")\
                    .execute()
                
                stats[policy.table_name] = {
                    "active_records": active_response.count if active_response.count else 0,
                    "archived_records": archived_response.count if archived_response.count else 0,
                    "retention_months": policy.retention_months,
                    "archive_method": policy.archive_method
                }
                
        except Exception as e:
            logger.error(f"Error getting archive statistics: {str(e)}")
            raise DatabaseError(f"Failed to get archive statistics: {str(e)}")
            
        return stats
    
    def get_retention_policies(self) -> Dict[str, RetentionPolicy]:
        """Get current retention policies."""
        return self.retention_policies
    
    def update_retention_policy(self, table_name: str, retention_months: int, archive_method: str = "soft_delete"):
        """Update retention policy for a specific table."""
        
        if table_name in self.retention_policies:
            self.retention_policies[table_name].retention_months = retention_months
            self.retention_policies[table_name].archive_method = archive_method
            logger.info(f"Updated retention policy for {table_name}: {retention_months} months, method: {archive_method}")
        else:
            raise ConfigurationError(f"No retention policy exists for table: {table_name}")