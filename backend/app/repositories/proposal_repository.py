"""
Repository for managing documentation change proposals.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError, ResourceNotFoundError
from app.models.proposals import Proposal

logger = logging.getLogger(__name__)


class ProposalRepository:
    """Repository for proposal operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_proposal(self, proposal_data: Dict[str, Any]) -> Proposal:
        """Create a new proposal."""
        try:
            proposal = Proposal(**proposal_data)
            self.session.add(proposal)
            await self.session.commit()
            await self.session.refresh(proposal)

            logger.info(f"Created proposal: {proposal.id} for {proposal.repo}@{proposal.commit[:7]}")
            return proposal

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating proposal: {e}", exc_info=True)
            raise DatabaseError(f"Failed to create proposal: {str(e)}")

    async def get_proposal_by_id(self, proposal_id: UUID) -> Optional[Proposal]:
        """Get a proposal by ID."""
        try:
            query = select(Proposal).where(Proposal.id == proposal_id)
            result = await self.session.execute(query)
            proposal = result.scalar_one_or_none()

            if proposal:
                logger.info(f"Found proposal: {proposal_id}")
            else:
                logger.info(f"Proposal not found: {proposal_id}")

            return proposal

        except Exception as e:
            logger.error(f"Error fetching proposal {proposal_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to fetch proposal: {str(e)}")

    async def get_proposal_by_commit(self, commit: str, repo: str) -> Optional[Proposal]:
        """Get a proposal by commit hash and repository."""
        try:
            query = select(Proposal).where(and_(Proposal.commit == commit, Proposal.repo == repo))
            result = await self.session.execute(query)
            proposal = result.scalar_one_or_none()

            if proposal:
                logger.info(f"Found proposal for {repo}@{commit[:7]}")
            else:
                logger.info(f"No proposal found for {repo}@{commit[:7]}")

            return proposal

        except Exception as e:
            logger.error(f"Error fetching proposal for {repo}@{commit}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to fetch proposal: {str(e)}")

    async def get_proposals_by_status(self, status: str, repo: Optional[str] = None, limit: int = 50) -> List[Proposal]:
        """Get proposals by status, optionally filtered by repository."""
        try:
            query = select(Proposal).where(Proposal.status == status)

            if repo:
                query = query.where(Proposal.repo == repo)

            query = query.order_by(Proposal.created_at.desc()).limit(limit)

            result = await self.session.execute(query)
            proposals = result.scalars().all()

            logger.info(f"Found {len(proposals)} {status} proposals" + (f" for {repo}" if repo else ""))
            return list(proposals)

        except Exception as e:
            logger.error(f"Error fetching proposals by status: {e}", exc_info=True)
            raise DatabaseError(f"Failed to fetch proposals: {str(e)}")

    async def get_pending_proposals(
        self, repo: Optional[str] = None, hours_old: Optional[int] = None
    ) -> List[Proposal]:
        """Get pending proposals, optionally filtered by age."""
        try:
            query = select(Proposal).where(Proposal.status == "pending")

            if repo:
                query = query.where(Proposal.repo == repo)

            if hours_old is not None:
                cutoff_time = datetime.utcnow() - timedelta(hours=hours_old)
                query = query.where(Proposal.created_at >= cutoff_time)

            query = query.order_by(Proposal.created_at.asc())

            result = await self.session.execute(query)
            proposals = result.scalars().all()

            logger.info(f"Found {len(proposals)} pending proposals")
            return list(proposals)

        except Exception as e:
            logger.error(f"Error fetching pending proposals: {e}", exc_info=True)
            raise DatabaseError(f"Failed to fetch pending proposals: {str(e)}")

    async def update_proposal_status(
        self, proposal_id: UUID, status: str, metadata_update: Optional[Dict[str, Any]] = None
    ) -> Optional[Proposal]:
        """Update proposal status and optionally metadata."""
        try:
            proposal = await self.get_proposal_by_id(proposal_id)
            if not proposal:
                raise ResourceNotFoundError("Proposal", str(proposal_id))

            proposal.status = status
            proposal.updated_at = datetime.utcnow()

            if metadata_update:
                if proposal.metadata:
                    proposal.metadata.update(metadata_update)
                else:
                    proposal.metadata = metadata_update

            await self.session.commit()
            await self.session.refresh(proposal)

            logger.info(f"Updated proposal {proposal_id} status to {status}")
            return proposal

        except ResourceNotFoundError:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating proposal status: {e}", exc_info=True)
            raise DatabaseError(f"Failed to update proposal status: {str(e)}")

    async def update_proposal_scores(self, proposal_id: UUID, scores: Dict[str, float]) -> Optional[Proposal]:
        """Update proposal quality scores."""
        try:
            proposal = await self.get_proposal_by_id(proposal_id)
            if not proposal:
                raise ResourceNotFoundError("Proposal", str(proposal_id))

            proposal.scores = scores
            proposal.updated_at = datetime.utcnow()

            await self.session.commit()
            await self.session.refresh(proposal)

            avg_score = proposal.get_total_score()
            logger.info(f"Updated proposal {proposal_id} scores (avg: {avg_score:.2f})")
            return proposal

        except ResourceNotFoundError:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating proposal scores: {e}", exc_info=True)
            raise DatabaseError(f"Failed to update proposal scores: {str(e)}")

    async def expire_old_proposals(self, days: int = 7) -> int:
        """Mark old pending proposals as expired."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days)

            stmt = (
                update(Proposal)
                .where(and_(Proposal.status == "pending", Proposal.created_at < cutoff_time))
                .values(status="expired", updated_at=datetime.utcnow())
            )

            result = await self.session.execute(stmt)
            await self.session.commit()

            expired_count = result.rowcount
            logger.info(f"Expired {expired_count} old proposals (>{days} days)")
            return expired_count

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error expiring old proposals: {e}", exc_info=True)
            raise DatabaseError(f"Failed to expire proposals: {str(e)}")

    async def get_proposal_statistics(self, repo: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        """Get statistics about proposals."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days)
            base_query = select(Proposal).where(Proposal.created_at >= cutoff_time)

            if repo:
                base_query = base_query.where(Proposal.repo == repo)

            # Get status counts
            status_query = (
                select(Proposal.status, func.count(Proposal.id).label("count"))
                .where(Proposal.created_at >= cutoff_time)
                .group_by(Proposal.status)
            )

            if repo:
                status_query = status_query.where(Proposal.repo == repo)

            status_result = await self.session.execute(status_query)

            stats = {
                "total": 0,
                "by_status": {},
                "avg_cost_cents": 0,
                "total_cost_cents": 0,
                "avg_score": 0,
                "period_days": days,
            }

            for row in status_result:
                stats["by_status"][row.status] = row.count
                stats["total"] += row.count

            # Get cost statistics
            cost_query = select(
                func.avg(Proposal.cost_cents).label("avg_cost"), func.sum(Proposal.cost_cents).label("total_cost")
            ).where(Proposal.created_at >= cutoff_time)

            if repo:
                cost_query = cost_query.where(Proposal.repo == repo)

            cost_result = await self.session.execute(cost_query)
            cost_row = cost_result.one()

            if cost_row.avg_cost:
                stats["avg_cost_cents"] = float(cost_row.avg_cost)
            if cost_row.total_cost:
                stats["total_cost_cents"] = int(cost_row.total_cost)

            # Calculate average score for approved proposals
            approved_query = select(Proposal).where(
                and_(Proposal.status == "approved", Proposal.created_at >= cutoff_time, Proposal.scores.isnot(None))
            )

            if repo:
                approved_query = approved_query.where(Proposal.repo == repo)

            approved_result = await self.session.execute(approved_query)
            approved_proposals = approved_result.scalars().all()

            if approved_proposals:
                total_score = sum(p.get_total_score() for p in approved_proposals)
                stats["avg_score"] = total_score / len(approved_proposals)

            logger.info(f"Generated proposal statistics: {stats['total']} proposals in {days} days")
            return stats

        except Exception as e:
            logger.error(f"Error getting proposal statistics: {e}", exc_info=True)
            raise DatabaseError(f"Failed to get proposal statistics: {str(e)}")

    async def delete_proposal(self, proposal_id: UUID) -> bool:
        """Delete a proposal."""
        try:
            proposal = await self.get_proposal_by_id(proposal_id)
            if not proposal:
                raise ResourceNotFoundError("Proposal", str(proposal_id))

            await self.session.delete(proposal)
            await self.session.commit()

            logger.info(f"Deleted proposal: {proposal_id}")
            return True

        except ResourceNotFoundError:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting proposal {proposal_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to delete proposal: {str(e)}")
