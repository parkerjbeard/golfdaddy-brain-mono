import logging
import sys
import types
from unittest.mock import MagicMock

# Provide a stub 'github' module if PyGithub is unavailable
if 'github' not in sys.modules:
    github_stub = types.ModuleType('github')
    class Github:
        def __init__(self, token):
            self.token = token
    class GithubException(Exception):
        pass
    github_stub.Github = Github
    github_stub.GithubException = GithubException
    sys.modules['github'] = github_stub

from doc_agent.client import AutoDocClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SAMPLE_DIFF = """diff --git a/README.md b/README.md
index 1111111..2222222 100644
--- a/README.md
+++ b/README.md
@@
-Old content
+New content
"""

def test_auto_doc_flow(monkeypatch):
    """Demonstrate the AutoDocClient end-to-end flow using mocks."""
    client = AutoDocClient("fake-openai", "fake-token", "owner/docs")

    # Mock OpenAI completion
    mock_openai = MagicMock()
    mock_openai.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="--- a/README.md\n+++ b/README.md\n@@\n-Old content\n+New content added\n"))]
    )
    client.openai_client = mock_openai

    # Auto-approve via Slack
    client.propose_via_slack = MagicMock(return_value=True)

    # Mock GitHub interactions
    mock_repo = MagicMock()
    mock_repo.default_branch = "main"
    mock_repo.create_pull.return_value.html_url = "http://example.com/pr/1"
    client.github = MagicMock()
    client.github.get_repo.return_value = mock_repo

    patch = client.analyze_diff(SAMPLE_DIFF)
    assert "New content added" in patch

    approved = client.propose_via_slack(patch)
    assert approved

    url = client.apply_patch(patch, "abcdef0", branch_name="auto-docs-test")
    assert url == "http://example.com/pr/1"
    logger.info("Created PR at %s", url)
