"""
Unit tests for the semantic search and context-aware features of AutoDocClient.
"""

import os
import sys
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))
from app.doc_agent.client import AutoDocClient
from app.models.doc_embeddings import CodeContext, DocEmbedding


class TestAutoDocClientSemantic:
    """Test cases for AutoDocClient semantic features."""

    @pytest.fixture
    def client(self):
        """Create a test client instance with semantic search enabled."""
        with patch("app.doc_agent.client.EmbeddingService") as mock_embedding:
            with patch("app.doc_agent.client.ContextAnalyzer") as mock_context:
                client = AutoDocClient(
                    openai_api_key="test-key",
                    github_token="test-github-token",
                    docs_repo="test-owner/test-repo",
                    enable_semantic_search=True,
                )
                client.embedding_service = mock_embedding()
                client.context_analyzer = mock_context()
                return client

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def sample_context_info(self):
        """Create sample context information."""
        return {
            "repository": "test-repo",
            "commit_hash": "abc123",
            "affected_files": ["/src/auth.py", "/src/api.py"],
            "related_docs": [
                {
                    "title": "Authentication Guide",
                    "content": "This guide explains authentication...",
                    "similarity": 0.92,
                    "file_path": "/docs/auth.md",
                }
            ],
            "code_patterns": ["factory", "singleton"],
            "dependencies": ["requests", "jwt"],
            "conventions": {"naming": "snake_case"},
            "similar_changes": [],
            "potential_duplicates": [],
        }

    @pytest.fixture
    def sample_diff(self):
        """Create a sample git diff."""
        return '''diff --git a/src/auth.py b/src/auth.py
index abc123..def456 100644
--- a/src/auth.py
+++ b/src/auth.py
@@ -10,6 +10,15 @@ class AuthManager:
     def __init__(self):
         self.jwt_secret = settings.JWT_SECRET
     
+    def authenticate_user(self, username: str, password: str) -> Optional[User]:
+        """Authenticate a user with username and password."""
+        user = self.get_user(username)
+        if user and self.verify_password(password, user.password_hash):
+            return user
+        return None
+    
+    def generate_token(self, user: User) -> str:
+        """Generate JWT token for authenticated user."""
+        payload = {"user_id": user.id, "exp": datetime.utcnow() + timedelta(hours=24)}
+        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")
'''

    @pytest.mark.asyncio
    async def test_analyze_diff_with_context_success(self, client, mock_db, sample_diff, sample_context_info):
        """Test context-aware diff analysis."""
        # Mock context gathering
        client._gather_context = AsyncMock(return_value=sample_context_info)

        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[
            0
        ].message.content = """
diff --git a/docs/auth.md b/docs/auth.md
index 123..456 100644
--- a/docs/auth.md
+++ b/docs/auth.md
@@ -5,6 +5,20 @@
 
 The authentication system provides secure user authentication.
 
+## API Methods
+
+### authenticate_user(username, password)
+
+Authenticates a user with their credentials.
+
+**Parameters:**
+- `username` (str): The user's username
+- `password` (str): The user's password
+
+**Returns:**
+- `User` object if authentication succeeds
+- `None` if authentication fails
+
 ## Configuration
"""

        with patch.object(client, "openai_client") as mock_openai:
            mock_chat = AsyncMock()
            mock_openai.chat = mock_chat
            mock_chat.completions.create = AsyncMock(return_value=mock_response)

            result = await client.analyze_diff_with_context(
                diff=sample_diff, repo_path="/test/repo", commit_hash="abc123", db=mock_db
            )

            assert result != ""
            assert "authenticate_user" in result
            mock_chat.completions.create.assert_called_once()

            # Verify context was used in prompt
            call_args = mock_chat.completions.create.call_args
            prompt = call_args[1]["messages"][1]["content"]
            assert "REPOSITORY CONTEXT:" in prompt
            assert "Authentication Guide" in prompt

    @pytest.mark.asyncio
    async def test_analyze_diff_with_context_fallback(self, client, mock_db, sample_diff):
        """Test fallback to regular analysis when context fails."""
        # Mock context gathering failure
        client._gather_context = AsyncMock(side_effect=Exception("Context error"))

        # Mock regular analyze_diff
        client.analyze_diff = AsyncMock(return_value="Regular analysis result")

        result = await client.analyze_diff_with_context(
            diff=sample_diff, repo_path="/test/repo", commit_hash="abc123", db=mock_db
        )

        assert result == "Regular analysis result"
        client.analyze_diff.assert_called_once_with(sample_diff)

    @pytest.mark.asyncio
    async def test_gather_context_comprehensive(self, client, mock_db, sample_diff):
        """Test comprehensive context gathering."""
        # Mock file context
        file_context = {"design_patterns": ["factory"], "dependencies": ["requests"]}
        client.context_analyzer.get_file_context = AsyncMock(return_value=file_context)

        # Mock related documentation
        related_docs = [(Mock(title="Auth Guide", content="Auth content", file_path="/docs/auth.md"), 0.9)]
        client.embedding_service.find_similar_documents = AsyncMock(return_value=related_docs)

        # Mock duplicate detection
        client.embedding_service.detect_duplicates = AsyncMock(return_value=[])

        context = await client._gather_context(
            db=mock_db, repository="test-repo", diff=sample_diff, commit_hash="abc123"
        )

        assert context["repository"] == "test-repo"
        assert context["commit_hash"] == "abc123"
        assert len(context["affected_files"]) > 0
        assert "factory" in context["code_patterns"]
        assert "requests" in context["dependencies"]
        assert len(context["related_docs"]) == 1
        assert context["related_docs"][0]["title"] == "Auth Guide"

    @pytest.mark.asyncio
    async def test_gather_context_with_duplicates(self, client, mock_db, sample_diff):
        """Test context gathering with duplicate detection."""
        # Mock duplicate documents
        duplicate_docs = [Mock(title="Existing Auth Doc", file_path="/docs/existing_auth.md")]
        client.embedding_service.detect_duplicates = AsyncMock(return_value=duplicate_docs)
        client.embedding_service.find_similar_documents = AsyncMock(return_value=[])
        client.context_analyzer.get_file_context = AsyncMock(return_value={})

        context = await client._gather_context(
            db=mock_db, repository="test-repo", diff=sample_diff, commit_hash="abc123"
        )

        assert "potential_duplicates" in context
        assert len(context["potential_duplicates"]) == 1
        assert context["potential_duplicates"][0]["title"] == "Existing Auth Doc"

    def test_summarize_diff(self, client, sample_diff):
        """Test diff summarization."""
        summary = client._summarize_diff(sample_diff)

        assert "Files changed:" in summary
        assert "src/auth.py" in summary
        assert "authenticate_user" in summary or "generate_token" in summary
        assert len(summary) <= 500

    def test_summarize_diff_empty(self, client):
        """Test summarizing empty diff."""
        summary = client._summarize_diff("")
        assert summary == ""

    def test_build_context_aware_prompt(self, client, sample_diff, sample_context_info):
        """Test context-aware prompt building."""
        prompt = client._build_context_aware_prompt(sample_diff, sample_context_info)

        # Check prompt structure
        assert "REPOSITORY CONTEXT:" in prompt
        assert "Repository: test-repo" in prompt
        assert "Affected files: /src/auth.py, /src/api.py" in prompt
        assert "Design patterns used: factory, singleton" in prompt
        assert "Key dependencies: requests, jwt" in prompt

        # Check related documentation section
        assert "RELATED DOCUMENTATION" in prompt
        assert "Authentication Guide" in prompt
        assert "similarity: 0.92" in prompt

        # Check instructions
        assert "CODE DIFF:" in prompt
        assert sample_diff in prompt
        assert "INSTRUCTIONS:" in prompt

    def test_build_context_aware_prompt_with_duplicates(self, client, sample_diff):
        """Test prompt building with duplicate warnings."""
        context = {
            "repository": "test-repo",
            "affected_files": ["/src/auth.py"],
            "code_patterns": [],
            "dependencies": [],
            "related_docs": [],
            "potential_duplicates": [{"title": "Existing Auth Doc", "file_path": "/docs/auth.md"}],
        }

        prompt = client._build_context_aware_prompt(sample_diff, context)

        assert "WARNING: Potential duplicate documentation detected:" in prompt
        assert "Existing Auth Doc at /docs/auth.md" in prompt
        assert "Please ensure updates don't duplicate existing content." in prompt

    @pytest.mark.asyncio
    async def test_check_documentation_coverage(self, client, mock_db):
        """Test documentation coverage checking."""
        # Mock file context
        file_context = {"module_name": "auth", "classes": ["AuthManager"], "functions": ["authenticate", "authorize"]}
        client.context_analyzer.get_file_context = AsyncMock(return_value=file_context)

        # Mock related documentation search
        related_docs = [(Mock(title="Auth Module Docs", file_path="/docs/auth.md"), 0.85)]
        client.embedding_service.find_similar_documents = AsyncMock(return_value=related_docs)

        coverage = await client.check_documentation_coverage(
            db=mock_db, repository="test-repo", file_path="/src/auth.py"
        )

        assert coverage["file_path"] == "/src/auth.py"
        assert coverage["has_documentation"] is True
        assert coverage["coverage_score"] == 0.85
        assert len(coverage["documentation_files"]) == 1
        assert coverage["documentation_files"][0]["title"] == "Auth Module Docs"

    @pytest.mark.asyncio
    async def test_check_documentation_coverage_no_docs(self, client, mock_db):
        """Test coverage check for undocumented file."""
        # Mock file context
        file_context = {
            "module_name": "utils",
            "classes": [],
            "functions": ["helper1", "helper2", "helper3", "helper4", "helper5", "helper6"],
        }
        client.context_analyzer.get_file_context = AsyncMock(return_value=file_context)

        # No related docs found
        client.embedding_service.find_similar_documents = AsyncMock(return_value=[])

        coverage = await client.check_documentation_coverage(
            db=mock_db, repository="test-repo", file_path="/src/utils.py"
        )

        assert coverage["has_documentation"] is False
        assert coverage["coverage_score"] == 0.0
        assert len(coverage["suggestions"]) > 0
        assert any("API documentation" in s for s in coverage["suggestions"])
        assert any("Create initial documentation" in s for s in coverage["suggestions"])

    @pytest.mark.asyncio
    async def test_semantic_search_disabled(self, mock_db):
        """Test that semantic features are disabled when not enabled."""
        client = AutoDocClient(
            openai_api_key="test-key",
            github_token="test-github-token",
            docs_repo="test-owner/test-repo",
            enable_semantic_search=False,
        )

        assert client.embedding_service is None
        assert client.context_analyzer is None

        # Should fall back to regular analysis
        with patch.object(client, "analyze_diff") as mock_analyze:
            mock_analyze.return_value = "Regular analysis"

            result = await client.analyze_diff_with_context(
                diff="some diff", repo_path="/repo", commit_hash="abc123", db=mock_db
            )

            assert result == "Regular analysis"
            mock_analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_aware_analysis_improves_output(self, client, mock_db):
        """Test that context-aware analysis produces better documentation."""
        diff = '''diff --git a/src/payment.py b/src/payment.py
+def process_payment(amount: float, card_token: str) -> PaymentResult:
+    """Process a payment using the provided card token."""
+    # Implementation here
+    pass
'''

        # Mock rich context
        context = {
            "repository": "e-commerce",
            "affected_files": ["/src/payment.py"],
            "related_docs": [
                {
                    "title": "Payment Integration Guide",
                    "content": "Our payment system uses Stripe for processing...",
                    "similarity": 0.88,
                    "file_path": "/docs/payments.md",
                }
            ],
            "code_patterns": ["facade", "factory"],
            "dependencies": ["stripe", "requests"],
            "conventions": {"error_handling": "raise custom exceptions"},
            "similar_changes": [],
            "potential_duplicates": [],
        }

        client._gather_context = AsyncMock(return_value=context)

        # Mock OpenAI to return context-aware documentation
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[
            0
        ].message.content = """
diff --git a/docs/payments.md b/docs/payments.md
+## process_payment
+
+Process a payment transaction using Stripe integration.
+
+This method follows the facade pattern established in our payment system
+and integrates with the existing Stripe configuration described above.
+
+**Parameters:**
+- `amount` (float): Payment amount in dollars
+- `card_token` (str): Stripe card token from frontend
+
+**Returns:**
+- `PaymentResult`: Object containing transaction ID and status
+
+**Raises:**
+- `PaymentException`: Custom exception following our error handling convention
"""

        with patch.object(client, "openai_client") as mock_openai:
            mock_chat = AsyncMock()
            mock_openai.chat = mock_chat
            mock_chat.completions.create = AsyncMock(return_value=mock_response)

            result = await client.analyze_diff_with_context(
                diff=diff, repo_path="/e-commerce", commit_hash="def456", db=mock_db
            )

            # Verify the documentation references existing patterns and docs
            assert "facade pattern" in result
            assert "Stripe" in result
            assert "PaymentException" in result
            assert "error handling convention" in result
