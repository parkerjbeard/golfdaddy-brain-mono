"""
Unit tests for the CommitAnalyzer impact scoring functionality.
Tests both traditional hours estimation and new impact scoring system.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import json
from datetime import datetime

from app.integrations.commit_analysis import CommitAnalyzer


class TestCommitAnalyzerImpact:
    """Test the impact scoring functionality of CommitAnalyzer"""

    @pytest_asyncio.fixture
    async def commit_analyzer(self):
        """Create a CommitAnalyzer instance with mocked OpenAI client"""
        with patch('app.config.settings.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.commit_analysis_model = "gpt-4"
            
            analyzer = CommitAnalyzer()
            analyzer.client = AsyncMock()
            return analyzer
    
    @pytest_asyncio.fixture
    def sample_commit_data(self):
        """Sample commit data for testing"""
        return {
            "commit_hash": "abc123",
            "repository": "test-repo",
            "author_name": "Test Author",
            "author_email": "test@example.com",
            "message": "feat: Add payment processing feature",
            "files_changed": ["src/payment.py", "tests/test_payment.py"],
            "additions": 150,
            "deletions": 20,
            "diff": """
diff --git a/src/payment.py b/src/payment.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/src/payment.py
@@ -0,0 +1,150 @@
+import stripe
+from typing import Dict, Any
+
+class PaymentProcessor:
+    def __init__(self, api_key: str):
+        self.stripe = stripe
+        self.stripe.api_key = api_key
+        
+    async def process_payment(self, amount: int, currency: str = "usd") -> Dict[str, Any]:
+        try:
+            intent = await self.stripe.PaymentIntent.create_async(
+                amount=amount,
+                currency=currency
+            )
+            return {"success": True, "intent_id": intent.id}
+        except Exception as e:
+            return {"success": False, "error": str(e)}

diff --git a/tests/test_payment.py b/tests/test_payment.py
new file mode 100644
index 0000000..2345678
--- /dev/null
+++ b/tests/test_payment.py
@@ -0,0 +1,50 @@
+import pytest
+from src.payment import PaymentProcessor

+@pytest.mark.asyncio
+async def test_process_payment_success():
+    processor = PaymentProcessor("test_key")
+    result = await processor.process_payment(1000)
+    assert result["success"] is True
"""
        }

    @pytest.mark.asyncio
    async def test_analyze_commit_impact_scoring(self, commit_analyzer, sample_commit_data):
        """Test that analyze_commit_impact returns correct impact scores"""
        # Mock the OpenAI API response for impact scoring
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "business_value": 8,
            "business_value_reasoning": "Payment processing is a customer-facing feature with direct revenue impact",
            "technical_complexity": 6,
            "technical_complexity_reasoning": "Multi-service integration with external payment provider",
            "code_quality": 1.2,
            "code_quality_reasoning": "Good test coverage and clear documentation",
            "risk_factor": 1.5,
            "risk_factor_reasoning": "High financial risk due to payment handling",
            "impact_score": 64.0,  # (8 * 6 * 1.2) / 1.5 = 38.4 rounded
            "dominant_category": "feature"
        })
        
        commit_analyzer.client.chat.completions.create.return_value = mock_response
        
        # Call the impact scoring method
        result = await commit_analyzer.analyze_commit_impact(sample_commit_data)
        
        # Verify the results
        assert result["business_value"] == 8
        assert result["technical_complexity"] == 6
        assert result["code_quality"] == 1.2
        assert result["risk_factor"] == 1.5
        assert "impact_score" in result
        assert result["dominant_category"] == "feature"
        assert result["scoring_method"] == "impact_points"
        
        # Verify the correct prompt was used
        call_args = commit_analyzer.client.chat.completions.create.call_args
        assert "Impact Points System" in call_args[1]["messages"][1]["content"]
        assert "Business Value Score (1-10)" in call_args[1]["messages"][1]["content"]

    @pytest.mark.asyncio
    async def test_analyze_commit_diff_combined_scoring(self, commit_analyzer, sample_commit_data):
        """Test that analyze_commit_diff returns both hours and impact scores"""
        # Mock the OpenAI API response for hours estimation
        hours_response = MagicMock()
        hours_response.choices = [MagicMock()]
        hours_response.choices[0].message.content = json.dumps({
            "complexity_score": 6,
            "estimated_hours": 3.5,
            "risk_level": "high",
            "seniority_score": 7,
            "seniority_rationale": "Well-structured payment integration with proper error handling",
            "key_changes": ["Payment processor implementation", "Unit tests for payment"]
        })
        
        # Mock the impact scoring response (will be called by analyze_commit_impact)
        impact_response = MagicMock()
        impact_response.choices = [MagicMock()]
        impact_response.choices[0].message.content = json.dumps({
            "business_value": 8,
            "technical_complexity": 6,
            "code_quality": 1.2,
            "risk_factor": 1.5,
            "impact_score": 38.4,
            "dominant_category": "feature"
        })
        
        # Set up the mock to return different responses for each call
        commit_analyzer.client.chat.completions.create.side_effect = [hours_response, impact_response]
        
        # Call the combined analysis method
        result = await commit_analyzer.analyze_commit_diff(sample_commit_data)
        
        # Verify hours estimation fields
        assert result["complexity_score"] == 6
        assert result["estimated_hours"] == 3.5
        assert result["risk_level"] == "high"
        assert result["seniority_score"] == 7
        assert result["key_changes"] == ["Payment processor implementation", "Unit tests for payment"]
        
        # Verify impact scoring fields (prefixed with impact_)
        assert result["impact_business_value"] == 8
        assert result["impact_technical_complexity"] == 6
        assert result["impact_code_quality"] == 1.2
        assert result["impact_risk_factor"] == 1.5
        assert result["impact_score"] == 38.4
        assert result["impact_dominant_category"] == "feature"
        
        # Verify metadata
        assert result["scoring_methods"] == ["hours_estimation", "impact_points"]
        assert "analyzed_at" in result
        assert result["model_used"] == "gpt-4"
        
        # Verify two API calls were made
        assert commit_analyzer.client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_impact_score_calculation(self, commit_analyzer, sample_commit_data):
        """Test that impact score is calculated correctly when not provided by AI"""
        # Mock response without impact_score
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "business_value": 10,
            "technical_complexity": 8,
            "code_quality": 1.5,
            "risk_factor": 2.0,
            "dominant_category": "infrastructure"
        })
        
        commit_analyzer.client.chat.completions.create.return_value = mock_response
        
        result = await commit_analyzer.analyze_commit_impact(sample_commit_data)
        
        # Verify impact score is calculated: (10 * 8 * 1.5) / 2.0 = 60.0
        assert result["impact_score"] == 60.0

    @pytest.mark.asyncio
    async def test_error_handling(self, commit_analyzer, sample_commit_data):
        """Test error handling in impact scoring"""
        # Mock an exception
        commit_analyzer.client.chat.completions.create.side_effect = Exception("API Error")
        
        result = await commit_analyzer.analyze_commit_impact(sample_commit_data)
        
        # Verify error response
        assert result["error"] is True
        assert "API Error" in result["message"]
        assert "timestamp" in result