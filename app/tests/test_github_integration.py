from app.schemas.github_event import CommitPayload
from app.services.commit_analysis_service import CommitAnalysisService
from unittest.mock import patch, MagicMock

@patch('app.integrations.github_integration.GitHubIntegration.get_commit_diff')
async def test_process_commit(mock_get_diff, mock_analyze_commit):
    # ... (mock setup) ...

    # Create test data as CommitPayload instance
    commit_payload_data = CommitPayload(
        commit_hash="test123",
        repository_name="test/repo",
        commit_message="Test commit",
        commit_timestamp="2023-01-01T12:00:00Z",
        commit_url="http://example.com/commit/test123",
        repository_url="http://example.com/repo/test",
        branch="main"
    )
    commit_payload_data.author_email = "test@example.com"
    commit_payload_data.author_github_username = "Test User"

    # Create an instance of CommitAnalysisService
    mock_supabase_client_for_service = MagicMock()
    service = CommitAnalysisService(mock_supabase_client_for_service)

    # Re-patch self.analyze_commit on the created service instance for this specific test
    result = await service.process_commit(commit_payload_data)

    # Assertions
    # ... existing code ... 