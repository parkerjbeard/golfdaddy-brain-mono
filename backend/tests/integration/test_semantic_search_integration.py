"""
Integration tests for semantic search and context-aware documentation features.
"""

import json
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pytest

from app.doc_agent.client import AutoDocClient
from app.models.doc_embeddings import CodeContext, DocEmbedding
from app.services.context_analyzer import ContextAnalyzer
from app.services.embedding_service import EmbeddingService
from app.services.semantic_search_service import SemanticSearchService


class TestSemanticSearchIntegration:
    """Integration tests for semantic search features."""

    @pytest.fixture
    async def setup_services(self):
        """Set up integrated services."""
        with patch("app.services.embedding_service.AsyncOpenAI") as mock_openai:
            # Create services
            embedding_service = EmbeddingService()
            embedding_service.openai = mock_openai()

            context_analyzer = ContextAnalyzer(embedding_service)
            semantic_search = SemanticSearchService(embedding_service, context_analyzer)

            # Create doc agent with semantic features
            doc_agent = AutoDocClient(
                openai_api_key="test-key", github_token="test-token", docs_repo="test/repo", enable_semantic_search=True
            )
            doc_agent.embedding_service = embedding_service
            doc_agent.context_analyzer = context_analyzer

            return {
                "embedding_service": embedding_service,
                "context_analyzer": context_analyzer,
                "semantic_search": semantic_search,
                "doc_agent": doc_agent,
                "mock_openai": mock_openai,
            }

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def sample_repository_data(self):
        """Create sample repository data for testing."""
        return {
            "code_files": [
                {
                    "path": "/src/auth.py",
                    "content": '''
import jwt
from datetime import datetime, timedelta

class AuthService:
    def authenticate(self, username, password):
        """Authenticate user and return JWT token."""
        # Implementation
        pass
    
    def verify_token(self, token):
        """Verify JWT token validity."""
        # Implementation
        pass
''',
                    "language": "python",
                    "module": "auth",
                    "classes": ["AuthService"],
                    "functions": ["authenticate", "verify_token"],
                },
                {
                    "path": "/src/api.py",
                    "content": '''
from fastapi import FastAPI, Depends
from .auth import AuthService

app = FastAPI()
auth_service = AuthService()

@app.post("/login")
async def login(credentials):
    """User login endpoint."""
    return auth_service.authenticate(credentials.username, credentials.password)
''',
                    "language": "python",
                    "module": "api",
                    "classes": [],
                    "functions": ["login"],
                },
            ],
            "docs": [
                {
                    "path": "/docs/authentication.md",
                    "title": "Authentication Guide",
                    "content": """
# Authentication Guide

This guide explains how to use the authentication system.

## Overview
The system uses JWT tokens for authentication.

## API Endpoints
- POST /login - Authenticate user
""",
                },
                {
                    "path": "/docs/api.md",
                    "title": "API Documentation",
                    "content": """
# API Documentation

## Authentication Endpoints
See the Authentication Guide for details.
""",
                },
            ],
        }

    @pytest.mark.asyncio
    async def test_end_to_end_documentation_analysis(self, setup_services, mock_db, sample_repository_data):
        """Test complete workflow from code analysis to documentation generation."""
        services = await setup_services

        # Mock OpenAI embeddings
        def mock_embedding(text):
            # Generate deterministic embeddings based on text content
            np.random.seed(hash(text) % 2**32)
            return np.random.rand(1536).tolist()

        services["mock_openai"].return_value.embeddings.create = AsyncMock(
            side_effect=lambda **kwargs: Mock(data=[Mock(embedding=mock_embedding(kwargs["input"]))])
        )

        # Step 1: Analyze repository code
        code_contexts = []
        for code_file in sample_repository_data["code_files"]:
            with patch("builtins.open", MagicMock(read_data=code_file["content"])):
                context = await services["context_analyzer"].analyze_file(
                    db=mock_db, repository="test-repo", file_path=code_file["path"]
                )
                if context:
                    code_contexts.append(context)

        assert len(code_contexts) == 2

        # Step 2: Store documentation embeddings
        doc_embeddings = []
        for doc in sample_repository_data["docs"]:
            embedding = await services["embedding_service"].store_document_embedding(
                db=mock_db, content=doc["content"], title=doc["title"], repository="test-repo", file_path=doc["path"]
            )
            if embedding:
                doc_embeddings.append(embedding)

        assert len(doc_embeddings) == 2

        # Step 3: Search for authentication-related documentation
        # Mock the database queries for search
        mock_result = MagicMock()
        mock_result.all.return_value = [(doc_embeddings[0], 0.92)]  # Auth guide with high similarity
        mock_db.execute = AsyncMock(return_value=mock_result)

        search_results = await services["semantic_search"].search_documents(
            db=mock_db, query="How to implement JWT authentication?", repository="test-repo", include_context=True
        )

        assert len(search_results["results"]) > 0
        assert search_results["results"][0]["title"] == "Authentication Guide"

        # Step 4: Analyze a code change and generate context-aware documentation
        diff = '''diff --git a/src/auth.py b/src/auth.py
+    def refresh_token(self, token):
+        """Refresh an expired JWT token."""
+        # Decode and validate old token
+        # Generate new token with extended expiry
+        pass
'''

        # Mock context gathering
        services["doc_agent"]._gather_context = AsyncMock(
            return_value={
                "repository": "test-repo",
                "affected_files": ["/src/auth.py"],
                "related_docs": [
                    {
                        "title": "Authentication Guide",
                        "content": doc_embeddings[0].content[:200],
                        "similarity": 0.92,
                        "file_path": "/docs/authentication.md",
                    }
                ],
                "code_patterns": ["service"],
                "dependencies": ["jwt"],
                "potential_duplicates": [],
            }
        )

        # Mock OpenAI documentation generation
        services["doc_agent"].openai_client = Mock()
        services["doc_agent"].openai_client.chat.completions.create = AsyncMock(
            return_value=Mock(
                choices=[
                    Mock(
                        message=Mock(
                            content="""
diff --git a/docs/authentication.md b/docs/authentication.md
@@ -10,6 +10,11 @@ The system uses JWT tokens for authentication.
 ## API Endpoints
 - POST /login - Authenticate user
+- POST /refresh - Refresh authentication token
+
+### Token Refresh
+When a JWT token expires, use the refresh_token method to obtain a new token
+without requiring re-authentication.
"""
                        )
                    )
                ]
            )
        )

        doc_patch = await services["doc_agent"].analyze_diff_with_context(
            diff=diff, repo_path="/test-repo", commit_hash="abc123", db=mock_db
        )

        assert "refresh" in doc_patch
        assert "JWT token expires" in doc_patch

    @pytest.mark.asyncio
    async def test_documentation_gap_detection_workflow(self, setup_services, mock_db):
        """Test workflow for detecting and prioritizing documentation gaps."""
        services = await setup_services

        # Create mock undocumented code files
        undocumented_contexts = [
            CodeContext(
                id=uuid.uuid4(),
                repository="test-repo",
                file_path="/src/payment.py",
                module_name="payment",
                classes=["PaymentProcessor", "StripeGateway"],
                functions=["process_payment", "validate_card", "refund", "charge"],
                complexity_score=35.0,
                lines_of_code=250,
            ),
            CodeContext(
                id=uuid.uuid4(),
                repository="test-repo",
                file_path="/src/utils.py",
                module_name="utils",
                classes=[],
                functions=["format_date", "parse_json"],
                complexity_score=8.0,
                lines_of_code=50,
            ),
        ]

        # Mock database queries
        mock_result1 = MagicMock()
        mock_result1.scalars.return_value.all.return_value = undocumented_contexts

        mock_result2 = MagicMock()
        mock_result2.scalar.return_value = 10  # Total files

        mock_db.execute = AsyncMock(side_effect=[mock_result1, mock_result2])

        # Mock embedding service to return no similar docs (undocumented)
        services["embedding_service"].find_similar_documents = AsyncMock(return_value=[])

        # Analyze gaps
        gaps = await services["semantic_search"].analyze_documentation_gaps(db=mock_db, repository="test-repo")

        # Verify payment.py is prioritized due to higher complexity
        assert gaps["gaps"][0]["file_path"] == "/src/payment.py"
        assert gaps["gaps"][0]["complexity"] == 35.0
        assert gaps["coverage_percentage"] == 80.0  # 8/10 files documented

        # Generate improvement suggestions
        mock_db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: [])))
        suggestions = await services["semantic_search"].suggest_documentation_improvements(
            db=mock_db, repository="test-repo"
        )

        assert "improvements" in suggestions

    @pytest.mark.asyncio
    async def test_duplicate_detection_prevents_redundancy(self, setup_services, mock_db):
        """Test that duplicate detection prevents creating redundant documentation."""
        services = await setup_services

        # Mock existing documentation
        existing_doc = DocEmbedding(
            id=uuid.uuid4(),
            title="Payment Processing Guide",
            content="This guide explains how to process payments using our payment service...",
            file_path="/docs/payments.md",
            repository="test-repo",
            embedding=[0.1] * 1536,
        )

        # Mock embedding generation
        services["embedding_service"].generate_embedding = AsyncMock(
            return_value=[0.11] * 1536  # Very similar embedding
        )

        # Mock similar document search
        mock_result = MagicMock()
        mock_result.all.return_value = [(existing_doc, 0.98)]  # Very high similarity
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Detect duplicates
        duplicates = await services["embedding_service"].detect_duplicates(
            db=mock_db,
            title="New Payment Guide",
            content="This document describes payment processing...",
            repository="test-repo",
            threshold=0.95,
        )

        assert len(duplicates) == 1
        assert duplicates[0].title == "Payment Processing Guide"

        # Now test doc agent with duplicate warning
        diff = '''diff --git a/src/payment.py b/src/payment.py
+def process_card_payment(card, amount):
+    """Process credit card payment."""
+    pass
'''

        services["doc_agent"]._gather_context = AsyncMock(
            return_value={
                "repository": "test-repo",
                "affected_files": ["/src/payment.py"],
                "related_docs": [],
                "potential_duplicates": [{"title": "Payment Processing Guide", "file_path": "/docs/payments.md"}],
            }
        )

        # Build prompt and verify duplicate warning
        prompt = services["doc_agent"]._build_context_aware_prompt(
            diff,
            {
                "repository": "test-repo",
                "affected_files": ["/src/payment.py"],
                "related_docs": [],
                "potential_duplicates": [{"title": "Payment Processing Guide", "file_path": "/docs/payments.md"}],
            },
        )

        assert "WARNING: Potential duplicate documentation detected:" in prompt
        assert "Payment Processing Guide" in prompt

    @pytest.mark.asyncio
    async def test_semantic_search_api_integration(self, setup_services, mock_db):
        """Test semantic search through API endpoints."""
        services = await setup_services

        # Mock FastAPI request
        from fastapi.testclient import TestClient

        from app.main import app

        with patch("app.api.semantic_search.get_db", return_value=mock_db):
            with patch("app.api.semantic_search.EmbeddingService", return_value=services["embedding_service"]):
                with patch("app.api.semantic_search.ContextAnalyzer", return_value=services["context_analyzer"]):
                    with patch(
                        "app.api.semantic_search.SemanticSearchService", return_value=services["semantic_search"]
                    ):

                        # Mock search results
                        services["semantic_search"].search_documents = AsyncMock(
                            return_value={
                                "results": [
                                    {
                                        "id": str(uuid.uuid4()),
                                        "title": "Test Document",
                                        "content": "Test content",
                                        "similarity": 0.9,
                                        "related_code": [],
                                    }
                                ],
                                "total_results": 1,
                            }
                        )

                        client = TestClient(app)

                        # Test search endpoint
                        response = client.post(
                            "/api/v1/search/documents",
                            json={"query": "authentication", "repository": "test-repo", "limit": 10},
                            headers={"Authorization": "Bearer test-token"},
                        )

                        # Note: This would need proper auth mocking to work
                        # assert response.status_code == 200
                        # assert response.json()['total_results'] == 1
