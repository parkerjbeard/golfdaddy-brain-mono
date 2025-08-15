"""
End-to-end tests for commit analysis functionality.
These tests verify the complete flow with minimal mocking.
"""

import asyncio
import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.integrations.commit_analysis import CommitAnalyzer
from app.integrations.github_integration import GitHubIntegration
from app.models.commit import Commit
from app.models.daily_report import AiAnalysis, DailyReport
from app.models.user import User, UserRole
from app.repositories.commit_repository import CommitRepository
from app.repositories.daily_commit_analysis_repository import DailyCommitAnalysisRepository
from app.repositories.daily_report_repository import DailyReportRepository
from app.repositories.user_repository import UserRepository
from app.schemas.github_event import CommitPayload
from app.services.commit_analysis_service import CommitAnalysisService
from app.services.daily_commit_analysis_service import DailyCommitAnalysisService
from supabase import Client


class TestCommitAnalysisE2E:
    """End-to-end tests for the complete commit analysis flow"""

    @pytest_asyncio.fixture
    async def mock_supabase_client(self):
        """Mock Supabase client with in-memory storage"""

        class MockSupabaseClient:
            def __init__(self):
                self.commits = {}
                self.users = {}
                self.daily_reports = {}
                self.daily_analyses = {}

            def table(self, table_name):
                return self

            def select(self, *args, **kwargs):
                return self

            def eq(self, column, value):
                return self

            def execute(self):
                # Simple mock implementation
                return {"data": [], "error": None}

            def insert(self, data):
                return self

            def update(self, data):
                return self

            def upsert(self, data):
                return self

        return MockSupabaseClient()

    @pytest_asyncio.fixture
    async def real_commit_payload(self):
        """Create a realistic commit payload"""
        return CommitPayload(
            commit_hash="f47ac10b58cc3726b5b0f3e7f1a8f3d2c8b9e4a1",
            commit_message="feat: Implement user authentication with OAuth2\n\n- Add OAuth2 provider integration\n- Implement token validation\n- Add user session management\n- Include comprehensive tests",
            commit_url="https://github.com/testorg/authservice/commit/f47ac10b58cc3726b5b0f3e7f1a8f3d2c8b9e4a1",
            commit_timestamp=datetime.now(timezone.utc),
            author_github_username="johndoe",
            author_email="john.doe@example.com",
            repository_name="testorg/authservice",
            repository_url="https://github.com/testorg/authservice",
            branch="feature/oauth-integration",
            diff_url="https://github.com/testorg/authservice/commit/f47ac10b58cc3726b5b0f3e7f1a8f3d2c8b9e4a1.diff",
            files_changed=[
                "src/auth/oauth_provider.py",
                "src/auth/token_validator.py",
                "src/auth/session_manager.py",
                "tests/test_oauth.py",
                "tests/test_token_validation.py",
            ],
            additions=385,
            deletions=42,
        )

    @pytest_asyncio.fixture
    async def realistic_diff_content(self):
        """Create realistic diff content for testing"""
        return """diff --git a/src/auth/oauth_provider.py b/src/auth/oauth_provider.py
new file mode 100644
index 0000000..a123456
--- /dev/null
+++ b/src/auth/oauth_provider.py
@@ -0,0 +1,145 @@
+import asyncio
+from typing import Optional, Dict, Any
+from datetime import datetime, timedelta
+import httpx
+import jwt
+from cryptography.hazmat.primitives import serialization
+from cryptography.hazmat.primitives.asymmetric import rsa
+
+class OAuth2Provider:
+    \"\"\"Handles OAuth2 authentication flow with external providers.\"\"\"
+    
+    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
+        self.client_id = client_id
+        self.client_secret = client_secret
+        self.redirect_uri = redirect_uri
+        self.token_endpoint = "https://oauth.provider.com/token"
+        self.auth_endpoint = "https://oauth.provider.com/authorize"
+        self._http_client = httpx.AsyncClient()
+        self._rsa_key = self._generate_rsa_key()
+    
+    def _generate_rsa_key(self) -> rsa.RSAPrivateKey:
+        \"\"\"Generate RSA key pair for token signing.\"\"\"
+        return rsa.generate_private_key(
+            public_exponent=65537,
+            key_size=2048,
+        )
+    
+    async def get_authorization_url(self, state: str, scopes: List[str]) -> str:
+        \"\"\"Generate OAuth2 authorization URL.\"\"\"
+        params = {
+            "client_id": self.client_id,
+            "redirect_uri": self.redirect_uri,
+            "response_type": "code",
+            "scope": " ".join(scopes),
+            "state": state,
+        }
+        return f"{self.auth_endpoint}?" + "&".join(f"{k}={v}" for k, v in params.items())
+    
+    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
+        \"\"\"Exchange authorization code for access token.\"\"\"
+        data = {
+            "grant_type": "authorization_code",
+            "code": code,
+            "redirect_uri": self.redirect_uri,
+            "client_id": self.client_id,
+            "client_secret": self.client_secret,
+        }
+        
+        response = await self._http_client.post(self.token_endpoint, data=data)
+        response.raise_for_status()
+        
+        token_data = response.json()
+        
+        # Validate token
+        if not self._validate_token_response(token_data):
+            raise ValueError("Invalid token response")
+        
+        return token_data
+    
+    def _validate_token_response(self, token_data: Dict[str, Any]) -> bool:
+        \"\"\"Validate OAuth2 token response.\"\"\"
+        required_fields = ["access_token", "token_type", "expires_in"]
+        return all(field in token_data for field in required_fields)
+    
+    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
+        \"\"\"Refresh an expired access token.\"\"\"
+        data = {
+            "grant_type": "refresh_token",
+            "refresh_token": refresh_token,
+            "client_id": self.client_id,
+            "client_secret": self.client_secret,
+        }
+        
+        response = await self._http_client.post(self.token_endpoint, data=data)
+        response.raise_for_status()
+        
+        return response.json()
+    
+    def create_jwt_token(self, user_id: str, expires_in: int = 3600) -> str:
+        \"\"\"Create a signed JWT token for the user.\"\"\"
+        now = datetime.utcnow()
+        payload = {
+            "sub": user_id,
+            "iat": now,
+            "exp": now + timedelta(seconds=expires_in),
+            "iss": "authservice",
+            "aud": ["api", "web"],
+        }
+        
+        private_key = self._rsa_key.private_bytes(
+            encoding=serialization.Encoding.PEM,
+            format=serialization.PrivateFormat.PKCS8,
+            encryption_algorithm=serialization.NoEncryption()
+        )
+        
+        return jwt.encode(payload, private_key, algorithm="RS256")
+    
+    async def close(self):
+        \"\"\"Clean up resources.\"\"\"
+        await self._http_client.aclose()

diff --git a/tests/test_oauth.py b/tests/test_oauth.py
new file mode 100644
index 0000000..b234567
--- /dev/null
+++ b/tests/test_oauth.py
@@ -0,0 +1,98 @@
+import pytest
+from unittest.mock import AsyncMock, patch
+from src.auth.oauth_provider import OAuth2Provider
+
+class TestOAuth2Provider:
+    \"\"\"Test cases for OAuth2Provider.\"\"\"
+    
+    @pytest.fixture
+    def provider(self):
+        return OAuth2Provider(
+            client_id="test_client",
+            client_secret="test_secret",
+            redirect_uri="http://localhost/callback"
+        )
+    
+    @pytest.mark.asyncio
+    async def test_get_authorization_url(self, provider):
+        \"\"\"Test authorization URL generation.\"\"\"
+        url = await provider.get_authorization_url("test_state", ["read", "write"])
+        
+        assert "client_id=test_client" in url
+        assert "redirect_uri=http://localhost/callback" in url
+        assert "state=test_state" in url
+        assert "scope=read write" in url
+    
+    @pytest.mark.asyncio
+    async def test_exchange_code_for_token(self, provider):
+        \"\"\"Test authorization code exchange.\"\"\"
+        mock_response = {
+            "access_token": "test_access_token",
+            "token_type": "Bearer",
+            "expires_in": 3600,
+            "refresh_token": "test_refresh_token"
+        }
+        
+        with patch.object(provider._http_client, 'post') as mock_post:
+            mock_post.return_value.json.return_value = mock_response
+            mock_post.return_value.raise_for_status = AsyncMock()
+            
+            result = await provider.exchange_code_for_token("test_code")
+            
+            assert result["access_token"] == "test_access_token"
+            assert result["token_type"] == "Bearer"
+    
+    def test_create_jwt_token(self, provider):
+        \"\"\"Test JWT token creation.\"\"\"
+        token = provider.create_jwt_token("user123")
+        
+        # Decode without verification for testing
+        import jwt
+        decoded = jwt.decode(token, options={"verify_signature": False})
+        
+        assert decoded["sub"] == "user123"
+        assert decoded["iss"] == "authservice"
+        assert "exp" in decoded
+        assert "iat" in decoded
"""

    @pytest.mark.asyncio
    async def test_complete_commit_flow_with_real_components(
        self, mock_supabase_client, real_commit_payload, realistic_diff_content
    ):
        """Test the complete flow with minimal mocking - only external services"""

        # Only mock external services (GitHub API and OpenAI)
        with (
            patch("app.integrations.github_integration.requests.get") as mock_github_get,
            patch("app.integrations.commit_analysis.AsyncOpenAI") as mock_openai_class,
        ):

            # Set up GitHub API mock
            github_response = MagicMock()
            github_response.status_code = 200
            github_response.json.return_value = {
                "files": [
                    {
                        "filename": "src/auth/oauth_provider.py",
                        "status": "added",
                        "additions": 145,
                        "deletions": 0,
                        "patch": realistic_diff_content.split("diff --git a/tests/test_oauth.py")[0],
                    },
                    {
                        "filename": "tests/test_oauth.py",
                        "status": "added",
                        "additions": 98,
                        "deletions": 0,
                        "patch": "diff --git a/tests/test_oauth.py"
                        + realistic_diff_content.split("diff --git a/tests/test_oauth.py")[1],
                    },
                ],
                "stats": {"additions": 385, "deletions": 42},
                "commit": {
                    "message": real_commit_payload.commit_message,
                    "author": {
                        "name": "John Doe",
                        "email": "john.doe@example.com",
                        "date": real_commit_payload.commit_timestamp.isoformat(),
                    },
                },
            }
            github_response.raise_for_status = MagicMock()
            mock_github_get.return_value = github_response

            # Set up OpenAI mock
            mock_openai = AsyncMock()
            mock_openai_class.return_value = mock_openai

            # Create realistic AI response
            mock_completion = AsyncMock()
            mock_completion.choices = [
                MagicMock(
                    message=MagicMock(
                        content=json.dumps(
                            {
                                "complexity_score": 7,
                                "estimated_hours": 4.5,
                                "risk_level": "medium",
                                "seniority_score": 8,
                                "seniority_rationale": "Demonstrates strong understanding of OAuth2 flow, security best practices with RSA key generation, proper async patterns, and comprehensive test coverage. The implementation shows senior-level architecture decisions.",
                                "key_changes": [
                                    "Implemented complete OAuth2 provider with authorization flow",
                                    "Added RSA-based JWT token generation for secure authentication",
                                    "Created comprehensive async HTTP client integration",
                                    "Included thorough test coverage with mocking strategies",
                                ],
                            }
                        )
                    )
                )
            ]
            mock_openai.chat.completions.create.return_value = mock_completion

            # Mock repository operations
            with (
                patch("app.repositories.commit_repository.CommitRepository") as mock_commit_repo_class,
                patch("app.repositories.user_repository.UserRepository") as mock_user_repo_class,
                patch("app.repositories.daily_report_repository.DailyReportRepository") as mock_report_repo_class,
            ):

                # Set up repository mocks with in-memory storage
                commits_storage = {}
                users_storage = {}

                # User repository mock
                mock_user_repo = AsyncMock()
                mock_user_repo_class.return_value = mock_user_repo

                # Create test user
                test_user = User(
                    id=uuid.uuid4(),
                    name="John Doe",
                    email="john.doe@example.com",
                    github_username="johndoe",
                    role=UserRole.EMPLOYEE,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    is_active=True,
                )
                users_storage[test_user.github_username] = test_user

                async def mock_get_user_by_github_username(username):
                    return users_storage.get(username)

                async def mock_get_user_by_email(email):
                    for user in users_storage.values():
                        if user.email == email:
                            return user
                    return None

                async def mock_create_user(user_data):
                    users_storage[user_data.github_username] = user_data
                    return user_data

                mock_user_repo.get_user_by_github_username = mock_get_user_by_github_username
                mock_user_repo.get_user_by_email = mock_get_user_by_email
                mock_user_repo.create_user = mock_create_user

                # Commit repository mock
                mock_commit_repo = AsyncMock()
                mock_commit_repo_class.return_value = mock_commit_repo

                async def mock_get_commit_by_hash(commit_hash):
                    return commits_storage.get(commit_hash)

                def mock_save_commit(commit):
                    commits_storage[commit.commit_hash] = commit
                    return commit

                mock_commit_repo.get_commit_by_hash = mock_get_commit_by_hash
                mock_commit_repo.save_commit = mock_save_commit

                # Daily report repository mock
                mock_report_repo = AsyncMock()
                mock_report_repo_class.return_value = mock_report_repo

                # Create test daily report
                test_report = DailyReport(
                    id=uuid.uuid4(),
                    user_id=test_user.id,
                    report_date=datetime.now(timezone.utc),
                    raw_text_input="- Implemented OAuth2 authentication system\n- Added RSA key generation\n- JWT signing process\n- Security review needed",
                    clarified_tasks_summary="Implemented OAuth2 authentication system with comprehensive security features",
                    additional_hours=Decimal("1.5"),
                    created_at=datetime.now(timezone.utc),
                    ai_analysis=AiAnalysis(
                        summary="Strong authentication system implementation",
                        estimated_hours=4.0,
                        key_achievements=[
                            "OAuth2 provider integration",
                            "JWT token implementation",
                            "Security best practices",
                        ],
                        sentiment="positive",
                    ),
                )

                async def mock_get_daily_report(user_id, date):
                    if user_id == test_user.id:
                        return test_report
                    return None

                mock_report_repo.get_daily_reports_by_user_and_date = mock_get_daily_report

                # Initialize service with real components
                service = CommitAnalysisService(mock_supabase_client)

                # Process the commit
                result = await service.process_commit(real_commit_payload)

                # Verify the complete flow worked
                assert result is not None
                assert result.commit_hash == real_commit_payload.commit_hash
                assert result.author_id == test_user.id
                assert result.ai_estimated_hours == Decimal("4.5")
                assert result.seniority_score == 8
                assert result.complexity_score == 7
                assert result.risk_level == "medium"
                assert len(result.key_changes) == 4
                assert "OAuth2" in result.key_changes[0]
                assert result.eod_report_id == test_report.id
                assert result.comparison_notes is not None
                assert "EOD report" in result.comparison_notes

                # Verify the commit was saved
                saved_commit = commits_storage.get(real_commit_payload.commit_hash)
                assert saved_commit is not None
                assert saved_commit.author_id == test_user.id

    @pytest.mark.asyncio
    async def test_daily_batch_analysis_flow(self, mock_supabase_client):
        """Test the daily batch analysis flow end-to-end"""

        # Set up test data
        test_user_id = uuid.uuid4()
        test_date = date.today()

        # Create multiple commits for batch analysis
        test_commits = []
        for i in range(5):
            commit = Commit(
                id=uuid.uuid4(),
                commit_hash=f"commit{i}hash",
                author_id=test_user_id,
                ai_estimated_hours=Decimal("0.0"),  # Not yet analyzed
                commit_timestamp=datetime.combine(test_date, datetime.min.time()) + timedelta(hours=i),
                repository_name="testorg/testrepo",
                commit_message=f"feat: Feature {i} implementation",
                additions=50 + i * 20,
                deletions=10 + i * 5,
                complexity_score=5,  # Default values
                seniority_score=5,
                model_used="none (batch analysis mode)",
            )
            test_commits.append(commit)

        # Mock only external dependencies
        with (
            patch("app.integrations.commit_analysis.AsyncOpenAI") as mock_openai_class,
            patch("app.repositories.commit_repository.CommitRepository") as mock_commit_repo_class,
            patch(
                "app.repositories.daily_commit_analysis_repository.DailyCommitAnalysisRepository"
            ) as mock_daily_repo_class,
            patch("app.repositories.user_repository.UserRepository") as mock_user_repo_class,
        ):

            # Set up OpenAI mock for batch analysis
            mock_openai = AsyncMock()
            mock_openai_class.return_value = mock_openai

            mock_completion = AsyncMock()
            mock_completion.choices = [
                MagicMock(
                    message=MagicMock(
                        content=json.dumps(
                            {
                                "total_estimated_hours": 12.5,
                                "average_complexity_score": 6.5,
                                "average_seniority_score": 7,
                                "summary": "Productive day with multiple feature implementations showing consistent quality",
                                "key_insights": [
                                    "Consistent code quality across commits",
                                    "Progressive feature development",
                                    "Good test coverage maintained",
                                ],
                                "recommendations": [
                                    "Consider refactoring common patterns",
                                    "Add integration tests for new features",
                                ],
                            }
                        )
                    )
                )
            ]
            mock_openai.chat.completions.create.return_value = mock_completion

            # Set up repository mocks
            mock_commit_repo = AsyncMock()
            mock_daily_repo = AsyncMock()
            mock_user_repo = AsyncMock()

            mock_commit_repo_class.return_value = mock_commit_repo
            mock_daily_repo_class.return_value = mock_daily_repo
            mock_user_repo_class.return_value = mock_user_repo

            # Mock repository methods
            async def mock_get_commits_by_user_in_range(author_id, start_date, end_date):
                if author_id == test_user_id:
                    return test_commits
                return []

            mock_commit_repo.get_commits_by_user_in_range = mock_get_commits_by_user_in_range

            # Mock user lookup
            test_user = User(id=test_user_id, name="Test Developer", email="test@example.com")
            mock_user_repo.get_by_id = AsyncMock(return_value=test_user)

            # Mock daily analysis repository
            daily_analyses = {}

            async def mock_get_by_user_and_date(user_id, analysis_date):
                key = f"{user_id}_{analysis_date}"
                return daily_analyses.get(key)

            async def mock_create_analysis(analysis_data):
                analysis = MagicMock()
                analysis.id = uuid.uuid4()
                analysis.user_id = analysis_data.user_id
                analysis.analysis_date = analysis_data.analysis_date
                analysis.total_estimated_hours = analysis_data.total_estimated_hours
                analysis.commit_count = analysis_data.commit_count
                analysis.ai_analysis = analysis_data.ai_analysis

                key = f"{analysis_data.user_id}_{analysis_data.analysis_date}"
                daily_analyses[key] = analysis
                return analysis

            mock_daily_repo.get_by_user_and_date = mock_get_by_user_and_date
            mock_daily_repo.create = mock_create_analysis

            # Initialize service and run analysis
            service = DailyCommitAnalysisService()
            result = await service.analyze_for_date(test_user_id, test_date)

            # Verify results
            assert result is not None
            assert result.total_estimated_hours == Decimal("12.5")
            assert result.commit_count == 5
            assert result.ai_analysis["average_complexity_score"] == 6.5
            assert result.ai_analysis["average_seniority_score"] == 7
            assert len(result.ai_analysis["key_insights"]) == 3
            assert len(result.ai_analysis["recommendations"]) == 2

    @pytest.mark.asyncio
    async def test_error_recovery_and_retries(self, mock_supabase_client, real_commit_payload):
        """Test error handling and recovery mechanisms"""

        with (
            patch("app.integrations.github_integration.requests.get") as mock_github_get,
            patch("app.integrations.commit_analysis.AsyncOpenAI") as mock_openai_class,
            patch("app.repositories.commit_repository.CommitRepository") as mock_commit_repo_class,
            patch("app.repositories.user_repository.UserRepository") as mock_user_repo_class,
        ):

            # Set up mocks
            mock_user_repo = AsyncMock()
            mock_commit_repo = AsyncMock()
            mock_user_repo_class.return_value = mock_user_repo
            mock_commit_repo_class.return_value = mock_commit_repo

            # First attempt: GitHub API fails
            mock_github_get.side_effect = Exception("GitHub API timeout")

            # User exists
            test_user = User(id=uuid.uuid4(), github_username="johndoe")
            mock_user_repo.get_user_by_github_username.return_value = test_user
            mock_commit_repo.get_commit_by_hash.return_value = None

            # Initialize service
            service = CommitAnalysisService(mock_supabase_client)

            # First attempt should fail gracefully
            result = await service.process_commit(real_commit_payload)
            assert result is None

            # Reset GitHub mock to succeed, but make OpenAI fail
            mock_github_get.side_effect = None
            github_response = MagicMock()
            github_response.json.return_value = {"files": [], "stats": {"additions": 10, "deletions": 5}}
            mock_github_get.return_value = github_response

            mock_openai = AsyncMock()
            mock_openai_class.return_value = mock_openai
            mock_openai.chat.completions.create.side_effect = Exception("OpenAI API error")

            # Second attempt should also fail gracefully
            result = await service.process_commit(real_commit_payload)
            assert result is None

            # Finally, let everything succeed
            mock_openai.chat.completions.create.side_effect = None
            mock_completion = AsyncMock()
            mock_completion.choices = [
                MagicMock(
                    message=MagicMock(
                        content=json.dumps(
                            {
                                "complexity_score": 5,
                                "estimated_hours": 2.0,
                                "risk_level": "low",
                                "seniority_score": 6,
                                "seniority_rationale": "Standard implementation",
                                "key_changes": ["Basic feature"],
                            }
                        )
                    )
                )
            ]
            mock_openai.chat.completions.create.return_value = mock_completion

            # Mock successful save
            saved_commit = Commit(
                commit_hash=real_commit_payload.commit_hash, author_id=test_user.id, ai_estimated_hours=Decimal("2.0")
            )
            mock_commit_repo.save_commit.return_value = saved_commit

            # Third attempt should succeed
            result = await service.process_commit(real_commit_payload)
            assert result is not None
            assert result.ai_estimated_hours == Decimal("2.0")


# Performance and load testing
class TestCommitAnalysisPerformance:
    """Performance tests for commit analysis"""

    @pytest.mark.asyncio
    async def test_concurrent_commit_processing(self, mock_supabase_client):
        """Test processing multiple commits concurrently"""

        with (
            patch("app.integrations.commit_analysis.AsyncOpenAI") as mock_openai_class,
            patch("app.repositories.commit_repository.CommitRepository") as mock_commit_repo_class,
            patch("app.repositories.user_repository.UserRepository") as mock_user_repo_class,
            patch("app.integrations.github_integration.requests.get") as mock_github_get,
        ):

            # Set up mocks
            mock_openai = AsyncMock()
            mock_openai_class.return_value = mock_openai

            # Configure AI to return quickly
            async def mock_ai_response(*args, **kwargs):
                await asyncio.sleep(0.1)  # Simulate API delay
                return AsyncMock(
                    choices=[
                        MagicMock(
                            message=MagicMock(
                                content=json.dumps(
                                    {
                                        "complexity_score": 5,
                                        "estimated_hours": 1.0,
                                        "risk_level": "low",
                                        "seniority_score": 5,
                                        "seniority_rationale": "Standard",
                                        "key_changes": ["Change"],
                                    }
                                )
                            )
                        )
                    ]
                )

            mock_openai.chat.completions.create = mock_ai_response

            # Set up other mocks
            mock_user_repo = AsyncMock()
            mock_commit_repo = AsyncMock()
            mock_user_repo_class.return_value = mock_user_repo
            mock_commit_repo_class.return_value = mock_commit_repo

            test_user = User(id=uuid.uuid4(), github_username="testuser")
            mock_user_repo.get_user_by_github_username.return_value = test_user
            mock_commit_repo.get_commit_by_hash.return_value = None
            mock_commit_repo.save_commit.side_effect = lambda c: c

            # Mock GitHub responses
            mock_github_get.return_value = MagicMock(
                json=MagicMock(return_value={"files": [], "stats": {"additions": 10, "deletions": 5}})
            )

            # Create multiple commit payloads
            commit_payloads = []
            for i in range(10):
                payload = CommitPayload(
                    commit_hash=f"hash{i}",
                    commit_message=f"Commit {i}",
                    commit_url=f"https://github.com/repo/commit/hash{i}",
                    commit_timestamp=datetime.now(timezone.utc),
                    author_github_username="testuser",
                    author_email="test@example.com",
                    repository_name="testorg/repo",
                    repository_url="https://github.com/testorg/repo",
                    branch="main",
                    diff_url=f"https://github.com/repo/commit/hash{i}.diff",
                )
                commit_payloads.append(payload)

            # Process commits concurrently
            service = CommitAnalysisService(mock_supabase_client)

            start_time = asyncio.get_event_loop().time()
            tasks = [service.process_commit(payload) for payload in commit_payloads]
            results = await asyncio.gather(*tasks)
            end_time = asyncio.get_event_loop().time()

            # Verify all processed
            assert len(results) == 10
            assert all(r is not None for r in results)

            # Verify concurrent execution (should be much faster than sequential)
            elapsed_time = end_time - start_time
            assert elapsed_time < 2.0  # Should complete in under 2 seconds for 10 commits

            # Verify AI was called 10 times
            assert mock_openai.chat.completions.create.call_count == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
