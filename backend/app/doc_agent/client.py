import os
import subprocess
import tempfile
import logging
import time
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import uuid
import re

from github import Github
from github import GithubException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Import settings
from app.config.settings import settings # Assuming this path
from app.core.database import get_db
from app.models.doc_approval import DocApproval
from app.services.slack_service import SlackService
from app.services.slack_message_templates import SlackMessageTemplates
from app.services.embedding_service import EmbeddingService
from app.services.context_analyzer import ContextAnalyzer

# Use AsyncOpenAI
try:
    from openai import AsyncOpenAI, OpenAIError # Added OpenAIError
except ImportError: # Adjusted for clarity
    AsyncOpenAI = None  # type: ignore
    OpenAIError = None # type: ignore

logger = logging.getLogger(__name__)


def _retry(
    func,
    *args,
    retries: int = 3,
    initial_delay: float = 1.0,
    backoff: int = 2,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    **kwargs,
) -> Any:
    """Retry a synchronous function with exponential backoff."""
    delay = initial_delay
    for attempt in range(1, retries + 1):
        try:
            return func(*args, **kwargs)
        except exceptions as exc:  # pragma: no cover - simple retry logic
            if attempt == retries:
                raise
            logger.warning(
                "Attempt %s/%s failed for %s: %s. Retrying in %.1fs",
                attempt,
                retries,
                getattr(func, "__name__", str(func)),
                exc,
                delay,
            )
            time.sleep(delay)
            delay *= backoff


async def _async_retry(
    func,
    *args,
    retries: int = 3,
    initial_delay: float = 1.0,
    backoff: int = 2,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    **kwargs,
) -> Any:
    """Retry an async function with exponential backoff."""
    delay = initial_delay
    for attempt in range(1, retries + 1):
        try:
            return await func(*args, **kwargs)
        except exceptions as exc:  # pragma: no cover - simple retry logic
            if attempt == retries:
                raise
            logger.warning(
                "Attempt %s/%s failed for %s: %s. Retrying in %.1fs",
                attempt,
                retries,
                getattr(func, "__name__", str(func)),
                exc,
                delay,
            )
            await asyncio.sleep(delay)
            delay *= backoff

# Default model if not specified
# DEFAULT_DOC_AGENT_MODEL = "gpt-4.1-2025-04-14" # Example, align with your preferred default

class AutoDocClient:
    """Thin layer between Git and OpenAI for automated documentation."""

    def __init__(self, openai_api_key: str, github_token: str, docs_repo: str,
                 slack_webhook: Optional[str] = None, slack_channel: Optional[str] = None,
                 enable_semantic_search: bool = True) -> None: # Removed openai_model parameter
        if not openai_api_key:
            raise ValueError("OpenAI API key is required.")
        self.openai_api_key = openai_api_key
        
        if not github_token: # Added check for github_token for consistency
            raise ValueError("GitHub token is required.")
        self.github_token = github_token
        
        self.docs_repo = docs_repo
        self.slack_webhook = slack_webhook
        self.slack_channel = slack_channel or settings.SLACK_DEFAULT_CHANNEL
        self.github = Github(github_token)
        self.slack_service = SlackService() if settings.SLACK_BOT_TOKEN else None
        
        # Initialize semantic search and context analyzer
        self.enable_semantic_search = enable_semantic_search
        if enable_semantic_search:
            self.embedding_service = EmbeddingService()
            self.context_analyzer = ContextAnalyzer(self.embedding_service)
        else:
            self.embedding_service = None
            self.context_analyzer = None
        
        if AsyncOpenAI:
            self.openai_client = AsyncOpenAI(api_key=openai_api_key)
        else:
            logger.warning("AsyncOpenAI client not available. Functionality will be limited.")
            self.openai_client = None
            
        self.openai_model = settings.DOC_AGENT_OPENAI_MODEL # Use model from settings

    def get_commit_diff(self, repo_path: str, commit_hash: str) -> str:
        """Return the diff for the given commit."""
        diff = subprocess.check_output(
            ["git", "-C", repo_path, "show", commit_hash], text=True
        )
        return diff

    async def analyze_diff(self, diff: str) -> str:
        """Use OpenAI to generate a documentation patch from a commit diff."""
        if not self.openai_client:
            logger.warning("OpenAI client not available, returning empty string.")
            return ""

        prompt = (
            "You are an expert technical writer. Given the following git diff, "
            "suggest documentation updates as a unified diff. Ensure the output is ONLY the diff content itself, no extra explanations or markdown."
        )

        api_params: Dict[str, Any] = {
            "model": self.openai_model,
            "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": diff}],
        }

        async def _call_openai() -> Any:
            if str(self.openai_model).startswith("gpt-5"):
                return await self.openai_client.responses.create(
                    model=self.openai_model,
                    reasoning={"effort": settings.openai_reasoning_effort},
                    input=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": diff}
                    ]
                )
            return await self.openai_client.chat.completions.create(**api_params)

        try:
            response = await _async_retry(_call_openai, exceptions=(OpenAIError,))
            if str(self.openai_model).startswith("gpt-5"):
                content = getattr(response, "output_text", None)
                if not content and hasattr(response, "choices") and response.choices:
                    content = response.choices[0].message.content
                return (content or "").strip()
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                return content.strip() if content else ""
            logger.error("OpenAI response did not contain expected content.")
            return ""
        except Exception as exc:
            logger.error("Failed to analyze diff with OpenAI: %s", exc)
            return ""

    async def propose_via_slack(self, diff: str, patch: str, commit_hash: str, 
                                commit_message: str = "", db: Optional[AsyncSession] = None) -> Optional[str]:
        """Send the proposed diff to Slack for manual approval."""
        if not diff or not self.slack_service:
            logger.warning("Slack service not configured or no diff provided")
            return None
            
        # Parse diff to get statistics
        files_affected = len(re.findall(r'^\+\+\+ ', diff, re.MULTILINE))
        additions = len(re.findall(r'^\+(?!\+\+)', diff, re.MULTILINE))
        deletions = len(re.findall(r'^-(?!--)', diff, re.MULTILINE))
        
        # Create approval record
        if not db:
            async with get_db() as session:
                db = session
                return await self._create_and_send_approval(db, diff, patch, commit_hash, 
                                                          commit_message, files_affected, 
                                                          additions, deletions)
        else:
            return await self._create_and_send_approval(db, diff, patch, commit_hash, 
                                                      commit_message, files_affected, 
                                                      additions, deletions)
    
    async def _create_and_send_approval(self, db: AsyncSession, diff: str, patch: str, 
                                      commit_hash: str, commit_message: str, 
                                      files_affected: int, additions: int, deletions: int) -> Optional[str]:
        """Create approval record and send Slack message."""
        try:
            # Create approval record
            approval = DocApproval(
                commit_hash=commit_hash,
                repository=self.docs_repo,
                diff_content=diff,
                patch_content=patch,
                slack_channel=self.slack_channel,
                expires_at=datetime.utcnow() + timedelta(hours=24),
                approval_metadata={
                    "commit_message": commit_message,
                    "files_affected": files_affected,
                    "additions": additions,
                    "deletions": deletions
                }
            )
            db.add(approval)
            await db.commit()
            await db.refresh(approval)
            
            # Prepare and send Slack message
            message = SlackMessageTemplates.doc_agent_approval(
                approval_id=str(approval.id),
                commit_hash=commit_hash,
                repository=self.docs_repo,
                commit_message=commit_message or "No commit message",
                diff_preview=diff[:2000],  # First 2000 chars
                files_affected=files_affected,
                additions=additions,
                deletions=deletions
            )
            
            # Send message
            result = await self.slack_service.send_message(
                channel=self.slack_channel,
                text=message["text"],
                blocks=message["blocks"]
            )
            
            if result:
                # Update approval with message timestamp
                approval.slack_message_ts = result.get("ts")
                await db.commit()
                logger.info(f"Sent approval request to Slack for {commit_hash[:8]}")
                return str(approval.id)
            else:
                logger.error("Failed to send Slack message")
                return None
                
        except Exception as e:
            logger.error(f"Error creating approval request: {e}")
            await db.rollback()
            return None

    def apply_patch(self, diff: str, commit_hash: str, branch_name: Optional[str] = None) -> Optional[str]:
        """Apply the diff to the docs repository and create a PR."""
        if not self.github:
            logger.error("GitHub client not configured")
            return None

        if not branch_name:
            branch_name = f"auto-docs-{commit_hash[:7]}"

        logger.info(
            "Applying patch for commit %s to repo %s on branch %s",
            commit_hash,
            self.docs_repo,
            branch_name,
        )

        repo = self.github.get_repo(self.docs_repo)
        base = repo.default_branch

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_url = f"https://{self.github_token}@github.com/{self.docs_repo}.git"
            try:
                subprocess.check_call(["git", "clone", repo_url, tmpdir])
            except subprocess.CalledProcessError as exc:
                logger.error("Git clone failed: %s", exc)
                if "authentication" in str(exc).lower() or "permission" in str(exc).lower():
                    logger.error("Git authentication failed. Check GITHUB_TOKEN")
                return None

            try:
                subprocess.check_call(["git", "-C", tmpdir, "checkout", "-b", branch_name])
            except subprocess.CalledProcessError as exc:
                logger.error("Failed to create branch %s: %s", branch_name, exc)
                return None

            patch_file = os.path.join(tmpdir, "patch.diff")
            with open(patch_file, "w") as f:
                f.write(diff)

            try:
                subprocess.check_call(["git", "-C", tmpdir, "apply", "--check", "patch.diff"], cwd=tmpdir)
            except subprocess.CalledProcessError:
                logger.error("Patch does not apply cleanly")
                return None

            try:
                subprocess.check_call(["git", "-C", tmpdir, "apply", "patch.diff"], cwd=tmpdir)
            except subprocess.CalledProcessError as exc:
                logger.error("Failed to apply documentation patch: %s", exc)
                return None

            subprocess.check_call(["git", "-C", tmpdir, "commit", "-am", "Automated documentation update"])

            try:
                subprocess.check_call(["git", "-C", tmpdir, "push", "origin", branch_name])
            except subprocess.CalledProcessError as exc:
                logger.error("Git push failed for branch %s: %s", branch_name, exc)
                return None

        def _create_pull() -> Any:
            return repo.create_pull(
                title=f"Automated docs update for {commit_hash}",
                body="This PR contains automated documentation updates.",
                head=branch_name,
                base=base,
            )

        try:
            pr = _retry(_create_pull, exceptions=(GithubException,))
        except Exception as exc:
            logger.error("Failed to create pull request: %s", exc)
            return None

        logger.info("Created pull request %s for commit %s", pr.html_url, commit_hash)
        return pr.html_url
    
    async def analyze_diff_with_context(
        self, 
        diff: str, 
        repo_path: str,
        commit_hash: str,
        db: Optional[AsyncSession] = None
    ) -> str:
        """Analyze diff with repository context and semantic search."""
        if not diff:
            logger.warning("No diff provided.")
            return ""
        
        if not self.context_analyzer or not self.embedding_service:
            # Fall back to regular analysis
            return await self.analyze_diff(diff)
        
        # Get repository name from path
        repo_name = os.path.basename(repo_path.rstrip('/'))
        
        # Analyze repository context
        context_info = await self._gather_context(db, repo_name, diff, commit_hash)
        
        # Build enhanced prompt with context
        prompt = self._build_context_aware_prompt(diff, context_info)
        
        if not self.openai_client:
            logger.error("OpenAI client is not configured.")
            return ""
        
        try:
            if str(settings.DOC_AGENT_OPENAI_MODEL).startswith("gpt-5"):
                completion = await _async_retry(
                    self.openai_client.responses.create,
                    model=settings.DOC_AGENT_OPENAI_MODEL,
                    reasoning={"effort": settings.openai_reasoning_effort},
                    input=[
                        {
                            "role": "system",
                            "content": "You are an expert technical writer who understands code changes and creates precise documentation updates. You have deep knowledge of the repository structure and conventions."
                        },
                        {"role": "user", "content": prompt},
                    ],
                )
                content = getattr(completion, "output_text", None)
                if not content and hasattr(completion, "choices") and completion.choices:
                    content = completion.choices[0].message.content
            else:
                completion = await _async_retry(
                    self.openai_client.chat.completions.create,
                    model=settings.DOC_AGENT_OPENAI_MODEL,  # Use settings
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert technical writer who understands code changes and creates precise documentation updates. You have deep knowledge of the repository structure and conventions."
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=2000,
                )
                content = completion.choices[0].message.content
            if content:
                return content.strip() if content else ""
            logger.error("OpenAI response did not contain expected content.")
            return ""
        except Exception as exc:
            logger.error("Failed to analyze diff with context: %s", exc)
            return await self.analyze_diff(diff)  # Fall back to regular analysis
    
    async def _gather_context(
        self,
        db: Optional[AsyncSession],
        repository: str,
        diff: str,
        commit_hash: str
    ) -> Dict[str, Any]:
        """Gather comprehensive context for the diff analysis."""
        context = {
            'repository': repository,
            'commit_hash': commit_hash,
            'affected_files': [],
            'related_docs': [],
            'code_patterns': [],
            'dependencies': [],
            'conventions': {},
            'similar_changes': []
        }
        
        # Extract affected files from diff
        file_pattern = r'^\+\+\+ b/(.+)$'
        for line in diff.split('\n'):
            match = re.match(file_pattern, line)
            if match:
                context['affected_files'].append(match.group(1))
        
        if not db or not context['affected_files']:
            return context
        
        # Get context for affected files
        for file_path in context['affected_files'][:5]:  # Limit to first 5 files
            file_context = await self.context_analyzer.get_file_context(
                db, repository, file_path
            )
            
            if file_context:
                # Add patterns and dependencies
                context['code_patterns'].extend(
                    file_context.get('design_patterns', [])
                )
                context['dependencies'].extend(
                    file_context.get('dependencies', [])
                )
        
        # Find related documentation using semantic search
        if self.embedding_service:
            # Create a summary of the change for search
            change_summary = self._summarize_diff(diff)
            
            related = await self.embedding_service.find_similar_documents(
                db,
                change_summary,
                repository,
                limit=3,
                threshold=0.7
            )
            
            context['related_docs'] = [
                {
                    'title': doc.title,
                    'content': doc.content[:500],
                    'similarity': score,
                    'file_path': doc.file_path
                }
                for doc, score in related
            ]
            
            # Check for duplicate documentation
            duplicates = await self.embedding_service.detect_duplicates(
                db,
                f"Changes from {commit_hash}",
                change_summary,
                repository
            )
            
            if duplicates:
                context['potential_duplicates'] = [
                    {'title': dup.title, 'file_path': dup.file_path}
                    for dup in duplicates
                ]
        
        # Remove duplicates from lists
        context['code_patterns'] = list(set(context['code_patterns']))
        context['dependencies'] = list(set(context['dependencies']))
        
        return context
    
    def _summarize_diff(self, diff: str, max_length: int = 500) -> str:
        """Create a summary of the diff for semantic search."""
        lines = diff.split('\n')
        summary_parts = []
        
        # Extract file changes
        files_changed = []
        for line in lines:
            if line.startswith('+++ b/'):
                files_changed.append(line[6:])
        
        if files_changed:
            summary_parts.append(f"Files changed: {', '.join(files_changed[:3])}")
        
        # Extract added content (first few meaningful additions)
        added_lines = []
        for line in lines:
            if line.startswith('+') and not line.startswith('+++'):
                content = line[1:].strip()
                if content and not content.startswith('#'):
                    added_lines.append(content)
                    if len(added_lines) >= 5:
                        break
        
        if added_lines:
            summary_parts.append(f"Changes include: {' '.join(added_lines[:3])}")
        
        summary = ' '.join(summary_parts)
        return summary[:max_length] if len(summary) > max_length else summary
    
    def _build_context_aware_prompt(
        self,
        diff: str,
        context: Dict[str, Any]
    ) -> str:
        """Build an enhanced prompt with repository context."""
        prompt_parts = [
            "Analyze the following code diff and generate documentation updates based on the repository context.",
            "",
            "REPOSITORY CONTEXT:",
            f"- Repository: {context['repository']}",
            f"- Affected files: {', '.join(context['affected_files'][:5])}",
        ]
        
        if context.get('code_patterns'):
            prompt_parts.append(
                f"- Design patterns used: {', '.join(context['code_patterns'][:5])}"
            )
        
        if context.get('dependencies'):
            prompt_parts.append(
                f"- Key dependencies: {', '.join(context['dependencies'][:5])}"
            )
        
        if context.get('related_docs'):
            prompt_parts.extend([
                "",
                "RELATED DOCUMENTATION (for reference):"
            ])
            for doc in context['related_docs'][:2]:
                prompt_parts.extend([
                    f"- {doc['title']} (similarity: {doc['similarity']:.2f})",
                    f"  Preview: {doc['content'][:200]}..."
                ])
        
        if context.get('potential_duplicates'):
            prompt_parts.extend([
                "",
                "WARNING: Potential duplicate documentation detected:",
            ])
            for dup in context['potential_duplicates'][:2]:
                prompt_parts.append(f"- {dup['title']} at {dup['file_path']}")
            prompt_parts.append("Please ensure updates don't duplicate existing content.")
        
        prompt_parts.extend([
            "",
            "CODE DIFF:",
            diff,
            "",
            "INSTRUCTIONS:",
            "1. Generate documentation updates that reflect the code changes",
            "2. Maintain consistency with existing documentation style and conventions",
            "3. Reference related documentation where appropriate",
            "4. Avoid duplicating existing documentation",
            "5. Include code examples where they add clarity",
            "6. Return ONLY the documentation updates as a unified diff format",
            "",
            "Generate the documentation updates:"
        ])
        
        return '\n'.join(prompt_parts)
    
    async def check_documentation_coverage(
        self,
        db: AsyncSession,
        repository: str,
        file_path: str
    ) -> Dict[str, Any]:
        """Check documentation coverage for a specific file."""
        if not self.embedding_service:
            return {'coverage': 'unknown', 'suggestions': []}
        
        # Get file context
        file_context = await self.context_analyzer.get_file_context(
            db, repository, file_path
        )
        
        if not file_context:
            return {'coverage': 'unknown', 'suggestions': ['File not analyzed']}
        
        # Search for existing documentation
        search_query = f"{file_path} {file_context.get('module_name', '')} documentation"
        related_docs = await self.embedding_service.find_similar_documents(
            db, search_query, repository, limit=5, threshold=0.6
        )
        
        coverage_info = {
            'file_path': file_path,
            'has_documentation': len(related_docs) > 0,
            'documentation_files': [],
            'coverage_score': 0.0,
            'suggestions': []
        }
        
        if related_docs:
            coverage_info['documentation_files'] = [
                {
                    'title': doc.title,
                    'path': doc.file_path,
                    'relevance': score
                }
                for doc, score in related_docs
            ]
            
            # Calculate coverage score based on relevance
            coverage_info['coverage_score'] = max(score for _, score in related_docs)
        
        # Generate suggestions based on what's missing
        if file_context.get('classes') and coverage_info['coverage_score'] < 0.8:
            coverage_info['suggestions'].append(
                f"Document classes: {', '.join(file_context['classes'][:3])}"
            )
        
        if file_context.get('functions') and len(file_context['functions']) > 5:
            coverage_info['suggestions'].append(
                f"Add API documentation for {len(file_context['functions'])} functions"
            )
        
        if not coverage_info['has_documentation']:
            coverage_info['suggestions'].append(
                f"Create initial documentation for {file_path}"
            )
        
        return coverage_info
