"""
Integration tests for Batch 2 database layer.
"""

import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

import numpy as np
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.code_symbols import CodeSymbol
from app.models.doc_approval import DocApproval
from app.models.doc_chunks import DocChunk
from app.models.embeddings_meta import EmbeddingsMeta
from app.models.proposals import Proposal
from app.repositories.code_symbol_repository import CodeSymbolRepository
from app.repositories.doc_approval_repository import DocApprovalRepository
from app.repositories.doc_chunk_repository import DocChunkRepository
from app.repositories.proposal_repository import ProposalRepository


@pytest.fixture(scope="function")
async def test_engine():
    """Create a test database engine."""
    # Use in-memory SQLite for testing (or configure test PostgreSQL)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture(scope="function")
async def test_session(test_engine):
    """Create a test database session."""
    async_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session


class TestDocChunkIntegration:
    """Integration tests for DocChunk operations."""

    @pytest.mark.asyncio
    async def test_create_and_retrieve_chunks(self, test_session):
        """Test creating and retrieving document chunks."""
        # Arrange
        repo = DocChunkRepository(test_session)
        chunks_data = [
            {
                "repo": "test-repo",
                "path": "docs/guide.md",
                "heading": "Introduction",
                "order_key": 1,
                "content": "This is the introduction.",
                "embedding": [0.1] * 3072,
            },
            {
                "repo": "test-repo",
                "path": "docs/guide.md",
                "heading": "Getting Started",
                "order_key": 2,
                "content": "Let's get started with the guide.",
                "embedding": [0.2] * 3072,
            },
        ]

        # Act - Create chunks
        created_chunks = await repo.bulk_create_chunks(chunks_data)

        # Assert creation
        assert len(created_chunks) == 2
        assert created_chunks[0].heading == "Introduction"

        # Act - Retrieve chunks
        retrieved_chunks = await repo.get_chunks_by_document("test-repo", "docs/guide.md")

        # Assert retrieval
        assert len(retrieved_chunks) == 2
        assert retrieved_chunks[0].order_key == 1
        assert retrieved_chunks[1].order_key == 2

    @pytest.mark.asyncio
    async def test_upsert_chunks(self, test_session):
        """Test upserting chunks (insert or update)."""
        # Arrange
        repo = DocChunkRepository(test_session)
        initial_data = {
            "repo": "test-repo",
            "path": "docs/api.md",
            "heading": "API",
            "order_key": 1,
            "content": "Initial content",
            "embedding": [0.1] * 3072,
        }

        # Act - Initial insert
        await repo.create_chunk(initial_data)

        # Act - Upsert with updated content
        updated_data = {**initial_data, "content": "Updated content"}
        upserted = await repo.upsert_chunks([updated_data])

        # Assert
        assert len(upserted) == 1
        assert upserted[0].content == "Updated content"

    @pytest.mark.asyncio
    async def test_delete_document_chunks(self, test_session):
        """Test deleting all chunks for a document."""
        # Arrange
        repo = DocChunkRepository(test_session)
        chunks_data = [
            {
                "repo": "test-repo",
                "path": "docs/temp.md",
                "heading": f"Section {i}",
                "order_key": i,
                "content": f"Content {i}",
                "embedding": [0.1] * 3072,
            }
            for i in range(1, 4)
        ]

        # Act - Create chunks
        await repo.bulk_create_chunks(chunks_data)

        # Act - Delete all chunks for document
        deleted_count = await repo.delete_document_chunks("test-repo", "docs/temp.md")

        # Assert
        assert deleted_count == 3

        # Verify deletion
        remaining = await repo.get_chunks_by_document("test-repo", "docs/temp.md")
        assert len(remaining) == 0


class TestCodeSymbolIntegration:
    """Integration tests for CodeSymbol operations."""

    @pytest.mark.asyncio
    async def test_create_and_search_symbols(self, test_session):
        """Test creating and searching code symbols."""
        # Arrange
        repo = CodeSymbolRepository(test_session)
        symbols_data = [
            {
                "repo": "test-repo",
                "path": "src/api.py",
                "lang": "python",
                "kind": "class",
                "name": "APIClient",
                "sig": "class APIClient(BaseClient):",
                "span": {"start": {"line": 10, "col": 0}, "end": {"line": 50, "col": 0}},
                "docstring": "Main API client class.",
                "embedding": [0.1] * 3072,
            },
            {
                "repo": "test-repo",
                "path": "src/api.py",
                "lang": "python",
                "kind": "function",
                "name": "get_user",
                "sig": "def get_user(user_id: str) -> User:",
                "span": {"start": {"line": 60, "col": 0}, "end": {"line": 70, "col": 0}},
                "docstring": "Get user by ID.",
                "embedding": [0.2] * 3072,
            },
        ]

        # Act - Create symbols
        created = await repo.bulk_create_symbols(symbols_data)

        # Assert creation
        assert len(created) == 2

        # Act - Search by name
        found = await repo.search_symbols_by_name("test-repo", "API")

        # Assert search
        assert len(found) == 1
        assert found[0].name == "APIClient"

    @pytest.mark.asyncio
    async def test_get_repo_statistics(self, test_session):
        """Test getting repository statistics."""
        # Arrange
        repo = CodeSymbolRepository(test_session)
        symbols_data = [
            {
                "repo": "test-repo",
                "path": f"src/file{i}.py",
                "lang": "python",
                "kind": kind,
                "name": f"{kind}_{i}",
                "sig": f"{kind} signature",
                "embedding": [0.1] * 3072,
            }
            for i in range(3)
            for kind in ["class", "function"]
        ]

        # Act - Create symbols
        await repo.bulk_create_symbols(symbols_data)

        # Act - Get statistics
        stats = await repo.get_repo_statistics("test-repo")

        # Assert
        assert stats["total_symbols"] == 6
        assert stats["by_kind"]["class"] == 3
        assert stats["by_kind"]["function"] == 3
        assert stats["files_count"] == 3


class TestProposalIntegration:
    """Integration tests for Proposal operations."""

    @pytest.mark.asyncio
    async def test_proposal_lifecycle(self, test_session):
        """Test complete proposal lifecycle."""
        # Arrange
        repo = ProposalRepository(test_session)
        proposal_data = {
            "commit": "abc123def456",
            "repo": "test-repo",
            "patch": "Documentation patch content",
            "targets": ["docs/api.md", "docs/guide.md"],
            "scores": {"relevance": 0.9, "accuracy": 0.85},
            "cost_cents": 25,
        }

        # Act - Create proposal
        proposal = await repo.create_proposal(proposal_data)

        # Assert creation
        assert proposal.status == "pending"
        assert proposal.get_total_score() == 0.875

        # Act - Update status
        updated = await repo.update_proposal_status(
            proposal.id, "approved", {"approver": "user123", "approved_at": datetime.utcnow().isoformat()}
        )

        # Assert update
        assert updated.status == "approved"
        assert updated.metadata["approver"] == "user123"

    @pytest.mark.asyncio
    async def test_expire_old_proposals(self, test_session):
        """Test expiring old proposals."""
        # Arrange
        repo = ProposalRepository(test_session)

        # Create old proposal (manually set created_at)
        old_proposal = Proposal(
            commit="old123",
            repo="test-repo",
            patch="Old patch",
            status="pending",
            created_at=datetime.utcnow() - timedelta(days=10),
        )
        test_session.add(old_proposal)

        # Create recent proposal
        recent_data = {"commit": "recent456", "repo": "test-repo", "patch": "Recent patch", "status": "pending"}
        recent_proposal = await repo.create_proposal(recent_data)

        # Act - Expire proposals older than 7 days
        expired_count = await repo.expire_old_proposals(days=7)

        # Assert
        assert expired_count == 1

        # Verify statuses
        old_updated = await repo.get_proposal_by_commit("old123", "test-repo")
        recent_updated = await repo.get_proposal_by_id(recent_proposal.id)

        assert old_updated.status == "expired"
        assert recent_updated.status == "pending"

    @pytest.mark.asyncio
    async def test_proposal_statistics(self, test_session):
        """Test getting proposal statistics."""
        # Arrange
        repo = ProposalRepository(test_session)

        # Create various proposals
        proposals_data = [
            {
                "commit": f"commit{i}",
                "repo": "test-repo",
                "patch": f"Patch {i}",
                "status": status,
                "cost_cents": 10 + i,
                "scores": {"relevance": 0.8 + i * 0.05} if status == "approved" else None,
            }
            for i, status in enumerate(["pending", "approved", "approved", "rejected"])
        ]

        for data in proposals_data:
            await repo.create_proposal(data)

        # Act - Get statistics
        stats = await repo.get_proposal_statistics(repo="test-repo", days=30)

        # Assert
        assert stats["total"] == 4
        assert stats["by_status"]["pending"] == 1
        assert stats["by_status"]["approved"] == 2
        assert stats["by_status"]["rejected"] == 1
        assert stats["avg_cost_cents"] > 0
        assert stats["avg_score"] > 0


class TestDocApprovalIntegration:
    """Integration tests for DocApproval operations."""

    @pytest.mark.asyncio
    async def test_approval_with_proposal_link(self, test_session):
        """Test approval linked to proposal."""
        # Arrange
        proposal_repo = ProposalRepository(test_session)
        approval_repo = DocApprovalRepository(test_session)

        # Create proposal
        proposal_data = {"commit": "abc123", "repo": "test-repo", "patch": "Documentation updates", "status": "pending"}
        proposal = await proposal_repo.create_proposal(proposal_data)

        # Create approval linked to proposal
        approval_data = {
            "commit_hash": "abc123",
            "repository": "test-repo",
            "diff_content": "Diff content",
            "patch_content": "Patch content",
            "proposal_id": proposal.id,
            "opened_by": "user123",
            "pr_number": 42,
            "check_run_id": "check_123",
        }
        approval = await approval_repo.create_approval(approval_data)

        # Act - Approve the request
        approved = await approval_repo.approve_request(
            approval.id, "manager456", pr_url="https://github.com/test/repo/pull/42", pr_number=42
        )

        # Assert approval
        assert approved.status == "approved"
        assert approved.approved_by == "manager456"

        # Verify proposal was also updated
        updated_proposal = await proposal_repo.get_proposal_by_id(proposal.id)
        assert updated_proposal.status == "approved"

    @pytest.mark.asyncio
    async def test_dashboard_approvals_pagination(self, test_session):
        """Test paginated approvals for dashboard."""
        # Arrange
        repo = DocApprovalRepository(test_session)

        # Create multiple approvals
        for i in range(15):
            approval_data = {
                "commit_hash": f"commit{i:03d}",
                "repository": "test-repo",
                "diff_content": f"Diff {i}",
                "patch_content": f"Patch {i}",
                "status": "pending" if i % 3 == 0 else "approved",
                "pr_number": i,
            }
            await repo.create_approval(approval_data)

        # Act - Get first page
        page1 = await repo.get_approvals_for_dashboard(status="pending", limit=5, offset=0)

        # Assert pagination
        assert len(page1["approvals"]) == 5
        assert page1["total"] == 5  # Total pending
        assert page1["has_more"] is False

    @pytest.mark.asyncio
    async def test_approval_statistics(self, test_session):
        """Test getting approval statistics."""
        # Arrange
        repo = DocApprovalRepository(test_session)

        # Create approvals with different statuses
        base_time = datetime.utcnow()
        approvals_data = [
            {
                "commit_hash": f"commit{i}",
                "repository": "test-repo",
                "diff_content": f"Diff {i}",
                "patch_content": f"Patch {i}",
                "status": status,
                "created_at": base_time - timedelta(hours=i),
                "approved_at": base_time if status in ["approved", "rejected"] else None,
                "approved_by": "user" if status in ["approved", "rejected"] else None,
            }
            for i, status in enumerate(["approved", "approved", "rejected", "pending", "expired"])
        ]

        for data in approvals_data:
            approval = DocApproval(**data)
            test_session.add(approval)

        await test_session.commit()

        # Act - Get statistics
        stats = await repo.get_approval_statistics(repo="test-repo", days=7)

        # Assert
        assert stats["total"] == 5
        assert stats["by_status"]["approved"] == 2
        assert stats["by_status"]["rejected"] == 1
        assert stats["approval_rate"] == 2 / 3  # 2 approved out of 3 decided
        assert stats["avg_response_time_hours"] >= 0


class TestEmbeddingsMetaIntegration:
    """Integration tests for EmbeddingsMeta operations."""

    @pytest.mark.asyncio
    async def test_embeddings_meta_tracking(self, test_session):
        """Test tracking embedding model metadata."""
        # Arrange
        meta = EmbeddingsMeta(model="text-embedding-3-large", dim=3072)

        # Act
        test_session.add(meta)
        await test_session.commit()

        # Query back
        result = await test_session.execute(
            text("SELECT * FROM embeddings_meta WHERE model = :model"), {"model": "text-embedding-3-large"}
        )
        row = result.first()

        # Assert
        assert row is not None
        assert row.dim == 3072
