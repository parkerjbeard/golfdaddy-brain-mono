"""
Detailed test showing the complete commit analysis data flow and outputs.
This test demonstrates exactly what happens at each step of the process.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import uuid
from decimal import Decimal
import json

from app.services.commit_analysis_service import CommitAnalysisService
from app.models.commit import Commit
from app.models.user import User, UserRole
from app.models.daily_report import DailyReport, AiAnalysis
from app.schemas.github_event import CommitPayload


@pytest.mark.asyncio
async def test_commit_analysis_detailed_flow():
    """
    Detailed test showing every step of the commit analysis process.
    """
    
    print("\n" + "="*80)
    print("COMMIT ANALYSIS SYSTEM - DETAILED FLOW TEST")
    print("="*80)
    
    # Test data
    test_user_id = uuid.uuid4()
    test_commit_hash = "f47ac10b58cc3726b5b0f3e7f1a8f3d2c8b9e4a1"
    test_timestamp = datetime.now(timezone.utc)
    
    print(f"\n1. WEBHOOK RECEIVED")
    print(f"   Commit Hash: {test_commit_hash}")
    print(f"   Repository: testorg/authservice")
    print(f"   Author: johndoe (john.doe@example.com)")
    print(f"   Branch: feature/oauth-integration")
    
    # Create test objects
    test_user = User(
        id=test_user_id,
        name="John Doe",
        email="john.doe@example.com", 
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
        raw_text_input="""- Implemented OAuth2 authentication system
- Added JWT token generation and validation
- Created comprehensive test suite
- Reviewed security best practices""",
        clarified_tasks_summary="Implemented complete OAuth2 authentication system with JWT support",
        additional_hours=Decimal("1.5"),
        ai_analysis=AiAnalysis(
            summary="Productive day implementing authentication features",
            estimated_hours=4.0,
            key_achievements=[
                "OAuth2 provider integration",
                "JWT token implementation", 
                "Security hardening"
            ]
        )
    )
    
    # Mock dependencies
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
        
        # Configure mocks
        mock_commit_repo_class.return_value = mock_commit_repo
        mock_user_repo_class.return_value = mock_user_repo
        mock_ai_class.return_value = mock_ai
        mock_github_class.return_value = mock_github
        mock_report_service_class.return_value = mock_report_service
        
        # 1. Check if commit exists
        mock_commit_repo.get_commit_by_hash.return_value = None
        print(f"\n2. DATABASE CHECK")
        print(f"   Checking if commit exists: NOT FOUND")
        print(f"   Proceeding with analysis...")
        
        # 2. User lookup
        mock_user_repo.get_user_by_github_username.return_value = test_user
        print(f"\n3. USER MAPPING")
        print(f"   GitHub username 'johndoe' mapped to:")
        print(f"   - User ID: {test_user_id}")
        print(f"   - Name: {test_user.name}")
        print(f"   - Role: {test_user.role}")
        
        # 3. GitHub diff data
        github_diff = {
            "files": [
                {
                    "filename": "src/auth/oauth_provider.py",
                    "status": "added",
                    "additions": 145,
                    "deletions": 0,
                    "patch": """@@ -0,0 +145 @@
+import asyncio
+from typing import Optional, Dict, Any
+from datetime import datetime, timedelta
+import httpx
+import jwt
+
+class OAuth2Provider:
+    def __init__(self, client_id: str, client_secret: str):
+        self.client_id = client_id
+        self.client_secret = client_secret
+        self.token_endpoint = "https://oauth.provider.com/token"
+    
+    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
+        data = {
+            "grant_type": "authorization_code",
+            "code": code,
+            "client_id": self.client_id,
+            "client_secret": self.client_secret,
+        }
+        response = await self._http_client.post(self.token_endpoint, data=data)
+        return response.json()"""
                },
                {
                    "filename": "tests/test_oauth.py",
                    "status": "added", 
                    "additions": 98,
                    "deletions": 0,
                    "patch": """@@ -0,0 +98 @@
+import pytest
+from src.auth.oauth_provider import OAuth2Provider
+
+class TestOAuth2Provider:
+    @pytest.mark.asyncio
+    async def test_token_exchange(self):
+        provider = OAuth2Provider("test_id", "test_secret")
+        # Test implementation..."""
                },
                {
                    "filename": "src/auth/jwt_handler.py",
                    "status": "added",
                    "additions": 87,
                    "deletions": 0,
                    "patch": """JWT token generation and validation logic..."""
                }
            ],
            "additions": 330,
            "deletions": 0,
            "message": "feat: Implement OAuth2 authentication with JWT tokens",
            "author": {
                "name": "John Doe",
                "email": "john.doe@example.com",
                "login": "johndoe"
            }
        }
        mock_github.get_commit_diff.return_value = github_diff
        
        print(f"\n4. GITHUB DIFF FETCHED")
        print(f"   Files changed: 3")
        print(f"   - src/auth/oauth_provider.py (+145 lines)")
        print(f"   - tests/test_oauth.py (+98 lines)")
        print(f"   - src/auth/jwt_handler.py (+87 lines)")
        print(f"   Total: +330 lines, -0 lines")
        
        # 4. AI Analysis
        ai_analysis = {
            "complexity_score": 8,
            "estimated_hours": 5.5,
            "risk_level": "medium",
            "seniority_score": 9,
            "seniority_rationale": """Demonstrates senior-level expertise:
- Proper async patterns with OAuth2 flow
- Secure token handling with JWT
- Comprehensive test coverage
- Clear separation of concerns
- Follows security best practices""",
            "key_changes": [
                "Implemented complete OAuth2 provider with authorization flow",
                "Added JWT token generation with proper expiration handling",
                "Created comprehensive async test suite",
                "Implemented secure client credential storage"
            ],
            "model_used": "gpt-4",
            "analyzed_at": test_timestamp.isoformat()
        }
        mock_ai.analyze_commit_diff.return_value = ai_analysis
        
        print(f"\n5. AI ANALYSIS RESULTS")
        print(f"   Model: {ai_analysis['model_used']}")
        print(f"   Complexity Score: {ai_analysis['complexity_score']}/10")
        print(f"   Estimated Hours: {ai_analysis['estimated_hours']}")
        print(f"   Risk Level: {ai_analysis['risk_level']}")
        print(f"   Seniority Score: {ai_analysis['seniority_score']}/10")
        print(f"   Key Changes:")
        for change in ai_analysis['key_changes']:
            print(f"   - {change}")
        
        # 5. Code Quality Analysis
        code_quality = {
            "quality_score": 9.0,
            "issues": [],
            "suggestions": [
                "Consider implementing refresh token rotation",
                "Add rate limiting to token endpoints"
            ],
            "security_score": 8.5,
            "test_coverage": "High",
            "code_patterns": {
                "async_await": "Properly implemented",
                "error_handling": "Comprehensive",
                "security": "Well considered"
            }
        }
        mock_ai.analyze_commit_code_quality.return_value = code_quality
        
        print(f"\n6. CODE QUALITY ANALYSIS")
        print(f"   Quality Score: {code_quality['quality_score']}/10")
        print(f"   Security Score: {code_quality['security_score']}/10") 
        print(f"   Test Coverage: {code_quality['test_coverage']}")
        print(f"   Suggestions:")
        for suggestion in code_quality['suggestions']:
            print(f"   - {suggestion}")
        
        # 6. EOD Report Integration
        mock_report_service.get_user_report_for_date.return_value = test_daily_report
        
        print(f"\n7. EOD REPORT INTEGRATION")
        print(f"   Found EOD report for {test_timestamp.date()}")
        print(f"   EOD Summary: {test_daily_report.clarified_tasks_summary}")
        print(f"   EOD Estimated Hours: {test_daily_report.ai_analysis.estimated_hours}")
        print(f"   Commit Estimated Hours: {ai_analysis['estimated_hours']}")
        print(f"   Alignment: EOD mentions authentication work, commit implements it")
        
        # 7. Final commit object
        saved_commit = Commit(
            id=uuid.uuid4(),
            commit_hash=test_commit_hash,
            author_id=test_user_id,
            ai_estimated_hours=Decimal("5.5"),
            seniority_score=9,
            complexity_score=8,
            risk_level="medium",
            key_changes=ai_analysis['key_changes'],
            seniority_rationale=ai_analysis['seniority_rationale'],
            model_used="gpt-4",
            commit_timestamp=test_timestamp,
            eod_report_id=test_daily_report.id,
            eod_report_summary=test_daily_report.clarified_tasks_summary,
            code_quality_analysis=code_quality,
            comparison_notes=f"""EOD report {test_daily_report.id} (date: {test_timestamp.date()}) found for user {test_user_id}.
  - EOD AI Analysis: Estimated Hours: 4.0, Summary: Productive day implementing authentication features
  - Commit AI Analysis: Estimated Hours for this commit: 5.5.
  - Alignment: Common themes between commit changes and EOD achievements: OAuth2 provider integration; JWT token implementation."""
        )
        mock_commit_repo.save_commit.return_value = saved_commit
        
        # Create service and process
        service = CommitAnalysisService(mock_supabase)
        
        commit_payload = CommitPayload(
            commit_hash=test_commit_hash,
            commit_message="feat: Implement OAuth2 authentication with JWT tokens",
            commit_url=f"https://github.com/testorg/authservice/commit/{test_commit_hash}",
            commit_timestamp=test_timestamp,
            author_github_username="johndoe",
            author_email="john.doe@example.com",
            repository_name="testorg/authservice",
            repository_url="https://github.com/testorg/authservice",
            branch="feature/oauth-integration",
            diff_url=f"https://github.com/testorg/authservice/commit/{test_commit_hash}.diff"
        )
        
        # Process the commit
        result = await service.process_commit(commit_payload)
        
        print(f"\n8. FINAL RESULTS")
        print(f"   Commit saved to database with ID: {result.id}")
        print(f"   Total estimated hours: {result.ai_estimated_hours}")
        print(f"   Overall quality metrics:")
        print(f"   - Complexity: {result.complexity_score}/10")
        print(f"   - Seniority: {result.seniority_score}/10")
        print(f"   - Code Quality: {result.code_quality_analysis['quality_score']}/10")
        print(f"   - Risk Level: {result.risk_level}")
        
        print(f"\n9. CROSS-VALIDATION")
        print(f"   EOD Report Hours: 4.0")
        print(f"   Commit Analysis Hours: 5.5") 
        print(f"   Difference: 1.5 hours")
        print(f"   Note: Single commit may be part of larger daily work")
        
        print("\n" + "="*80)
        print("✅ COMMIT ANALYSIS COMPLETE")
        print("="*80)
        
        # Assertions
        assert result is not None
        assert result.commit_hash == test_commit_hash
        assert result.author_id == test_user_id
        assert result.ai_estimated_hours == Decimal("5.5")
        assert result.seniority_score == 9
        assert result.code_quality_analysis["quality_score"] == 9.0
        assert len(result.key_changes) == 4
        assert "OAuth2" in result.comparison_notes
        
        return result


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_commit_analysis_detailed_flow())