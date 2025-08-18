from typing import Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints import kpi, users  # Add other endpoint modules here as they are created
from app.config.settings import settings
from app.core.database import get_db
from app.doc_agent.client_v2 import AutoDocClientV2
from app.integrations.ai_integration_v2 import AIIntegrationV2
from app.integrations.github_app import CheckRunConclusion, CheckRunStatus, GitHubApp
from app.models.doc_approval import DocApproval
from app.repositories.doc_approval_repository import DocApprovalRepository

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

    # Create PR and Check Run like Slack flow
    try:
        client = AutoDocClientV2(
            openai_api_key=settings.OPENAI_API_KEY or "",
            docs_repo=approval.repository or (settings.DOCS_REPOSITORY or ""),
            slack_channel=settings.SLACK_DEFAULT_CHANNEL,
            enable_semantic_search=False,
            use_github_app=True,
        )
        pr_result = await client.create_pr_with_check_run(
            approval.patch_content,
            approval.commit_hash,
            approval_id=str(approval.id),
        )
    except Exception:
        pr_result = None

    # Update Check Run if exists; mark approved in DB with PR info
    if pr_result:
        try:
            await repo_layer.update_check_run(
                approval_id, str(pr_result.get("check_run_id")), head_sha=pr_result.get("head_sha")
            )
        except Exception:
            pass
        approval = await repo_layer.approve_request(
            approval_id,
            approved_by="dashboard",
            pr_url=pr_result.get("pr_url"),
            pr_number=pr_result.get("pr_number"),
        )
    else:
        # Fallback: just mark approved (no PR)
        approval = await repo_layer.approve_request(approval_id, approved_by="dashboard")

    return {
        "id": str(approval.id),
        "status": approval.status,
        "pr_url": approval.pr_url,
        "pr_number": approval.pr_number,
    }


@api_v1_router.post("/doc-approvals/{approval_id}/reject")
async def reject_doc_approval(
    approval_id: UUID, payload: Dict[str, str] = Body(default={}), db: AsyncSession = Depends(get_db)
):
    repo_layer = DocApprovalRepository(db)
    approval = await repo_layer.get_approval_by_id(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    reason = (payload or {}).get("reason", "")
    # Update GitHub Check Run if available
    if approval.repository and approval.check_run_id:
        try:
            owner, repo = approval.repository.split("/")
            gh = GitHubApp()
            gh.update_check_run(
                owner,
                repo,
                int(approval.check_run_id),
                status=CheckRunStatus.COMPLETED,
                conclusion=CheckRunConclusion.FAILURE,
                output={"title": "Documentation Rejected", "summary": reason or "Rejected from dashboard"},
            )
        except Exception:
            pass

    approval = await repo_layer.reject_request(approval_id, rejected_by="dashboard", reason=reason or "Rejected")
    return {"id": str(approval.id), "status": approval.status, "rejection_reason": approval.rejection_reason}


@api_v1_router.post("/doc-approvals/{approval_id}/edit")
async def edit_doc_approval(approval_id: UUID, payload: Dict[str, str] = Body(...), db: AsyncSession = Depends(get_db)):
    repo_layer = DocApprovalRepository(db)
    approval = await repo_layer.get_approval_by_id(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    new_patch = (payload or {}).get("patch")
    if not new_patch:
        raise HTTPException(status_code=400, detail="Missing patch")
    approval.patch_content = new_patch
    approval.updated_at = approval.updated_at
    await db.commit()
    return {"id": str(approval.id), "patch_content": approval.patch_content}


@api_v1_router.post("/doc-approvals/{approval_id}/refine")
async def refine_doc_approval(
    approval_id: UUID, payload: Dict[str, str] = Body(...), db: AsyncSession = Depends(get_db)
):
    repo_layer = DocApprovalRepository(db)
    approval = await repo_layer.get_approval_by_id(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    feedback = (payload or {}).get("feedback", "")
    if not feedback:
        raise HTTPException(status_code=400, detail="Missing feedback")
    ai = AIIntegrationV2()
    updated_patch = await ai.refine_patch(approval.patch_content or "", feedback)
    if not updated_patch:
        raise HTTPException(status_code=502, detail="AI failed to refine patch")
    approval.patch_content = updated_patch
    # Append feedback history
    meta = approval.approval_metadata or {}
    feedback_list = meta.get("feedback", [])
    feedback_list.append({"by": "dashboard", "at": "", "feedback": feedback})
    meta["feedback"] = feedback_list
    approval.approval_metadata = meta
    await db.commit()
    return {"id": str(approval.id), "patch_content": approval.patch_content}
