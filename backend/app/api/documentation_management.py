"""
Documentation Management API Endpoints

Comprehensive API for documentation quality validation, approval workflows,
diff management, and caching operations.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field
from datetime import datetime

from app.config.supabase_client import get_supabase_client
from app.services.doc_quality_service import DocQualityService, QualityMetrics
from app.services.doc_approval_service import DocApprovalService, ApprovalStatus, ReviewerRole
from app.services.doc_diff_service import DocDiffService, DiffFormat
from app.services.doc_cache_service import cache_service, cache_monitor, warmup_service
from app.core.exceptions import ValidationError, ResourceNotFoundError
from supabase import Client
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documentation", tags=["documentation_management"])


# Pydantic models for request/response validation
class QualityValidationRequest(BaseModel):
    content: str = Field(..., description="Documentation content to validate")
    doc_type: str = Field("general", description="Type of documentation")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context for validation")


class QualityValidationResponse(BaseModel):
    metrics: Dict[str, Any]
    auto_approve_recommended: bool
    improvement_suggestions: List[str]
    validated_at: str


class ApprovalRequestModel(BaseModel):
    document_id: str = Field(..., description="ID of the document")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Document content")
    doc_type: str = Field(..., description="Type of documentation")
    reviewers: Optional[List[str]] = Field(None, description="Specific reviewers to assign")


class ReviewSubmissionModel(BaseModel):
    decision: str = Field(..., description="Review decision: approve, reject, or request_changes")
    comments: str = Field(..., description="Review comments")
    reviewer_role: str = Field("technical_reviewer", description="Role of the reviewer")


class DiffPreviewRequest(BaseModel):
    current_content: str = Field(..., description="Current document content")
    proposed_content: str = Field(..., description="Proposed new content")
    format_type: str = Field("side_by_side", description="Diff format: unified, side_by_side, html, json")


class RollbackRequest(BaseModel):
    target_version_id: str = Field(..., description="Version ID to rollback to")
    reason: str = Field("", description="Reason for rollback")


# Quality Validation Endpoints
@router.post("/quality/validate", response_model=QualityValidationResponse)
async def validate_documentation_quality(
    request: QualityValidationRequest = Body(...),
):
    """
    Validate documentation quality and get detailed metrics.
    
    Returns quality scores, issues, suggestions, and auto-approval recommendation.
    """
    try:
        quality_service = DocQualityService()
        
        # Validate documentation
        metrics = await quality_service.validate_documentation(
            content=request.content,
            doc_type=request.doc_type,
            context=request.context
        )
        
        # Check auto-approval recommendation
        auto_approve = quality_service.should_approve_automatically(metrics, request.doc_type)
        
        # Generate improvement suggestions
        suggestions = await quality_service.generate_improvement_suggestions(request.content, metrics)
        
        return QualityValidationResponse(
            metrics=metrics.to_dict(),
            auto_approve_recommended=auto_approve,
            improvement_suggestions=suggestions,
            validated_at=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error validating documentation quality: {e}")
        raise HTTPException(status_code=500, detail=f"Quality validation failed: {str(e)}")


@router.get("/quality/thresholds")
async def get_quality_thresholds():
    """Get quality thresholds for different document types."""
    quality_service = DocQualityService()
    
    doc_types = ["api", "guide", "reference", "tutorial", "general"]
    thresholds = {}
    
    for doc_type in doc_types:
        thresholds[doc_type] = quality_service.get_quality_threshold(doc_type)
    
    return {"thresholds": thresholds}


# Approval Workflow Endpoints
@router.post("/approvals")
async def create_approval_request(
    request: ApprovalRequestModel = Body(...),
    supabase: Client = Depends(get_supabase_client)
):
    """Create a new documentation approval request."""
    try:
        approval_service = DocApprovalService(supabase)
        
        # Optionally validate quality first
        quality_service = DocQualityService()
        quality_metrics = await quality_service.validate_documentation(
            content=request.content,
            doc_type=request.doc_type
        )
        
        # Create approval request
        approval_request = await approval_service.create_approval_request(
            document_id=request.document_id,
            title=request.title,
            content=request.content,
            doc_type=request.doc_type,
            author_id="current_user_id",  # TODO: Get from auth context
            quality_metrics=quality_metrics,
            reviewers=request.reviewers
        )
        
        return approval_request.to_dict()
        
    except Exception as e:
        logger.error(f"Error creating approval request: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create approval request: {str(e)}")


@router.get("/approvals/{request_id}")
async def get_approval_request(
    request_id: str,
    supabase: Client = Depends(get_supabase_client)
):
    """Get approval request by ID."""
    try:
        approval_service = DocApprovalService(supabase)
        approval_request = await approval_service.get_approval_request(request_id)
        return approval_request.to_dict()
        
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail=f"Approval request {request_id} not found")
    except Exception as e:
        logger.error(f"Error fetching approval request {request_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/approvals")
async def list_approval_requests(
    status: Optional[str] = Query(None, description="Filter by status"),
    doc_type: Optional[str] = Query(None, description="Filter by document type"),
    author_id: Optional[str] = Query(None, description="Filter by author"),
    reviewer_id: Optional[str] = Query(None, description="Filter by reviewer"),
    limit: int = Query(50, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination"),
    supabase: Client = Depends(get_supabase_client)
):
    """List approval requests with optional filters."""
    try:
        approval_service = DocApprovalService(supabase)
        
        filters = {}
        if status:
            filters["status"] = status
        if doc_type:
            filters["doc_type"] = doc_type
        if author_id:
            filters["author_id"] = author_id
        if reviewer_id:
            filters["reviewer_id"] = reviewer_id
        
        requests = await approval_service.list_approval_requests(
            filters=filters,
            limit=limit,
            offset=offset
        )
        
        return {
            "requests": [req.to_dict() for req in requests],
            "count": len(requests),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Error listing approval requests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approvals/{request_id}/review")
async def submit_review(
    request_id: str,
    review: ReviewSubmissionModel = Body(...),
    supabase: Client = Depends(get_supabase_client)
):
    """Submit a review for an approval request."""
    try:
        approval_service = DocApprovalService(supabase)
        
        # Validate review decision
        if review.decision not in ["approve", "reject", "request_changes"]:
            raise ValidationError("Invalid review decision")
        
        # Submit review
        updated_request = await approval_service.submit_review(
            request_id=request_id,
            reviewer_id="current_user_id",  # TODO: Get from auth context
            decision=review.decision,
            comments=review.comments,
            reviewer_role=ReviewerRole(review.reviewer_role)
        )
        
        return updated_request.to_dict()
        
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail=f"Approval request {request_id} not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error submitting review for {request_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/approvals/pending/{user_id}")
async def get_pending_approvals(
    user_id: str,
    supabase: Client = Depends(get_supabase_client)
):
    """Get pending approval requests for a user."""
    try:
        approval_service = DocApprovalService(supabase)
        requests = await approval_service.get_pending_approvals_for_user(user_id)
        
        return {
            "pending_requests": [req.to_dict() for req in requests],
            "count": len(requests)
        }
        
    except Exception as e:
        logger.error(f"Error getting pending approvals for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Diff and Version Management Endpoints
@router.post("/diff/preview")
async def preview_documentation_changes(
    request: DiffPreviewRequest = Body(...)
):
    """Preview changes between current and proposed documentation content."""
    try:
        diff_service = DocDiffService(None)  # No DB needed for preview
        
        # Validate format type
        try:
            format_type = DiffFormat(request.format_type)
        except ValueError:
            raise ValidationError(f"Invalid format type: {request.format_type}")
        
        # Generate diff preview
        preview = await diff_service.preview_changes(
            current_content=request.current_content,
            proposed_content=request.proposed_content,
            format_type=format_type
        )
        
        return preview
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating diff preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/{document_id}/versions")
async def create_document_version(
    document_id: str,
    content: str = Body(..., embed=True),
    title: str = Body(..., embed=True),
    commit_message: Optional[str] = Body(None, embed=True),
    supabase: Client = Depends(get_supabase_client)
):
    """Create a new version of a document."""
    try:
        diff_service = DocDiffService(supabase)
        
        version = await diff_service.create_version(
            document_id=document_id,
            content=content,
            title=title,
            author_id="current_user_id",  # TODO: Get from auth context
            commit_message=commit_message
        )
        
        return version.to_dict()
        
    except Exception as e:
        logger.error(f"Error creating version for document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{document_id}/versions")
async def list_document_versions(
    document_id: str,
    limit: int = Query(20, description="Maximum number of versions to return"),
    supabase: Client = Depends(get_supabase_client)
):
    """List versions for a document."""
    try:
        diff_service = DocDiffService(supabase)
        versions = await diff_service.list_versions(document_id, limit)
        
        return {
            "versions": [version.to_dict() for version in versions],
            "count": len(versions)
        }
        
    except Exception as e:
        logger.error(f"Error listing versions for document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions/{version_id}")
async def get_document_version(
    version_id: str,
    supabase: Client = Depends(get_supabase_client)
):
    """Get a specific document version."""
    try:
        diff_service = DocDiffService(supabase)
        version = await diff_service.get_version(version_id)
        return version.to_dict()
        
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail=f"Version {version_id} not found")
    except Exception as e:
        logger.error(f"Error fetching version {version_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/diff/{from_version_id}/{to_version_id}")
async def get_version_diff(
    from_version_id: str,
    to_version_id: str,
    format_type: str = Query("unified", description="Diff format"),
    supabase: Client = Depends(get_supabase_client)
):
    """Generate diff between two document versions."""
    try:
        diff_service = DocDiffService(supabase)
        
        # Validate format type
        try:
            diff_format = DiffFormat(format_type)
        except ValueError:
            raise ValidationError(f"Invalid format type: {format_type}")
        
        diff = await diff_service.generate_diff(from_version_id, to_version_id, diff_format)
        return diff.to_dict()
        
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating diff between {from_version_id} and {to_version_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/{document_id}/rollback")
async def rollback_document(
    document_id: str,
    request: RollbackRequest = Body(...),
    supabase: Client = Depends(get_supabase_client)
):
    """Rollback document to a specific version."""
    try:
        diff_service = DocDiffService(supabase)
        
        rollback_version = await diff_service.rollback_to_version(
            document_id=document_id,
            target_version_id=request.target_version_id,
            author_id="current_user_id",  # TODO: Get from auth context
            rollback_reason=request.reason
        )
        
        return rollback_version.to_dict()
        
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error rolling back document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{document_id}/rollback-history")
async def get_rollback_history(
    document_id: str,
    supabase: Client = Depends(get_supabase_client)
):
    """Get rollback history for a document."""
    try:
        diff_service = DocDiffService(supabase)
        history = await diff_service.get_rollback_history(document_id)
        
        return {"rollback_history": history}
        
    except Exception as e:
        logger.error(f"Error fetching rollback history for document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Cache Management Endpoints
@router.get("/cache/stats")
async def get_cache_statistics():
    """Get cache performance statistics."""
    try:
        stats = cache_service.get_stats()
        performance_analysis = cache_monitor.analyze_performance()
        
        return {
            "cache_stats": stats,
            "performance_analysis": performance_analysis
        }
        
    except Exception as e:
        logger.error(f"Error fetching cache statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/entries")
async def get_cache_entries():
    """Get information about all cache entries."""
    try:
        entries = cache_service.get_entries()
        return {"cache_entries": entries}
        
    except Exception as e:
        logger.error(f"Error fetching cache entries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache")
async def clear_cache():
    """Clear all cache entries."""
    try:
        await cache_service.clear()
        return {"message": "Cache cleared successfully"}
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache/{operation}")
async def invalidate_cache_operation(operation: str):
    """Invalidate cache entries for a specific operation."""
    try:
        count = await cache_service.invalidate_pattern(f"{operation}:*")
        return {"message": f"Invalidated {count} cache entries for operation: {operation}"}
        
    except Exception as e:
        logger.error(f"Error invalidating cache for operation {operation}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/warmup")
async def warmup_cache():
    """Warm up cache with commonly used operations."""
    try:
        await warmup_service.warmup_common_operations()
        return {"message": "Cache warmup completed successfully"}
        
    except Exception as e:
        logger.error(f"Error warming up cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))