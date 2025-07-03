"""
Summary test demonstrating the commit analysis functionality.
This test shows the complete flow with proper mocking.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import uuid
from decimal import Decimal

from app.services.commit_analysis_service import CommitAnalysisService
from app.models.commit import Commit
from app.models.user import User, UserRole
from app.models.daily_report import DailyReport, AiAnalysis
from app.schemas.github_event import CommitPayload


@pytest.mark.asyncio
async def test_commit_analysis_complete_flow():
    """
    Test the complete commit analysis flow from webhook to storage.
    This demonstrates how the system:
    1. Receives a commit via webhook
    2. Maps the author to an internal user
    3. Fetches the diff from GitHub
    4. Analyzes it with AI
    5. Integrates with EOD reports
    6. Stores the results
    """
    
    # Test data setup
    test_user_id = uuid.uuid4()
    test_commit_hash = "abc123def456"
    test_timestamp = datetime.now(timezone.utc)
    
    # Create test objects
    test_user = User(
        id=test_user_id,
        name="John Doe",
        email="john@example.com", 
        github_username="johndoe",
        role=UserRole.EMPLOYEE,
        created_at=test_timestamp,
        updated_at=test_timestamp,
        is_active=True
    )
    
    test_daily_report = DailyReport(
        id=uuid.uuid4(),
        user_id=test_user_id,
        report_date=test_timestamp,
        raw_text_input="- Implemented authentication system\n- Added tests",
        clarified_tasks_summary="Implemented authentication system with tests",
        additional_hours=Decimal("2.0"),
        ai_analysis=AiAnalysis(
            summary="Productive day with authentication work",
            estimated_hours=4.0,
            key_achievements=["Authentication system", "Test coverage"]
        )
    )
    
    # Mock all external dependencies
    with patch('app.services.commit_analysis_service.CommitRepository') as mock_commit_repo_class, \
         patch('app.services.commit_analysis_service.UserRepository') as mock_user_repo_class, \
         patch('app.services.commit_analysis_service.AIIntegration') as mock_ai_class, \
         patch('app.services.commit_analysis_service.GitHubIntegration') as mock_github_class, \
         patch('app.services.commit_analysis_service.DailyReportService') as mock_report_service_class, \
         patch('supabase.Client') as mock_supabase:
        
        # Create mock instances
        mock_commit_repo = AsyncMock()
        mock_user_repo = AsyncMock()
        mock_ai = AsyncMock()
        mock_github = MagicMock()
        mock_report_service = AsyncMock()
        
        # Configure mock classes to return mock instances
        mock_commit_repo_class.return_value = mock_commit_repo
        mock_user_repo_class.return_value = mock_user_repo
        mock_ai_class.return_value = mock_ai
        mock_github_class.return_value = mock_github
        mock_report_service_class.return_value = mock_report_service
        
        # Configure mock behaviors
        
        # 1. Commit doesn't exist yet
        mock_commit_repo.get_commit_by_hash.return_value = None
        
        # 2. User lookup succeeds
        mock_user_repo.get_user_by_github_username.return_value = test_user
        
        # 3. GitHub returns diff data
        mock_github.get_commit_diff.return_value = {
            "files": [
                {
                    "filename": "src/auth.py",
                    "status": "added",
                    "additions": 150,
                    "deletions": 20,
                    "patch": """@@ -0,0 +150,20 @@
+class AuthenticationService:
+    def __init__(self):
+        self.jwt_secret = settings.JWT_SECRET
+    
+    def authenticate(self, username, password):
+        # Implementation details...
+        return generate_jwt_token(user)"""
                }
            ],
            "additions": 150,
            "deletions": 20,
            "message": "feat: Add authentication service with JWT support",
            "author": {
                "name": "John Doe",
                "email": "john@example.com",
                "login": "johndoe"
            }
        }
        
        # 4. AI analysis returns results
        mock_ai.analyze_commit_diff.return_value = {
            "complexity_score": 7,
            "estimated_hours": 4.5,
            "risk_level": "medium",
            "seniority_score": 8,
            "seniority_rationale": "Well-structured authentication implementation with proper security considerations and JWT handling",
            "key_changes": [
                "Implemented JWT-based authentication service",
                "Added secure password handling",
                "Created authentication middleware"
            ],
            "model_used": "gpt-4",
            "analyzed_at": test_timestamp.isoformat()
        }
        
        # 5. Code quality analysis
        mock_ai.analyze_commit_code_quality.return_value = {
            "quality_score": 8.5,
            "issues": [],
            "suggestions": ["Consider adding rate limiting to authentication endpoints"]
        }
        
        # 6. Daily report lookup
        mock_report_service.get_user_report_for_date.return_value = test_daily_report
        
        # 7. Save operation succeeds
        saved_commit = Commit(
            id=uuid.uuid4(),
            commit_hash=test_commit_hash,
            author_id=test_user_id,
            ai_estimated_hours=Decimal("4.5"),
            seniority_score=8,
            complexity_score=7,
            risk_level="medium",
            key_changes=[
                "Implemented JWT-based authentication service",
                "Added secure password handling",
                "Created authentication middleware"
            ],
            seniority_rationale="Well-structured authentication implementation with proper security considerations and JWT handling",
            model_used="gpt-4",
            commit_timestamp=test_timestamp,
            eod_report_id=test_daily_report.id,
            eod_report_summary=test_daily_report.clarified_tasks_summary,
            code_quality_analysis={
                "quality_score": 8.5,
                "issues": [],
                "suggestions": ["Consider adding rate limiting to authentication endpoints"]
            },
            comparison_notes="EOD report fbc6dc73-cc85-4a91-8173-89cae6dcac7c"
        )
        mock_commit_repo.save_commit.return_value = saved_commit
        
        # Create service and process commit
        service = CommitAnalysisService(mock_supabase)
        
        # Create commit payload (webhook data)
        commit_payload = CommitPayload(
            commit_hash=test_commit_hash,
            commit_message="feat: Add authentication service with JWT support",
            commit_url=f"https://github.com/org/repo/commit/{test_commit_hash}",
            commit_timestamp=test_timestamp,
            author_github_username="johndoe",
            author_email="john@example.com",
            repository_name="org/repo",
            repository_url="https://github.com/org/repo",
            branch="main",
            diff_url=f"https://github.com/org/repo/commit/{test_commit_hash}.diff"
        )
        
        # Process the commit
        result = await service.process_commit(commit_payload)
        
        # Verify the result
        assert result is not None, "Commit processing should succeed"
        assert result.commit_hash == test_commit_hash
        assert result.author_id == test_user_id
        assert result.ai_estimated_hours == Decimal("4.5")
        assert result.seniority_score == 8
        assert result.complexity_score == 7
        assert result.risk_level == "medium"
        assert len(result.key_changes) == 3
        assert result.eod_report_id == test_daily_report.id
        assert result.code_quality_analysis["quality_score"] == 8.5
        
        # Verify the flow executed correctly
        mock_commit_repo.get_commit_by_hash.assert_called_once_with(test_commit_hash)
        mock_user_repo.get_user_by_github_username.assert_called_once_with("johndoe")
        mock_github.get_commit_diff.assert_called_once_with("org/repo", test_commit_hash)
        mock_ai.analyze_commit_diff.assert_called_once()
        mock_ai.analyze_commit_code_quality.assert_called_once()
        mock_report_service.get_user_report_for_date.assert_called_once()
        mock_commit_repo.save_commit.assert_called_once()
        
        print("\n✅ Commit Analysis Complete Flow Test Passed!")
        print(f"  - Processed commit: {test_commit_hash}")
        print(f"  - Author mapped to user: {test_user.name} ({test_user_id})")
        print(f"  - AI estimated hours: {result.ai_estimated_hours}")
        print(f"  - Seniority score: {result.seniority_score}/10")
        print(f"  - Code quality: {result.code_quality_analysis['quality_score']}/10")
        print(f"  - Integrated with EOD report: {result.eod_report_id}")
        print(f"  - Key changes identified: {len(result.key_changes)}")
        
        return result


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_commit_analysis_complete_flow())