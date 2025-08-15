"""
Repository for managing documentation approval requests with dashboard integration.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import DatabaseError, ResourceNotFoundError
from app.models.doc_approval import DocApproval
from app.models.proposals import Proposal

logger = logging.getLogger(__name__)


class DocApprovalRepository:
    """Repository for documentation approval operations with enhanced dashboard support."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_approval(self, approval_data: Dict[str, Any]) -> DocApproval:
        """Create a new documentation approval request."""
        try:
            approval = DocApproval(**approval_data)
            self.session.add(approval)
            await self.session.commit()
            await self.session.refresh(approval)

            logger.info(f"Created doc approval: {approval.id} for {approval.repository}@{approval.commit_hash[:7]}")
            return approval

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating doc approval: {e}", exc_info=True)
            raise DatabaseError(f"Failed to create doc approval: {str(e)}")

    async def get_approval_by_id(self, approval_id: UUID) -> Optional[DocApproval]:
        """Get an approval by ID, including proposal if linked."""
        try:
            query = select(DocApproval).where(DocApproval.id == approval_id)
            result = await self.session.execute(query)
            approval = result.scalar_one_or_none()

            if approval:
                logger.info(f"Found doc approval: {approval_id}")
            else:
                logger.info(f"Doc approval not found: {approval_id}")

            return approval

        except Exception as e:
            logger.error(f"Error fetching doc approval {approval_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to fetch doc approval: {str(e)}")

    async def get_approval_by_pr(self, repo: str, pr_number: int) -> Optional[DocApproval]:
        """Get an approval by repository and PR number."""
        try:
            query = select(DocApproval).where(and_(DocApproval.repository == repo, DocApproval.pr_number == pr_number))
            result = await self.session.execute(query)
            approval = result.scalar_one_or_none()

            if approval:
                logger.info(f"Found doc approval for {repo} PR #{pr_number}")
            else:
                logger.info(f"No approval found for {repo} PR #{pr_number}")

            return approval

        except Exception as e:
            logger.error(f"Error fetching approval for {repo} PR #{pr_number}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to fetch approval by PR: {str(e)}")

    async def get_approval_by_check_run(self, check_run_id: str) -> Optional[DocApproval]:
        """Get an approval by GitHub Check Run ID."""
        try:
            query = select(DocApproval).where(DocApproval.check_run_id == check_run_id)
            result = await self.session.execute(query)
            approval = result.scalar_one_or_none()

            if approval:
                logger.info(f"Found doc approval for Check Run {check_run_id}")
            else:
                logger.info(f"No approval found for Check Run {check_run_id}")

            return approval

        except Exception as e:
            logger.error(f"Error fetching approval by Check Run {check_run_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to fetch approval by Check Run: {str(e)}")

    async def get_pending_approvals(
        self, repo: Optional[str] = None, user_id: Optional[str] = None, include_expired: bool = False
    ) -> List[DocApproval]:
        """Get pending approvals for dashboard display."""
        try:
            query = select(DocApproval).where(DocApproval.status == "pending")

            if repo:
                query = query.where(DocApproval.repository == repo)

            if user_id:
                query = query.where(DocApproval.slack_user_id == user_id)

            if not include_expired:
                # Filter out expired approvals (older than 48 hours by default)
                cutoff_time = datetime.utcnow() - timedelta(hours=48)
                query = query.where(
                    or_(
                        DocApproval.expires_at.is_(None),
                        DocApproval.expires_at > datetime.utcnow(),
                        DocApproval.created_at > cutoff_time,
                    )
                )

            query = query.order_by(DocApproval.created_at.desc())

            result = await self.session.execute(query)
            approvals = result.scalars().all()

            logger.info(f"Found {len(approvals)} pending approvals")
            return list(approvals)

        except Exception as e:
            logger.error(f"Error fetching pending approvals: {e}", exc_info=True)
            raise DatabaseError(f"Failed to fetch pending approvals: {str(e)}")

    async def get_approvals_for_dashboard(
        self, status: Optional[str] = None, repo: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> Dict[str, Any]:
        """Get paginated approvals optimized for dashboard display."""
        try:
            # Build base query
            query = select(DocApproval)
            count_query = select(func.count(DocApproval.id))

            # Apply filters
            if status:
                query = query.where(DocApproval.status == status)
                count_query = count_query.where(DocApproval.status == status)

            if repo:
                query = query.where(DocApproval.repository == repo)
                count_query = count_query.where(DocApproval.repository == repo)

            # Get total count
            count_result = await self.session.execute(count_query)
            total_count = count_result.scalar()

            # Get paginated results
            query = query.order_by(DocApproval.created_at.desc()).limit(limit).offset(offset)

            result = await self.session.execute(query)
            approvals = result.scalars().all()

            # Format for dashboard
            formatted_approvals = []
            for approval in approvals:
                formatted = {
                    "id": str(approval.id),
                    "commit_hash": approval.commit_hash,
                    "repository": approval.repository,
                    "status": approval.status,
                    "pr_number": approval.pr_number,
                    "pr_url": approval.pr_url,
                    "check_run_id": approval.check_run_id,
                    "opened_by": approval.opened_by,
                    "approved_by": approval.approved_by,
                    "approved_at": approval.approved_at.isoformat() if approval.approved_at else None,
                    "created_at": approval.created_at.isoformat() if approval.created_at else None,
                    "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
                    "proposal_id": str(approval.proposal_id) if approval.proposal_id else None,
                }
                formatted_approvals.append(formatted)

            logger.info(f"Retrieved {len(approvals)} approvals for dashboard (total: {total_count})")

            return {
                "approvals": formatted_approvals,
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_count,
            }

        except Exception as e:
            logger.error(f"Error fetching approvals for dashboard: {e}", exc_info=True)
            raise DatabaseError(f"Failed to fetch dashboard approvals: {str(e)}")

    async def approve_request(
        self,
        approval_id: UUID,
        approved_by: str,
        pr_url: Optional[str] = None,
        pr_number: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DocApproval:
        """Approve a documentation request."""
        try:
            approval = await self.get_approval_by_id(approval_id)
            if not approval:
                raise ResourceNotFoundError("DocApproval", str(approval_id))

            if approval.status != "pending":
                raise DatabaseError(f"Cannot approve request with status: {approval.status}")

            approval.status = "approved"
            approval.approved_by = approved_by
            approval.approved_at = datetime.utcnow()
            approval.updated_at = datetime.utcnow()

            if pr_url:
                approval.pr_url = pr_url
            if pr_number:
                approval.pr_number = pr_number

            if metadata:
                if approval.approval_metadata:
                    approval.approval_metadata.update(metadata)
                else:
                    approval.approval_metadata = metadata

            # Update linked proposal if exists
            if approval.proposal_id:
                proposal_update = (
                    update(Proposal)
                    .where(Proposal.id == approval.proposal_id)
                    .values(status="approved", updated_at=datetime.utcnow())
                )
                await self.session.execute(proposal_update)

            await self.session.commit()
            await self.session.refresh(approval)

            logger.info(f"Approved doc request {approval_id} by {approved_by}")
            return approval

        except ResourceNotFoundError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error approving request {approval_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to approve request: {str(e)}")

    async def reject_request(
        self, approval_id: UUID, rejected_by: str, reason: str, metadata: Optional[Dict[str, Any]] = None
    ) -> DocApproval:
        """Reject a documentation request."""
        try:
            approval = await self.get_approval_by_id(approval_id)
            if not approval:
                raise ResourceNotFoundError("DocApproval", str(approval_id))

            if approval.status != "pending":
                raise DatabaseError(f"Cannot reject request with status: {approval.status}")

            approval.status = "rejected"
            approval.approved_by = rejected_by  # Track who rejected
            approval.approved_at = datetime.utcnow()  # Track when
            approval.rejection_reason = reason
            approval.updated_at = datetime.utcnow()

            if metadata:
                if approval.approval_metadata:
                    approval.approval_metadata.update(metadata)
                else:
                    approval.approval_metadata = metadata

            # Update linked proposal if exists
            if approval.proposal_id:
                proposal_update = (
                    update(Proposal)
                    .where(Proposal.id == approval.proposal_id)
                    .values(status="rejected", updated_at=datetime.utcnow())
                )
                await self.session.execute(proposal_update)

            await self.session.commit()
            await self.session.refresh(approval)

            logger.info(f"Rejected doc request {approval_id} by {rejected_by}: {reason}")
            return approval

        except ResourceNotFoundError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error rejecting request {approval_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to reject request: {str(e)}")

    async def update_check_run(
        self, approval_id: UUID, check_run_id: str, head_sha: Optional[str] = None
    ) -> DocApproval:
        """Update Check Run information for an approval."""
        try:
            approval = await self.get_approval_by_id(approval_id)
            if not approval:
                raise ResourceNotFoundError("DocApproval", str(approval_id))

            approval.check_run_id = check_run_id
            if head_sha:
                approval.head_sha = head_sha

            approval.updated_at = datetime.utcnow()

            await self.session.commit()
            await self.session.refresh(approval)

            logger.info(f"Updated Check Run {check_run_id} for approval {approval_id}")
            return approval

        except ResourceNotFoundError:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating Check Run for {approval_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to update Check Run: {str(e)}")

    async def expire_old_approvals(self, hours: int = 48) -> int:
        """Mark old pending approvals as expired."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)

            stmt = (
                update(DocApproval)
                .where(
                    and_(
                        DocApproval.status == "pending",
                        or_(DocApproval.expires_at < datetime.utcnow(), DocApproval.created_at < cutoff_time),
                    )
                )
                .values(status="expired", updated_at=datetime.utcnow())
            )

            result = await self.session.execute(stmt)
            await self.session.commit()

            expired_count = result.rowcount
            logger.info(f"Expired {expired_count} old approvals (>{hours} hours)")
            return expired_count

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error expiring old approvals: {e}", exc_info=True)
            raise DatabaseError(f"Failed to expire approvals: {str(e)}")

    async def get_approval_statistics(self, repo: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        """Get statistics about approvals."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days)

            # Get status counts
            status_query = (
                select(DocApproval.status, func.count(DocApproval.id).label("count"))
                .where(DocApproval.created_at >= cutoff_time)
                .group_by(DocApproval.status)
            )

            if repo:
                status_query = status_query.where(DocApproval.repository == repo)

            status_result = await self.session.execute(status_query)

            stats = {"total": 0, "by_status": {}, "avg_response_time_hours": 0, "approval_rate": 0, "period_days": days}

            for row in status_result:
                stats["by_status"][row.status] = row.count
                stats["total"] += row.count

            # Calculate approval rate
            approved = stats["by_status"].get("approved", 0)
            rejected = stats["by_status"].get("rejected", 0)
            if approved + rejected > 0:
                stats["approval_rate"] = approved / (approved + rejected)

            # Calculate average response time for completed approvals
            response_query = select(
                func.avg(
                    func.extract("epoch", DocApproval.approved_at - DocApproval.created_at) / 3600  # Convert to hours
                ).label("avg_hours")
            ).where(
                and_(
                    DocApproval.created_at >= cutoff_time,
                    DocApproval.status.in_(["approved", "rejected"]),
                    DocApproval.approved_at.isnot(None),
                )
            )

            if repo:
                response_query = response_query.where(DocApproval.repository == repo)

            response_result = await self.session.execute(response_query)
            avg_hours = response_result.scalar()

            if avg_hours:
                stats["avg_response_time_hours"] = float(avg_hours)

            logger.info(f"Generated approval statistics: {stats['total']} approvals in {days} days")
            return stats

        except Exception as e:
            logger.error(f"Error getting approval statistics: {e}", exc_info=True)
            raise DatabaseError(f"Failed to get approval statistics: {str(e)}")
