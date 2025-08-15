from fastapi import APIRouter

from app.api.v1.endpoints import kpi, users  # Add other endpoint modules here as they are created
from fastapi import APIRouter
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException
from app.repositories.doc_approval_repository import DocApprovalRepository
from app.models.doc_approval import DocApproval
from uuid import UUID
from typing import Optional
from app.integrations.github_app import GitHubApp, CheckRunStatus, CheckRunConclusion

# Example: from .endpoints import items, other_resources

api_v1_router = APIRouter()

# Include user routes
api_v1_router.include_router(users.router, prefix="/users", tags=["Users"])

# Include KPI routes
api_v1_router.include_router(kpi.router, prefix="/kpi", tags=["KPIs"])

# Include other resource routers here
# api_v1_router.include_router(items.router, prefix="/items", tags=["Items"])
# api_v1_router.include_router(other_resources.router, prefix="/others", tags=["Others"])


# Minimal documentation approvals API for dashboard
@api_v1_router.get("/doc-approvals")
async def list_doc_approvals(
    status: Optional[str] = None,
    repo: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    repo_layer = DocApprovalRepository(db)
    return await repo_layer.get_approvals_for_dashboard(status=status, repo=repo, limit=limit, offset=offset)


@api_v1_router.get("/doc-approvals/{approval_id}")
async def get_doc_approval(approval_id: UUID, db: AsyncSession = Depends(get_db)):
    repo_layer = DocApprovalRepository(db)
    approval = await repo_layer.get_approval_by_id(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    return {
        "id": str(approval.id),
        "commit_hash": approval.commit_hash,
        "repository": approval.repository,
        "status": approval.status,
        "pr_number": approval.pr_number,
        "pr_url": approval.pr_url,
        "check_run_id": approval.check_run_id,
        "created_at": approval.created_at.isoformat() if approval.created_at else None,
        "expires_at": approval.expires_at.isoformat() if getattr(approval, "expires_at", None) else None,
        "approval_metadata": approval.approval_metadata or {},
        "diff_content": approval.diff_content,
        "patch_content": approval.patch_content,
    }


@api_v1_router.post("/doc-approvals/{approval_id}/approve")
async def approve_doc_approval(approval_id: UUID, db: AsyncSession = Depends(get_db)):
    repo_layer = DocApprovalRepository(db)
    approval = await repo_layer.get_approval_by_id(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    # Update GitHub Check Run if available
    if approval.repository and approval.check_run_id:
        try:
            owner, repo = approval.repository.split("/")
            gh = GitHubApp()
            gh.update_check_run(owner, repo, int(approval.check_run_id), status=CheckRunStatus.COMPLETED, conclusion=CheckRunConclusion.SUCCESS)
        except Exception:
            pass

    approval = await repo_layer.approve_request(approval_id, approved_by="dashboard")
    return {"id": str(approval.id), "status": approval.status, "pr_url": approval.pr_url}


@api_v1_router.post("/doc-approvals/{approval_id}/reject")
async def reject_doc_approval(approval_id: UUID, reason: str = "", db: AsyncSession = Depends(get_db)):
    repo_layer = DocApprovalRepository(db)
    approval = await repo_layer.get_approval_by_id(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    # Update GitHub Check Run if available
    if approval.repository and approval.check_run_id:
        try:
            owner, repo = approval.repository.split("/")
            gh = GitHubApp()
            gh.update_check_run(owner, repo, int(approval.check_run_id), status=CheckRunStatus.COMPLETED, conclusion=CheckRunConclusion.FAILURE, output={
                "title": "Documentation Rejected",
                "summary": reason or "Rejected from dashboard"
            })
        except Exception:
            pass

    approval = await repo_layer.reject_request(approval_id, rejected_by="dashboard", reason=reason or "Rejected")
    return {"id": str(approval.id), "status": approval.status, "rejection_reason": approval.rejection_reason}
