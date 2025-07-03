"""
Test commit analysis with REAL OpenAI API calls.
This test demonstrates the actual AI analysis in action.

WARNING: This test will make real API calls to OpenAI and will incur costs!
Only run this test when you want to see actual AI analysis.
"""

import asyncio
import os
from datetime import datetime, timezone
from decimal import Decimal
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the backend directory to the Python path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.integrations.commit_analysis import CommitAnalyzer
from app.config.settings import settings


async def test_real_commit_analysis():
    """
    Test commit analysis with actual OpenAI API calls.
    This shows exactly what the AI returns for real commits.
    """
    
    print("\n" + "="*80)
    print("COMMIT ANALYSIS WITH REAL OPENAI API")
    print("="*80)
    print(f"Using model: {settings.commit_analysis_model}")
    print(f"API Key configured: {'Yes' if settings.openai_api_key else 'No'}")
    
    if not settings.openai_api_key:
        print("\n❌ ERROR: OpenAI API key not configured!")
        print("Please set OPENAI_API_KEY in your .env file")
        return
    
    # Create the analyzer
    analyzer = CommitAnalyzer()
    
    # Example 1: Simple bug fix commit
    print("\n" + "-"*80)
    print("EXAMPLE 1: Simple Bug Fix")
    print("-"*80)
    
    simple_commit = {
        "commit_hash": "abc123",
        "repository": "myapp/backend",
        "message": "fix: Fix null pointer exception in user service",
        "author_name": "John Developer",
        "author_email": "john@example.com",
        "files_changed": ["src/services/user_service.py"],
        "additions": 5,
        "deletions": 2,
        "diff": """diff --git a/src/services/user_service.py b/src/services/user_service.py
index 1234567..abcdefg 100644
--- a/src/services/user_service.py
+++ b/src/services/user_service.py
@@ -45,7 +45,10 @@ class UserService:
     def get_user_profile(self, user_id: str) -> UserProfile:
         user = self.user_repository.get_by_id(user_id)
-        return user.profile  # This was causing NullPointerException
+        if user and user.profile:
+            return user.profile
+        else:
+            raise UserNotFoundError(f"User {user_id} or profile not found")
"""
    }
    
    print(f"Analyzing commit: {simple_commit['message']}")
    result1 = await analyzer.analyze_commit_diff(simple_commit)
    print(f"\nAI Analysis Results:")
    print(json.dumps(result1, indent=2))
    
    # Example 2: Feature implementation
    print("\n" + "-"*80)
    print("EXAMPLE 2: Feature Implementation")
    print("-"*80)
    
    feature_commit = {
        "commit_hash": "def456",
        "repository": "myapp/backend",
        "message": "feat: Add OAuth2 authentication with JWT tokens",
        "author_name": "Jane Developer",
        "author_email": "jane@example.com",
        "files_changed": ["src/auth/oauth.py", "src/auth/jwt_handler.py", "tests/test_auth.py"],
        "additions": 250,
        "deletions": 30,
        "diff": """diff --git a/src/auth/oauth.py b/src/auth/oauth.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/src/auth/oauth.py
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

diff --git a/tests/test_auth.py b/tests/test_auth.py
new file mode 100644
index 0000000..2345678
--- /dev/null
+++ b/tests/test_auth.py
@@ -0,0 +1,55 @@
+import pytest
+from unittest.mock import AsyncMock, patch
+from src.auth.oauth import OAuth2Provider
+
+class TestOAuth2Provider:
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
+        url = await provider.get_authorization_url("test_state", ["read", "write"])
+        assert "client_id=test_client" in url
+        assert "state=test_state" in url
+    
+    @pytest.mark.asyncio
+    async def test_token_exchange(self, provider):
+        with patch.object(provider._http_client, 'post') as mock_post:
+            mock_post.return_value.json.return_value = {
+                "access_token": "test_token",
+                "token_type": "Bearer"
+            }
+            result = await provider.exchange_code_for_token("test_code")
+            assert result["access_token"] == "test_token"
"""
    }
    
    print(f"Analyzing commit: {feature_commit['message']}")
    result2 = await analyzer.analyze_commit_diff(feature_commit)
    print(f"\nAI Analysis Results:")
    print(json.dumps(result2, indent=2))
    
    # Example 3: Complex refactoring
    print("\n" + "-"*80)
    print("EXAMPLE 3: Complex Refactoring")
    print("-"*80)
    
    refactor_commit = {
        "commit_hash": "ghi789",
        "repository": "myapp/backend",
        "message": "refactor: Migrate from synchronous to async database operations",
        "author_name": "Senior Developer",
        "author_email": "senior@example.com", 
        "files_changed": [
            "src/db/connection.py",
            "src/repositories/base.py",
            "src/repositories/user_repo.py",
            "src/services/user_service.py"
        ],
        "additions": 450,
        "deletions": 380,
        "diff": """diff --git a/src/repositories/base.py b/src/repositories/base.py
index 1234567..abcdefg 100644
--- a/src/repositories/base.py
+++ b/src/repositories/base.py
@@ -1,25 +1,35 @@
-from typing import TypeVar, Generic, List, Optional
-from sqlalchemy.orm import Session
+from typing import TypeVar, Generic, List, Optional
+from sqlalchemy.ext.asyncio import AsyncSession
+from sqlalchemy import select, update, delete
 
 T = TypeVar('T')
 
 class BaseRepository(Generic[T]):
-    def __init__(self, session: Session, model_class: type[T]):
+    def __init__(self, session: AsyncSession, model_class: type[T]):
         self.session = session
         self.model = model_class
     
-    def get_by_id(self, id: int) -> Optional[T]:
-        return self.session.query(self.model).filter(self.model.id == id).first()
+    async def get_by_id(self, id: int) -> Optional[T]:
+        result = await self.session.execute(
+            select(self.model).where(self.model.id == id)
+        )
+        return result.scalar_one_or_none()
     
-    def get_all(self) -> List[T]:
-        return self.session.query(self.model).all()
+    async def get_all(self) -> List[T]:
+        result = await self.session.execute(select(self.model))
+        return result.scalars().all()
     
-    def create(self, **kwargs) -> T:
+    async def create(self, **kwargs) -> T:
         instance = self.model(**kwargs)
         self.session.add(instance)
-        self.session.commit()
-        self.session.refresh(instance)
+        await self.session.commit()
+        await self.session.refresh(instance)
         return instance
+    
+    async def update(self, id: int, **kwargs) -> Optional[T]:
+        await self.session.execute(
+            update(self.model).where(self.model.id == id).values(**kwargs)
+        )
+        await self.session.commit()
+        return await self.get_by_id(id)
"""
    }
    
    print(f"Analyzing commit: {refactor_commit['message']}")
    result3 = await analyzer.analyze_commit_diff(refactor_commit)
    print(f"\nAI Analysis Results:")
    print(json.dumps(result3, indent=2))
    
    # Summary
    print("\n" + "="*80)
    print("ANALYSIS SUMMARY")
    print("="*80)
    
    print(f"\n1. Bug Fix: {simple_commit['message']}")
    print(f"   - Estimated Hours: {result1.get('estimated_hours', 'N/A')}")
    print(f"   - Complexity: {result1.get('complexity_score', 'N/A')}/10")
    print(f"   - Seniority: {result1.get('seniority_score', 'N/A')}/10")
    
    print(f"\n2. Feature: {feature_commit['message']}")
    print(f"   - Estimated Hours: {result2.get('estimated_hours', 'N/A')}")
    print(f"   - Complexity: {result2.get('complexity_score', 'N/A')}/10")
    print(f"   - Seniority: {result2.get('seniority_score', 'N/A')}/10")
    
    print(f"\n3. Refactor: {refactor_commit['message']}")
    print(f"   - Estimated Hours: {result3.get('estimated_hours', 'N/A')}")
    print(f"   - Complexity: {result3.get('complexity_score', 'N/A')}/10")
    print(f"   - Seniority: {result3.get('seniority_score', 'N/A')}/10")
    
    print("\n✅ Real API test complete!")
    print("Note: These are actual AI-generated estimates, not mocked data.")


if __name__ == "__main__":
    # Run the async function
    asyncio.run(test_real_commit_analysis())