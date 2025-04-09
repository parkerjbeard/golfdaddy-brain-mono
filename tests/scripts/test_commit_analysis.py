import sys
import os
from datetime import datetime
import logging
from typing import Dict, Any

# Add the app directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set environment variable to disable auto-database connection
os.environ["TESTING_MODE"] = "True"

from app.services.commit_analysis_service import CommitAnalysisService
from app.integrations.ai_integration import AIIntegration
from app.config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MockDB:
    """Mock database session for testing without a real database."""
    def __init__(self):
        pass
        
    def commit(self):
        pass
        
    def rollback(self):
        pass
        
    def close(self):
        pass
        
    def query(self, *args, **kwargs):
        return MockQuery()
        
class MockQuery:
    """Mock query object that returns None or empty lists."""
    def filter(self, *args, **kwargs):
        return self
        
    def first(self):
        return None
        
    def all(self):
        return []

def analyze_sample_commit():
    """Analyze a sample commit using the CommitAnalysisService."""
    try:
        # Initialize services with mock DB if needed
        mock_db = MockDB()
        commit_service = CommitAnalysisService(db=None)  # Pass None to avoid DB interaction
        ai_integration = AIIntegration()
        
        # Log which model will be used
        logger.info(f"Using model for commit analysis: {settings.commit_analysis_model}")
        logger.info(f"Default OpenAI model: {settings.openai_model}")
        
        # Sample commit data
        sample_commit = {
            "commit_hash": "abc123def456",
            "author_id": "user123",
            "repository": "golfdaddy-brain",
            "branch": "main",
            "commit_message": "Add new point calculation system with AI integration",
            "commit_timestamp": datetime.now(),
            "diff": """
diff --git a/app/services/commit_analysis_service.py b/app/services/commit_analysis_service.py
index 1234567..89abcdef 100644
--- a/app/services/commit_analysis_service.py
+++ b/app/services/commit_analysis_service.py
@@ -1,3 +1,5 @@
 from typing import Dict, Any, Optional, List, Tuple
+from datetime import datetime
+import math
+import json
 
 from app.repositories.commit_repository import CommitRepository
@@ -10,6 +12,7 @@ class CommitAnalysisService:
     def __init__(self, db: Session):
         self.db = db
         self.commit_repository = CommitRepository(db)
+        self.ai_integration = AIIntegration()
         
         # Point calculation coefficients
         self.alpha = 3.0  # Complexity score weight
@@ -20,6 +23,7 @@ class CommitAnalysisService:
         self.risk_factors = {
             "low": 1.0,
             "medium": 1.5,
+            "high": 2.0
         }
""",
            "lines_added": 15,
            "lines_deleted": 3,
            "changed_files": ["app/services/commit_analysis_service.py"],
            "author_name": "John Doe",
            "author_email": "john.doe@example.com"
        }
        
        # First, test AI analysis directly
        logger.info("Testing AI analysis directly...")
        ai_result = ai_integration.analyze_commit_diff(sample_commit)
        logger.info("AI Analysis Result:")
        logger.info(f"Model Used: {ai_result.get('model_used')}")
        logger.info(f"Complexity Score: {ai_result.get('complexity_score')}")
        logger.info(f"Risk Level: {ai_result.get('risk_level')}")
        logger.info(f"Estimated Hours: {ai_result.get('estimated_hours')}")
        logger.info(f"Key Changes: {ai_result.get('key_changes')}")
        logger.info(f"Technical Debt: {ai_result.get('technical_debt')}")
        logger.info(f"Suggestions: {ai_result.get('suggestions')}")
        
        # Then, test full commit analysis
        logger.info("\nTesting full commit analysis...")
        result = commit_service.analyze_commits(sample_commit)
        
        # Log the results
        logger.info("\nCommit Analysis Result:")
        analysis = result.get('analysis', {})
        logger.info("\nAnalysis Details:")
        logger.info(f"AI Points: {analysis.get('ai_points')}")
        logger.info(f"Estimated Hours: {analysis.get('ai_estimated_hours')}")
        logger.info(f"Complexity Score: {analysis.get('complexity_score')}")
        logger.info(f"Risk Level: {analysis.get('risk_level')}")
        logger.info(f"Risk Factor: {analysis.get('risk_factor')}")
        
        # Log point calculation details
        point_calc = analysis.get('point_calculation', {})
        logger.info("\nPoint Calculation Details:")
        logger.info(f"Complexity Component: {point_calc.get('complexity_component')}")
        logger.info(f"Lines Component: {point_calc.get('lines_component')}")
        logger.info(f"Risk Component: {point_calc.get('risk_component')}")
        logger.info(f"Total Points: {point_calc.get('total_points')}")
        
        # Log analysis notes
        logger.info("\nAnalysis Notes:")
        logger.info(analysis.get('ai_analysis_notes'))
        
    except Exception as e:
        logger.error(f"Error during analysis: {str(e)}", exc_info=True)

if __name__ == "__main__":
    analyze_sample_commit() 