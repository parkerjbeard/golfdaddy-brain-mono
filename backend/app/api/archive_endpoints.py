"""
API endpoints for data archiving and retention management.
Admin-only endpoints for managing data lifecycle.
"""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID

from app.config.supabase_client import get_supabase_client
from app.services.archive_service import ArchiveService, RetentionPolicy
from app.auth.dependencies import get_current_user as get_current_user_profile
from app.models.user import User, UserRole
from app.core.exceptions import DatabaseError, ConfigurationError, PermissionDeniedError
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/archive", tags=["archive"])

# Pydantic models for request/response validation
class ArchiveRequest(BaseModel):
    table_name: Optional[str] = Field(None, description="Specific table to archive. If None, archives all tables.")
    dry_run: bool = Field(True, description="If True, only simulates the archiving without making changes")

class RestoreRequest(BaseModel):
    table_name: str = Field(..., description="Name of the table containing archived records")
    record_ids: List[str] = Field(..., description="List of record IDs to restore")

class RetentionPolicyUpdate(BaseModel):
    table_name: str = Field(..., description="Name of the table")
    retention_months: int = Field(..., ge=1, le=120, description="Retention period in months (1-120)")
    archive_method: str = Field("soft_delete", description="Archive method: 'soft_delete' or 'move_to_archive'")

class ArchiveStatsResponse(BaseModel):
    table_name: str
    active_records: int
    archived_records: int
    retention_months: int
    archive_method: str

class ArchiveResultResponse(BaseModel):
    action: str
    dry_run: bool
    total_records_affected: int
    table_results: Dict[str, Any]
    timestamp: datetime

def get_archive_service():
    """Dependency to get ArchiveService instance."""
    supabase = get_supabase_client()
    return ArchiveService(supabase)

def require_admin_user(current_user: User = Depends(get_current_user_profile)) -> User:
    """Dependency to ensure only admin users can access archive endpoints."""
    if current_user.role != UserRole.ADMIN:
        raise PermissionDeniedError("Archive operations require admin privileges")
    return current_user

@router.post("/run", response_model=ArchiveResultResponse)
async def run_archiving(
    request: ArchiveRequest,
    archive_service: ArchiveService = Depends(get_archive_service),
    current_user: User = Depends(require_admin_user)
):
    """
    Run data archiving process for old, irrelevant data.
    
    This endpoint allows admins to manually trigger the archiving process
    based on configured retention policies.
    """
    try:
        logger.info(f"Admin {current_user.email} initiated archiving: table={request.table_name}, dry_run={request.dry_run}")
        
        results = await archive_service.archive_old_data(
            table_name=request.table_name,
            dry_run=request.dry_run
        )
        
        # Calculate total records affected
        total_affected = 0
        for result in results.values():
            if request.dry_run:
                total_affected += result.get('records_to_archive', 0)
            else:
                total_affected += result.get('records_archived', 0)
        
        return ArchiveResultResponse(
            action="archive",
            dry_run=request.dry_run,
            total_records_affected=total_affected,
            table_results=results,
            timestamp=datetime.now()
        )
        
    except (DatabaseError, ConfigurationError) as e:
        logger.error(f"Archiving error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during archiving: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Archiving operation failed")

@router.post("/restore")
async def restore_archived_data(
    request: RestoreRequest,
    archive_service: ArchiveService = Depends(get_archive_service),
    current_user: User = Depends(require_admin_user)
):
    """
    Restore previously archived records.
    
    This endpoint allows admins to restore specific archived records
    back to active status.
    """
    try:
        logger.info(f"Admin {current_user.email} initiated restoration: table={request.table_name}, count={len(request.record_ids)}")
        
        result = await archive_service.restore_archived_data(
            table_name=request.table_name,
            record_ids=request.record_ids
        )
        
        return {
            "action": "restore",
            "table_name": request.table_name,
            "records_restored": result.get('records_restored', 0),
            "record_ids": request.record_ids,
            "timestamp": datetime.now()
        }
        
    except (DatabaseError, ConfigurationError) as e:
        logger.error(f"Restoration error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during restoration: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Restoration operation failed")

@router.get("/stats", response_model=Dict[str, ArchiveStatsResponse])
async def get_archive_statistics(
    archive_service: ArchiveService = Depends(get_archive_service),
    current_user: User = Depends(require_admin_user)
):
    """
    Get statistics about archived data across all tables.
    
    This endpoint provides an overview of active vs archived records
    for each table with archiving enabled.
    """
    try:
        stats = await archive_service.get_archive_statistics()
        
        # Convert to response model format
        response = {}
        for table_name, table_stats in stats.items():
            response[table_name] = ArchiveStatsResponse(
                table_name=table_name,
                active_records=table_stats['active_records'],
                archived_records=table_stats['archived_records'],
                retention_months=table_stats['retention_months'],
                archive_method=table_stats['archive_method']
            )
        
        return response
        
    except DatabaseError as e:
        logger.error(f"Error getting archive statistics: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting statistics: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get archive statistics")

@router.get("/policies")
async def get_retention_policies(
    archive_service: ArchiveService = Depends(get_archive_service),
    current_user: User = Depends(require_admin_user)
):
    """
    Get current retention policies for all tables.
    
    Returns the configured retention periods and archive methods
    for each table.
    """
    try:
        policies = archive_service.get_retention_policies()
        
        # Convert RetentionPolicy objects to dictionaries
        response = {}
        for table_name, policy in policies.items():
            response[table_name] = {
                "table_name": policy.table_name,
                "retention_months": policy.retention_months,
                "archive_method": policy.archive_method,
                "date_column": policy.date_column,
                "additional_conditions": policy.additional_conditions
            }
        
        return response
        
    except Exception as e:
        logger.error(f"Error getting retention policies: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get retention policies")

@router.put("/policies")
async def update_retention_policy(
    request: RetentionPolicyUpdate,
    archive_service: ArchiveService = Depends(get_archive_service),
    current_user: User = Depends(require_admin_user)
):
    """
    Update retention policy for a specific table.
    
    This endpoint allows admins to modify the retention period
    and archive method for a specific table.
    """
    try:
        logger.info(f"Admin {current_user.email} updating retention policy: {request.table_name} -> {request.retention_months} months")
        
        archive_service.update_retention_policy(
            table_name=request.table_name,
            retention_months=request.retention_months,
            archive_method=request.archive_method
        )
        
        return {
            "action": "update_policy",
            "table_name": request.table_name,
            "retention_months": request.retention_months,
            "archive_method": request.archive_method,
            "updated_by": current_user.email,
            "timestamp": datetime.now()
        }
        
    except ConfigurationError as e:
        logger.error(f"Configuration error updating policy: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error updating policy: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update retention policy")

@router.get("/archived/{table_name}")
async def list_archived_records(
    table_name: str,
    archive_service: ArchiveService = Depends(get_archive_service),
    current_user: User = Depends(require_admin_user),
    limit: int = Query(50, ge=1, le=500, description="Number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip")
):
    """
    List archived records from a specific table.
    
    This endpoint allows admins to browse archived records
    for potential restoration.
    """
    try:
        # Get archived records from the specified table
        supabase = get_supabase_client()
        
        response = supabase.table(table_name)\
            .select("*")\
            .not_.is_("archived_at", "null")\
            .order("archived_at", desc=True)\
            .range(offset, offset + limit - 1)\
            .execute()
        
        return {
            "table_name": table_name,
            "records": response.data if response.data else [],
            "count": len(response.data) if response.data else 0,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Error listing archived records: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list archived records")

@router.delete("/purge/{table_name}")
async def purge_archived_data(
    table_name: str,
    archive_service: ArchiveService = Depends(get_archive_service),
    current_user: User = Depends(require_admin_user),
    older_than_months: int = Query(36, ge=12, description="Purge records archived more than X months ago")
):
    """
    Permanently delete archived records older than specified threshold.
    
    ⚠️ WARNING: This operation permanently deletes data and cannot be undone!
    
    This endpoint allows admins to permanently remove very old archived data
    to free up storage space.
    """
    try:
        logger.warning(f"Admin {current_user.email} initiated PURGE operation: table={table_name}, older_than={older_than_months} months")
        
        # Calculate purge cutoff date
        purge_cutoff = datetime.now() - timedelta(days=older_than_months * 30)
        
        # Get count of records to be purged first
        supabase = get_supabase_client()
        count_response = supabase.table(table_name)\
            .select("count", count="exact")\
            .not_.is_("archived_at", "null")\
            .filter("archived_at", "lt", purge_cutoff.isoformat())\
            .execute()
        
        records_to_purge = count_response.count if count_response.count else 0
        
        if records_to_purge == 0:
            return {
                "action": "purge",
                "table_name": table_name,
                "records_purged": 0,
                "message": "No records found matching purge criteria"
            }
        
        # Perform the permanent deletion
        delete_response = supabase.table(table_name)\
            .delete()\
            .not_.is_("archived_at", "null")\
            .filter("archived_at", "lt", purge_cutoff.isoformat())\
            .execute()
        
        logger.warning(f"PURGED {records_to_purge} records from {table_name} older than {older_than_months} months")
        
        return {
            "action": "purge",
            "table_name": table_name,
            "records_purged": records_to_purge,
            "cutoff_date": purge_cutoff.isoformat(),
            "performed_by": current_user.email,
            "timestamp": datetime.now(),
            "warning": "Data has been permanently deleted"
        }
        
    except Exception as e:
        logger.error(f"Error during purge operation: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Purge operation failed")