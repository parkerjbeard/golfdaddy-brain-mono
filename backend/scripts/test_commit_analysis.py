import sys
import os
from datetime import datetime, date, timedelta
import logging
from typing import Dict, Any, Optional, List, Union
import asyncio
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4, UUID
from decimal import Decimal

# Add the app directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set environment variable to disable auto-database connection
os.environ["TESTING_MODE"] = "True"
# Set necessary settings for testing
os.environ["OPENAI_API_KEY"] = "test-openai-key" # Required by integrations
os.environ["GITHUB_TOKEN"] = "test-github-token" # Required by integrations
os.environ["DOCS_REPOSITORY"] = "testowner/test-docs-repo"
os.environ["ENABLE_DOCS_UPDATES"] = "True"
os.environ["COMMIT_ANALYSIS_MODEL"] = "gpt-4-test" # Example model
os.environ["OPENAI_MODEL"] = "gpt-3.5-turbo-test" # Example model

# Mock settings before importing modules that use them
from unittest import mock
mock_settings = mock.Mock()
mock_settings.openai_api_key = "test-openai-key"
mock_settings.github_token = "test-github-token"
mock_settings.docs_repository = "testowner/test-docs-repo"
mock_settings.enable_docs_updates = True
mock_settings.reanalyze_existing_commits = False
mock_settings.commit_analysis_model = "o4-mini-test" # A model likely to exist
mock_settings.openai_model = "gpt-3.5-turbo-test" # A model likely to exist

with mock.patch('app.config.settings', mock_settings):
    from app.services.commit_analysis_service import CommitAnalysisService
    from app.integrations.ai_integration import AIIntegration # Imports CommitAnalyzer
    from app.integrations.github_integration import GitHubIntegration
    from app.repositories.commit_repository import CommitRepository
    from app.repositories.user_repository import UserRepository
    from app.services.daily_report_service import DailyReportService
    from app.services.documentation_update_service import DocumentationUpdateService
    from app.models.commit import Commit
    from app.models.user import User
    from app.models.daily_report import DailyReport, EODReportAnalysis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Mocks ---

class MockSupabaseClient:
    def __init__(self):
        logger.info("MockSupabaseClient initialized.")
        self.storage = {} # Simple key-value store for tables
        self.table_name = None
        self._query_filters = {}
        self._select_cols = "*"
        self._insert_data = None
        self._upsert_data = None
        self._on_conflict = None
        self._returning = "representation"
        self._maybe_single = False

    def table(self, table_name: str):
        logger.info(f"MockSupabaseClient: Using table '{table_name}'")
        self.table_name = table_name
        if table_name not in self.storage:
            self.storage[table_name] = {} # Use dict as {primary_key: record}
        # Reset query state
        self._query_filters = {}
        self._select_cols = "*"
        self._insert_data = None
        self._upsert_data = None
        self._on_conflict = None
        self._maybe_single = False
        return self

    def from_(self, table_name: str): # Added from_ to bypass RLS like in repo
        return self.table(table_name)

    def select(self, *args, **kwargs):
        self._select_cols = args[0] if args else "*"
        logger.info(f"MockSupabaseClient: Selecting '{self._select_cols}' from {self.table_name}")
        return self

    def eq(self, column: str, value: Any):
        logger.info(f"MockSupabaseClient: eq filter on {self.table_name}: {column} == {value}")
        self._query_filters[column] = value
        return self

    def gte(self, column: str, value: Any):
        logger.info(f"MockSupabaseClient: gte filter on {self.table_name}: {column} >= {value}")
        self._query_filters[column] = lambda x: x >= value
        return self

    def lt(self, column: str, value: Any):
        logger.info(f"MockSupabaseClient: lt filter on {self.table_name}: {column} < {value}")
        self._query_filters[column] = lambda x: x < value
        return self

    def order(self, column: str, desc: bool = False):
        logger.info(f"MockSupabaseClient: order by {column} {'DESC' if desc else 'ASC'} (mock does not implement sorting)")
        return self # Mock doesn't actually sort

    def maybe_single(self):
        logger.info(f"MockSupabaseClient: maybe_single() called on {self.table_name}")
        self._maybe_single = True
        return self # Return self, execute will handle the logic

    def insert(self, data: Union[Dict[str, Any], List[Dict[str, Any]]], returning: Any = "representation"):
        logger.info(f"MockSupabaseClient: insert called for {self.table_name}")
        self._insert_data = data if isinstance(data, list) else [data]
        self._returning = returning
        return self

    def upsert(self, data: Union[Dict[str, Any], List[Dict[str, Any]]], on_conflict: Optional[str] = None, returning: Any = "representation"):
        logger.info(f"MockSupabaseClient: upsert called for {self.table_name}, on_conflict={on_conflict}")
        self._upsert_data = data if isinstance(data, list) else [data]
        self._on_conflict = on_conflict
        self._returning = returning
        return self

    def delete(self):
        logger.info(f"MockSupabaseClient: delete called for {self.table_name}")
        # Filters should be set via .eq() before calling execute
        return self

    def _apply_filters(self, record: Dict[str, Any]) -> bool:
        for col, condition in self._query_filters.items():
            if col not in record: return False
            value = record[col]
            if callable(condition):
                if not condition(value): return False
            elif value != condition:
                return False
        return True

    def execute(self):
        logger.info(f"MockSupabaseClient: execute() called on {self.table_name}")
        response_data = []
        error = None

        try:
            if self._insert_data:
                table_store = self.storage.setdefault(self.table_name, {})
                for item in self._insert_data:
                    new_item = {**item}
                    pk = new_item.get('id') or new_item.get('commit_hash') or str(uuid4()) # Assume some PK
                    if pk in table_store:
                         # Basic simulation of constraint violation for insert
                         raise ValueError(f"Duplicate key value violates unique constraint for key {pk}")
                    new_item.setdefault('id', str(uuid4()))
                    new_item.setdefault('created_at', datetime.now().isoformat())
                    table_store[pk] = new_item
                    response_data.append(new_item)

            elif self._upsert_data:
                table_store = self.storage.setdefault(self.table_name, {})
                conflict_col = self._on_conflict or 'id' # Default to 'id' if not specified
                for item in self._upsert_data:
                    new_item = {**item}
                    conflict_key = new_item.get(conflict_col)

                    # Find existing based on conflict key
                    existing_pk = None
                    for pk, record in table_store.items():
                        if record.get(conflict_col) == conflict_key:
                            existing_pk = pk
                            break

                    if existing_pk: # Update
                        table_store[existing_pk].update(new_item)
                        table_store[existing_pk]['updated_at'] = datetime.now().isoformat()
                        response_data.append(table_store[existing_pk])
                    else: # Insert
                        pk = new_item.get('id') or conflict_key or str(uuid4())
                        new_item.setdefault('id', str(uuid4()))
                        new_item.setdefault('created_at', datetime.now().isoformat())
                        table_store[pk] = new_item
                        response_data.append(new_item)

            elif self._query_filters and not self._maybe_single: # Select with filters (or delete)
                 table_store = self.storage.get(self.table_name, {})
                 response_data = [record for record in table_store.values() if self._apply_filters(record)]
                 # Handle delete case (filter applied)
                 if hasattr(self, '_delete_marker'): # Check if delete was intended
                     keys_to_delete = [pk for pk, record in table_store.items() if self._apply_filters(record)]
                     for key in keys_to_delete:
                         del table_store[key]
                     response_data = [{"message": f"Deleted {len(keys_to_delete)} rows"}] # Simulate delete response
                     delattr(self, '_delete_marker')

            elif self._query_filters and self._maybe_single: # Select with filter for single result
                table_store = self.storage.get(self.table_name, {})
                found = None
                for record in table_store.values():
                    if self._apply_filters(record):
                        found = record
                        break
                response_data = found # maybe_single returns the dict directly or None

            else: # Select all (no filters)
                response_data = list(self.storage.get(self.table_name, {}).values())

        except Exception as e:
            logger.error(f"MockSupabaseClient execute error: {e}")
            error = MagicMock()
            error.message = str(e)
            # Simulate Supabase structure where data is None/empty on error
            response_data = None if self._maybe_single else []


        # Construct response object similar to supabase-py
        response = MagicMock()
        response.data = response_data
        response.error = error
        response.status_code = 400 if error else (200 if response_data or self._maybe_single and response_data is not None else 404)

        # Reset state for next call chain
        self._insert_data = None
        self._upsert_data = None
        self._query_filters = {}
        self._maybe_single = False
        self._on_conflict = None

        logger.info(f"MockSupabaseClient execute result: data={response.data}, error={response.error}")
        return response


# --- Test Setup ---

# Sample data
sample_commit_hash = "abc123def456xyz789"
sample_repo_name = "testowner/test-repo"
sample_author_email = "test.author@example.com"
sample_author_name = "Test Author"
sample_github_username = "test-author-gh"
sample_user_id = uuid4()
sample_eod_report_id = uuid4()
sample_commit_timestamp = datetime.now()

# Create a realistic sample diff
sample_diff = '''diff --git a/src/calculator.py b/src/calculator.py
index e69de29..ba7c3cf 100644
--- a/src/calculator.py
+++ b/src/calculator.py
@@ -0,0 +1,11 @@
+class Calculator:
+    def add(self, a, b):
+        """Adds two numbers."""
+        return a + b
+
+    def subtract(self, a, b):
+        """Subtracts second number from first."""
+        return a - b
+
+    def multiply(self, a, b):
+        """Multiplies two numbers."""
+        return a * b
'''

sample_commit_payload_dict = {
    "commit_hash": sample_commit_hash,
    "repository_name": sample_repo_name,
    "author_email": sample_author_email,
    "author_name": sample_author_name,
    "author_github_username": sample_github_username,
    "commit_timestamp": sample_commit_timestamp.isoformat(),
    "commit_message": "Feat: Add multiply operation to calculator",
    "files_changed": ["src/calculator.py"],
    "additions": 11,
    "deletions": 0,
    "commit_diff": sample_diff
}

# AI Analysis Mock Response (Original)
mock_ai_commit_analysis = {
    "complexity_score": 5,
    "estimated_hours": 1.5,
    "risk_level": "low",
    "seniority_score": 7,
    "seniority_rationale": "Clear implementation, follows standard patterns.",
    "key_changes": ["Added multiply method", "Included docstrings"],
    "analyzed_at": datetime.now().isoformat(),
    "model_used": "o4-mini-test",
    "commit_hash": sample_commit_hash,
    "repository": sample_repo_name
}

# AI Code Quality Mock Response
mock_ai_code_quality_analysis = {
    "model_used": "gpt-3.5-turbo-test",
    "readability_score": 8,
    "complexity_score": 3, # Different from commit analysis complexity
    "maintainability_score": 9,
    "test_coverage_estimation": "medium",
    "estimated_seniority_level": "mid",
    "security_concerns": [],
    "performance_issues": [],
    "best_practices_adherence": ["Clear variable names", "Docstrings present"],
    "suggestions_for_improvement": ["Consider adding type hints"],
    "positive_feedback": ["Well-structured code"],
    "overall_assessment_summary": "Good quality code for the feature.",
    "error": None # Explicitly indicate no error
}

# Mock User
mock_user = User(id=sample_user_id, email=sample_author_email, role="developer", team="core", created_at=datetime.now())

# Mock EOD Report
mock_eod_report = DailyReport(
    id=sample_eod_report_id,
    user_id=sample_user_id,
    report_date=sample_commit_timestamp.date(),
    raw_text_input="Worked on calculator feature, added multiplication.",
    ai_analysis=EODReportAnalysis(
        summary="Completed multiplication feature for calculator.",
        estimated_hours=Decimal('2.0'), # Example value
        key_achievements=["Added multiply method", "Wrote tests"],
        blockers=[],
        sentiment="positive",
        confidence_score=0.9
    ),
    created_at=datetime.now()
)

# Mock Documentation Analysis
mock_docs_analysis = {
    "changes_needed": True,
    "proposed_changes": [
        {"file_path": "docs/calculator.md", "content": "Updated documentation for multiply."}
    ]
}

mock_docs_pr_result = {
    "status": "success",
    "pull_request_url": f"https://github.com/{mock_settings.docs_repository}/pull/123"
}


async def run_test_analysis():
    """Runs the commit analysis test with mocks."""
    logger.info("--- Starting Test Analysis ---")

    # --- Setup Mocks ---
    mock_supabase_client = MockSupabaseClient()
    mock_user_repo = AsyncMock(spec=UserRepository)
    mock_commit_repo = MagicMock(spec=CommitRepository) # Uses sync methods
    mock_ai_integration = AsyncMock(spec=AIIntegration)
    mock_github_integration = MagicMock(spec=GitHubIntegration)
    mock_daily_report_service = AsyncMock(spec=DailyReportService)
    mock_docs_update_service = MagicMock(spec=DocumentationUpdateService) # Sync methods used in _scan_documentation

    # Configure mock return values
    mock_user_repo.get_user_by_email.return_value = mock_user
    mock_commit_repo.get_commit_by_hash.return_value = None # Simulate commit not existing initially
    # Simulate save_commit returning a Commit object based on input
    def mock_save_commit(commit_obj: Commit) -> Commit:
         # Add simulated DB fields if not present
        commit_obj.id = commit_obj.id or uuid4()
        commit_obj.created_at = commit_obj.created_at or datetime.now()
        commit_obj.updated_at = datetime.now()
        # Ensure Decimal type for hours
        if commit_obj.ai_estimated_hours is not None and not isinstance(commit_obj.ai_estimated_hours, Decimal):
             commit_obj.ai_estimated_hours = Decimal(str(commit_obj.ai_estimated_hours)).quantize(Decimal('0.1'))
        return commit_obj
    mock_commit_repo.save_commit.side_effect = mock_save_commit

    mock_ai_integration.analyze_commit_diff.return_value = mock_ai_commit_analysis
    mock_ai_integration.analyze_commit_code_quality.return_value = mock_ai_code_quality_analysis
    mock_github_integration.get_commit_diff.return_value = { # Needed if fetch_diff=True is tested
        "diff": sample_diff, "files_changed": ["src/calculator.py"], "additions": 11, "deletions": 0,
        "message": "Feat: Add multiply operation", "author": {"name": sample_author_name, "email": sample_author_email, "date": sample_commit_timestamp.isoformat()}
    }
    mock_daily_report_service.get_user_report_for_date.return_value = mock_eod_report
    mock_docs_update_service.analyze_documentation.return_value = mock_docs_analysis
    mock_docs_update_service.create_pull_request.return_value = mock_docs_pr_result

    # --- Instantiate Service ---
    # Need to inject mocks manually since we're not using a DI framework
    commit_service = CommitAnalysisService(supabase=mock_supabase_client)
    commit_service.user_repository = mock_user_repo
    # Instantiate real CommitRepository but give it the mock client
    commit_service.commit_repository = CommitRepository(client=mock_supabase_client)
    commit_service.ai_integration = mock_ai_integration
    commit_service.github_integration = mock_github_integration
    commit_service.daily_report_service = mock_daily_report_service
    # Instantiate real DocsUpdateService, assuming it doesn't need complex mocks for this test
    # If it makes external calls (e.g., GitHub API), those parts would need mocking too.
    try:
        commit_service.docs_update_service = DocumentationUpdateService()
        # If DocumentationUpdateService has dependencies, mock them here or mock the service itself as before
        commit_service.docs_update_service.analyze_documentation = mock_docs_update_service.analyze_documentation
        commit_service.docs_update_service.create_pull_request = mock_docs_update_service.create_pull_request
    except Exception as e:
        logger.warning(f"Could not instantiate real DocumentationUpdateService, using full mock: {e}")
        commit_service.docs_update_service = mock_docs_update_service # Fallback to full mock


    # --- Run Test ---
    logger.info(f"\n----- Testing CommitAnalysisService.process_commit for {sample_commit_hash} -----")
    analyzed_commit_object: Optional[Commit] = await commit_service.process_commit(
        commit_data_input=sample_commit_payload_dict,
        scan_docs=True # Force docs scan for testing
    )

    # --- Assertions and Verification ---
    logger.info("\n----- Verifying Results -----")

    assert analyzed_commit_object is not None, "process_commit should return a Commit object"
    assert analyzed_commit_object.commit_hash == sample_commit_hash
    assert analyzed_commit_object.author_id == sample_user_id
    # Check if 'repository_name' attribute exists and matches
    assert getattr(analyzed_commit_object, 'repository_name', None) == sample_repo_name, f"Commit object repository_name mismatch or missing. Got: {getattr(analyzed_commit_object, 'repository_name', 'N/A')}"

    assert analyzed_commit_object.ai_points == mock_ai_commit_analysis["complexity_score"]
    # Compare Decimal values carefully
    expected_hours = Decimal(str(mock_ai_commit_analysis["estimated_hours"])).quantize(Decimal('0.1'))
    assert analyzed_commit_object.ai_estimated_hours == expected_hours, f"Expected hours {expected_hours}, got {analyzed_commit_object.ai_estimated_hours}"
    assert analyzed_commit_object.seniority_score == mock_ai_commit_analysis["seniority_score"]
    assert analyzed_commit_object.commit_timestamp.date() == sample_commit_timestamp.date()
    assert analyzed_commit_object.complexity_score == mock_ai_commit_analysis["complexity_score"]
    assert analyzed_commit_object.risk_level == mock_ai_commit_analysis["risk_level"]
    assert analyzed_commit_object.key_changes == mock_ai_commit_analysis["key_changes"]
    assert analyzed_commit_object.seniority_rationale == mock_ai_commit_analysis["seniority_rationale"]
    assert analyzed_commit_object.model_used == mock_ai_commit_analysis["model_used"]
    assert analyzed_commit_object.analyzed_at is not None

    # Verify EOD integration fields
    assert analyzed_commit_object.eod_report_id == sample_eod_report_id
    assert mock_eod_report.ai_analysis.summary in analyzed_commit_object.eod_report_summary
    assert analyzed_commit_object.comparison_notes is not None, "Comparison notes should not be None"
    assert "Comparison Notes:" in analyzed_commit_object.comparison_notes
    assert f"EOD report {sample_eod_report_id}" in analyzed_commit_object.comparison_notes
    assert f"EOD AI Analysis: Estimated Hours: {mock_eod_report.ai_analysis.estimated_hours:.2f}" in analyzed_commit_object.comparison_notes

    # Verify Code Quality integration fields
    assert analyzed_commit_object.code_quality_analysis is not None
    assert analyzed_commit_object.code_quality_analysis["model_used"] == mock_ai_code_quality_analysis["model_used"]
    assert analyzed_commit_object.code_quality_analysis["readability_score"] == mock_ai_code_quality_analysis["readability_score"]
    assert analyzed_commit_object.code_quality_analysis["overall_assessment_summary"] == mock_ai_code_quality_analysis["overall_assessment_summary"]

    # Verify mock calls
    commit_service.commit_repository._client.from_.assert_called_with('commits') # Check table access in get_commit_by_hash
    mock_user_repo.get_user_by_email.assert_called_once_with(sample_author_email)
    mock_ai_integration.analyze_commit_diff.assert_called_once()
    # Check args passed to analyze_commit_diff
    ai_diff_call_args, _ = mock_ai_integration.analyze_commit_diff.call_args
    assert ai_diff_call_args[0]['commit_hash'] == sample_commit_hash
    assert ai_diff_call_args[0]['diff'] == sample_diff

    mock_ai_integration.analyze_commit_code_quality.assert_called_once()
     # Check args passed to analyze_commit_code_quality
    ai_quality_call_args, _ = mock_ai_integration.analyze_commit_code_quality.call_args
    assert ai_quality_call_args[0] == sample_diff # First arg is diff
    assert ai_quality_call_args[1] == sample_commit_payload_dict['commit_message'] # Second arg is message

    mock_daily_report_service.get_user_report_for_date.assert_called_once_with(sample_user_id, mock.ANY) # Check user ID, date might vary slightly
    # Check that the date passed to get_user_report_for_date is correct
    call_args, _ = mock_daily_report_service.get_user_report_for_date.call_args
    assert isinstance(call_args[1], datetime), "Second arg to get_user_report_for_date should be datetime"
    assert call_args[1].date() == sample_commit_timestamp.date()

    # Check save_commit call (via the real repository using the mock client)
    # Assert that the upsert method was called on the mock client via the repository
    commit_service.commit_repository._client.upsert.assert_called_once()
    upsert_call_args, upsert_call_kwargs = commit_service.commit_repository._client.upsert.call_args
    assert upsert_call_kwargs.get('on_conflict') == 'commit_hash'
    assert isinstance(upsert_call_args[0], dict)
    assert upsert_call_args[0]['commit_hash'] == sample_commit_hash
    assert upsert_call_args[0]['author_id'] == str(sample_user_id) # Ensure UUID is stringified
    assert upsert_call_args[0]['ai_estimated_hours'] == str(mock_ai_commit_analysis['estimated_hours']) # Ensure Decimal is stringified


    # Verify docs scan calls (since scan_docs=True)
    commit_service.docs_update_service.analyze_documentation.assert_called_once()
    commit_service.docs_update_service.create_pull_request.assert_called_once()


    logger.info("\n----- Logging Final Commit Object -----")
    log_commit_object(analyzed_commit_object)

    logger.info("\n--- Test Analysis Completed Successfully ---")


def log_commit_object(commit: Commit, indent_level: int = 0):
    """Helper to log the fields of the final Commit object."""
    indent = "  " * indent_level
    if not commit:
        logger.info(f"{indent}Commit object is None.")
        return

    logger.info(f"{indent}Commit Hash: {commit.commit_hash}")
    logger.info(f"{indent}Author ID: {commit.author_id}")
    logger.info(f"{indent}Repo Name: {getattr(commit, 'repository_name', 'N/A')}") # Check if field exists
    logger.info(f"{indent}Timestamp: {commit.commit_timestamp}")
    logger.info(f"{indent}AI Points (Complexity): {commit.ai_points}")
    logger.info(f"{indent}AI Estimated Hours: {commit.ai_estimated_hours}")
    logger.info(f"{indent}Seniority Score: {commit.seniority_score}")
    logger.info(f"{indent}Risk Level: {commit.risk_level}")
    logger.info(f"{indent}Model Used (Commit Analysis): {commit.model_used}")
    logger.info(f"{indent}Analyzed At: {commit.analyzed_at}")
    logger.info(f"{indent}Key Changes: {commit.key_changes}")
    logger.info(f"{indent}Seniority Rationale: {commit.seniority_rationale}")
    logger.info(f"{indent}EOD Report ID: {commit.eod_report_id}")
    logger.info(f"{indent}EOD Report Summary Snippet: {commit.eod_report_summary}")
    logger.info(f"{indent}Comparison Notes: \n{indent}  " + commit.comparison_notes.replace('\n', f'\n{indent}  ') if commit.comparison_notes else "None")
    logger.info(f"{indent}Code Quality Analysis:")
    if commit.code_quality_analysis:
        log_code_quality_results(commit.code_quality_analysis, indent_level + 1)
    else:
        logger.info(f"{indent}  None")
    # Log DB fields if available (populated by mock_save_commit)
    logger.info(f"{indent}DB ID: {getattr(commit, 'id', 'N/A')}")
    logger.info(f"{indent}DB Created At: {getattr(commit, 'created_at', 'N/A')}")
    logger.info(f"{indent}DB Updated At: {getattr(commit, 'updated_at', 'N/A')}")


def log_code_quality_results(result: Dict[str, Any], indent_level: int = 0):
    """Helper to log code quality specific fields."""
    indent = "  " * indent_level
    if not result:
        logger.error(f"{indent}Code Quality Analysis Result is None or empty.")
        return
    if result.get("error"):
        logger.error(f"{indent}Code Quality Analysis Error: {result.get('message')}")
        return

    logger.info(f"{indent}Model Used: {result.get('model_used', 'N/A')}")
    logger.info(f"{indent}Readability Score: {result.get('readability_score', 'N/A')}")
    logger.info(f"{indent}Complexity Score (Quality): {result.get('complexity_score', 'N/A')}")
    logger.info(f"{indent}Maintainability Score: {result.get('maintainability_score', 'N/A')}")
    logger.info(f"{indent}Test Coverage Estimation: {result.get('test_coverage_estimation', 'N/A')}")
    logger.info(f"{indent}Estimated Seniority Level: {result.get('estimated_seniority_level', 'N/A')}")

    def log_list(name: str, items: Optional[List[str]]):
        logger.info(f"{indent}{name} ({len(items) if items else 0}):")
        if items:
            for item in items:
                logger.info(f"{indent}  - {item}")
        else:
             logger.info(f"{indent}  None")

    log_list("Security Concerns", result.get('security_concerns'))
    log_list("Performance Issues", result.get('performance_issues'))
    log_list("Best Practices Adherence", result.get('best_practices_adherence'))
    log_list("Suggestions for Improvement", result.get('suggestions_for_improvement'))
    log_list("Positive Feedback", result.get('positive_feedback'))
    logger.info(f"{indent}Overall Assessment Summary: {result.get('overall_assessment_summary', 'N/A')}")


if __name__ == "__main__":
    # Ensure environment variables are set if running directly
    required_env_vars = ["OPENAI_API_KEY", "GITHUB_TOKEN"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.warning(f"Missing environment variables: {', '.join(missing_vars)}. Using placeholder values.")
        os.environ.setdefault("OPENAI_API_KEY", "fake-key-placeholder")
        os.environ.setdefault("GITHUB_TOKEN", "fake-token-placeholder")

    try:
        asyncio.run(run_test_analysis())
    except Exception as e:
         logger.error(f"Unhandled exception during test execution: {e}", exc_info=True)
         sys.exit(1)

# --- Removed Old Code ---
# Removed old synchronous test functions and related helpers/mocks if they existed.
# Ensure all top-level execution uses asyncio.run(run_test_analysis()).

# Removed old synchronous test functions and related helpers/mocks if they existed.
# Ensure all top-level execution uses asyncio.run(run_test_analysis()). 