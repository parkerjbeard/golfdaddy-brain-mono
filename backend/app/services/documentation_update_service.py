from typing import Dict, Any, List, Optional
import logging
import json
import os
from datetime import datetime

from openai import OpenAI, APIError as OpenAIAPIError
from github import Github, GithubException
from github.Repository import Repository
from github.ContentFile import ContentFile

from app.config.settings import settings
from app.core.exceptions import (
    ConfigurationError,
    ExternalServiceError,
    AIIntegrationError,
    AppExceptionBase
)

logger = logging.getLogger(__name__)

class DocumentationUpdateService:
    """Service for scanning documentation and proposing updates based on commit analysis."""
    
    def __init__(self):
        """Initialize the documentation update service."""
        self.github_token = settings.GITHUB_TOKEN
        self.openai_api_key = settings.OPENAI_API_KEY
        
        if not self.github_token:
            raise ConfigurationError("GitHub token not configured in settings. Documentation features will be disabled.")
        
        if not self.openai_api_key:
            raise ConfigurationError("OpenAI API key not configured in settings. Documentation features will be disabled.")
        
        try:
            self.openai_client = OpenAI(api_key=self.openai_api_key)
            self.github_client = Github(self.github_token)
        except Exception as e:
            logger.error(f"Failed to initialize clients for DocumentationUpdateService: {e}", exc_info=True)
            raise ConfigurationError(f"Failed to initialize clients: {e}")

        self.openai_model = settings.DOCUMENTATION_OPENAI_MODEL
    
    def _log_separator(self, message="", char="=", length=80):
        """Print a separator line with optional message for visual log grouping."""
        if not message:
            logger.info(char * length)
            return
        
        side_length = (length - len(message) - 2) // 2
        if side_length <= 0:
            logger.info(message)
            return
            
        left = char * side_length
        right = char * (length - side_length - len(message) - 2)
        logger.info(f"{left} {message} {right}")
    
    def get_repository_content(self, repo_name: str, path: str = "") -> List[Dict[str, Any]]:
        """
        Recursively get all markdown content from a repository.
        
        Args:
            repo_name: The name of the repository in format 'owner/repo'
            path: The directory path to start from (empty for root)
            
        Returns:
            List of dictionaries containing file paths and content
        """
        try:
            logger.info(f"Fetching documentation files from {repo_name}/{path}")
            
            repo = self.github_client.get_repo(repo_name)
            contents = repo.get_contents(path)
            
            markdown_files = []
            
            while contents:
                file_content = contents.pop(0)
                
                if file_content.type == "dir":
                    # Get contents of the directory
                    dir_contents = repo.get_contents(file_content.path)
                    contents.extend(dir_contents)
                elif file_content.name.endswith((".md", ".markdown")) and not file_content.name.startswith("."):
                    # Only include markdown files and exclude hidden files
                    try:
                        file_data = {
                            "path": file_content.path,
                            "name": file_content.name,
                            "content": file_content.decoded_content.decode("utf-8"),
                            "sha": file_content.sha
                        }
                        markdown_files.append(file_data)
                        logger.debug(f"Added markdown file: {file_content.path}")
                    except Exception as e:
                        logger.error(f"Error decoding content for {file_content.path}: {e}")
            
            logger.info(f"Found {len(markdown_files)} markdown files in repository")
            return markdown_files
        
        except GithubException as e:
            logger.error(f"GitHub API error fetching repository content for {repo_name}/{path}: {e.status} {e.data}", exc_info=True)
            raise ExternalServiceError(service_name="GitHub", original_message=f"Failed to fetch content from {repo_name}: {e.data.get('message', str(e))}")
        except Exception as e:
            logger.error(f"Unexpected error fetching repository content for {repo_name}/{path}: {e}", exc_info=True)
            raise AppExceptionBase(f"Unexpected error fetching repository content from {repo_name}: {str(e)}")
    
    def analyze_documentation(self, 
                             docs_repo_name: str, 
                             commit_analysis_result: Dict[str, Any],
                             source_repo_name: str) -> Dict[str, Any]:
        """
        Analyze documentation based on commit analysis results and propose changes if needed.
        
        Args:
            docs_repo_name: Name of the documentation repository in format 'owner/repo'
            commit_analysis_result: Results from the commit analysis
            source_repo_name: The repository where the commit was made
            
        Returns:
            Dictionary with documentation analysis results and proposed changes
        """
        self._log_separator(f"DOCUMENTATION ANALYSIS", "=")
        logger.info(f"Starting documentation analysis for {docs_repo_name}")
        logger.info(f"Based on commit analysis in {source_repo_name}")
        
        try:
            # Fetch all markdown documentation files
            docs_files = self.get_repository_content(docs_repo_name)
            
            if not docs_files:
                logger.warning(f"No documentation files found in {docs_repo_name}. Skipping analysis.")
                return {
                    "status": "no_files_found",
                    "message": f"No documentation files found in {docs_repo_name}",
                    "changes_needed": False,
                    "analyzed_at": datetime.now().isoformat()
                }
            
            # Combine all documentation into a single context for analysis
            all_docs_content = "\n\n".join([
                f"# File: {doc['path']}\n\n{doc['content']}" for doc in docs_files
            ])
            
            # Create list of file paths for reference
            doc_files_list = [doc['path'] for doc in docs_files]
            
            # Prepare prompt for OpenAI
            prompt = self._create_analysis_prompt(all_docs_content, doc_files_list, commit_analysis_result, source_repo_name)
            
            # Call OpenAI to analyze the documentation
            response = self.openai_client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": "You are an expert technical documentation specialist with a deep understanding of software development. Your task is to analyze existing documentation against recent code changes and suggest necessary updates."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            # Parse the response
            analysis_result = json.loads(response.choices[0].message.content)
            
            # Add metadata
            analysis_result.update({
                "analyzed_at": datetime.now().isoformat(),
                "docs_repository": docs_repo_name,
                "source_repository": source_repo_name,
                "model_used": self.openai_model
            })
            
            # Log summary
            if analysis_result.get("changes_needed", False):
                changes_count = len(analysis_result.get("proposed_changes", []))
                logger.info(f"Documentation updates needed: {changes_count} file(s) require changes")
                for change in analysis_result.get("proposed_changes", []):
                    logger.info(f"- {change['file_path']}: {change['change_summary']}")
            else:
                logger.info("No documentation updates needed")
            
            self._log_separator(f"END DOCUMENTATION ANALYSIS", "=")
            return analysis_result
            
        except OpenAIAPIError as e:
            logger.error(f"OpenAI API error during documentation analysis: {e.status_code} {e.response}", exc_info=True)
            raise AIIntegrationError(f"OpenAI service error: {e.message or str(e)}")
        except (ExternalServiceError, AppExceptionBase) as e:
            raise e
        except Exception as e:
            logger.error(f"Error analyzing documentation for {docs_repo_name}: {e}", exc_info=True)
            raise AIIntegrationError(f"Failed to analyze documentation due to an unexpected error: {str(e)}")
    
    def _create_analysis_prompt(self, 
                              docs_content: str, 
                              doc_files_list: List[str],
                              commit_analysis: Dict[str, Any],
                              source_repo: str) -> str:
        """
        Create a prompt for the OpenAI model to analyze documentation.
        
        Args:
            docs_content: The combined content of all documentation files
            doc_files_list: List of documentation file paths
            commit_analysis: Results from commit analysis
            source_repo: Repository where the commit was made
            
        Returns:
            Prompt string for OpenAI
        """
        # Extract relevant information from commit analysis
        key_changes = commit_analysis.get("key_changes", [])
        suggestions = commit_analysis.get("suggestions", [])
        technical_debt = commit_analysis.get("technical_debt", [])
        commit_message = commit_analysis.get("message", "No message provided")
        commit_hash = commit_analysis.get("commit_hash", "unknown")
        files_changed = commit_analysis.get("files_changed", [])
        
        # Create the prompt
        prompt = f"""I need you to analyze the existing documentation against recent code changes and identify if any documentation updates are needed.

COMMIT INFORMATION:
- Repository: {source_repo}
- Commit Hash: {commit_hash}
- Commit Message: {commit_message}
- Files Changed: {', '.join(files_changed) if isinstance(files_changed, list) else files_changed}

KEY CHANGES FROM COMMIT ANALYSIS:
{json.dumps(key_changes, indent=2)}

TECHNICAL DEBT IDENTIFIED:
{json.dumps(technical_debt, indent=2)}

IMPLEMENTATION SUGGESTIONS:
{json.dumps(suggestions, indent=2)}

DOCUMENTATION FILES AVAILABLE:
{json.dumps(doc_files_list, indent=2)}

CURRENT DOCUMENTATION CONTENT:
{docs_content}

Please analyze the current documentation against the recent code changes and provide the following:

1. Determine if any documentation changes are needed based on the commit analysis.
2. For each file that needs changes, identify what specific updates should be made and why.
3. If no changes are needed, explain why the current documentation is sufficient.

Please format your response as a JSON object with the following structure:
{{
  "changes_needed": <boolean>,
  "analysis_summary": <string>,
  "proposed_changes": [
    {{
      "file_path": <string>,
      "change_summary": <string>,
      "change_details": <string>,
      "justification": <string>,
      "priority": <"high"|"medium"|"low">
    }}
  ],
  "recommendations": <string>
}}

Your analysis should focus on:
- API changes that need documentation
- New features that should be documented
- Changed functionality that makes current documentation inaccurate
- Examples or tutorials that need updating
- Architecture changes that should be reflected in documentation
- Security considerations that should be documented

IMPORTANT: Be conservative in suggesting changes. Only propose documentation updates if they are genuinely needed based on the commit analysis. Most commits will not require documentation updates."""

        return prompt
    
    def create_pull_request(self, 
                          docs_repo_name: str, 
                          proposed_changes: List[Dict[str, Any]],
                          commit_analysis: Dict[str, Any],
                          branch_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a pull request with proposed documentation changes.
        
        Args:
            docs_repo_name: Name of the documentation repository
            proposed_changes: List of changes to be made from documentation analysis
            commit_analysis: Original commit analysis results
            branch_name: Optional custom branch name
            
        Returns:
            Dictionary with pull request details
        """
        if not proposed_changes:
            logger.info("No changes proposed. Skipping pull request creation.")
            return {
                "status": "no_changes",
                "message": "No documentation changes needed"
            }
        
        try:
            repo = self.github_client.get_repo(docs_repo_name)
            default_branch = repo.default_branch
            
            # Create a unique branch name if not provided
            if not branch_name:
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                commit_hash = commit_analysis.get("commit_hash", "unknown")[:7]
                branch_name = f"docs-update-{commit_hash}-{timestamp}"
            
            # Get the reference to the default branch
            ref = repo.get_git_ref(f"heads/{default_branch}")
            sha = ref.object.sha
            
            # Create a new branch
            repo.create_git_ref(f"refs/heads/{branch_name}", sha)
            logger.info(f"Created branch {branch_name} in {docs_repo_name}")
            
            # Make changes to each file
            for change in proposed_changes:
                file_path = change["file_path"]
                
                try:
                    # Get the current file content
                    file_content = repo.get_contents(file_path, ref=branch_name)
                    current_content = file_content.decoded_content.decode("utf-8")
                    
                    # Create prompt for generating updated content
                    update_prompt = f"""Given the following markdown documentation file and the proposed changes, 
                    generate the updated markdown content incorporating the changes. 
                    
                    Current content:
                    ```
                    {current_content}
                    ```
                    
                    Proposed changes:
                    - Summary: {change['change_summary']}
                    - Details: {change['change_details']}
                    
                    Return only the complete updated markdown content. Do not include any explanations or markdown code blocks."""
                    
                    # Generate updated content
                    updated_content_response = self.openai_client.chat.completions.create(
                        model=self.openai_model,
                        messages=[
                            {"role": "system", "content": "You are a technical documentation specialist. Your task is to update markdown documentation to accurately reflect code changes."},
                            {"role": "user", "content": update_prompt}
                        ],
                        temperature=0.3
                    )
                    
                    updated_content = updated_content_response.choices[0].message.content.strip()
                    
                    # Commit the changes
                    commit_message = f"Update {file_path}\n\n{change['change_summary']}"
                    repo.update_file(
                        path=file_path,
                        message=commit_message,
                        content=updated_content,
                        sha=file_content.sha,
                        branch=branch_name
                    )
                    
                    logger.info(f"Updated file {file_path} in branch {branch_name}")
                    
                except GithubException as e_git_file:
                    logger.error(f"GitHub error updating file {file_path} in {branch_name}: {e_git_file.status} {e_git_file.data}", exc_info=True)
                    change['error'] = f"Failed to update file on GitHub: {e_git_file.data.get('message', str(e_git_file))}"
                    continue
                except OpenAIAPIError as e_openai_file:
                    logger.error(f"OpenAI error generating content for file {file_path}: {e_openai_file.status_code} {e_openai_file.response}", exc_info=True)
                    change['error'] = f"Failed to generate updated content with OpenAI: {e_openai_file.message or str(e_openai_file)}"
                    continue
                except Exception as e_file:
                    logger.error(f"Error processing file {file_path} for PR in {branch_name}: {e_file}", exc_info=True)
                    change['error'] = f"Unexpected error processing file: {str(e_file)}"
                    continue
            
            # Create a pull request
            commit_hash = commit_analysis.get("commit_hash", "unknown")[:7]
            pr_title = f"Documentation Updates for {commit_hash}"
            
            # Prepare PR body with change details
            pr_body = f"# Documentation Updates\n\nBased on commit [{commit_hash}]({commit_analysis.get('repository', '')}/commit/{commit_analysis.get('commit_hash', '')})\n\n"
            pr_body += "## Changes Summary\n\n"
            
            for change in proposed_changes:
                pr_body += f"- **{change['file_path']}**: {change['change_summary']}\n"
                pr_body += f"  {change['justification']}\n\n"
            
            pr_body += "\nThis PR was automatically generated based on code changes analysis."
            
            # Create the PR
            pr = repo.create_pull(
                title=pr_title,
                body=pr_body,
                head=branch_name,
                base=default_branch
            )
            
            logger.info(f"Created pull request #{pr.number} in {docs_repo_name}")
            
            return {
                "status": "success",
                "pull_request_number": pr.number,
                "pull_request_url": pr.html_url,
                "branch_name": branch_name
            }
            
        except GithubException as e:
            logger.error(f"GitHub API error creating pull request for {docs_repo_name}: {e.status} {e.data}", exc_info=True)
            raise ExternalServiceError(service_name="GitHub", original_message=f"Failed to create PR for {docs_repo_name}: {e.data.get('message', str(e))}")
        except OpenAIAPIError as e:
            logger.error(f"OpenAI API error during PR creation process for {docs_repo_name}: {e.status_code} {e.response}", exc_info=True)
            raise AIIntegrationError(f"OpenAI service error during PR creation: {e.message or str(e)}")
        except Exception as e:
            logger.error(f"Error creating pull request for {docs_repo_name}: {e}", exc_info=True)
            raise AppExceptionBase(f"Unexpected error creating pull request for {docs_repo_name}: {str(e)}")

    def save_to_git_repository(self, repo_name: str, file_path: str, content: str, 
                             title: str, commit_message: Optional[str] = None) -> Dict[str, Any]:
        """
        Save documentation directly to a Git repository.
        
        Args:
            repo_name: The repository name in format 'owner/repo'
            file_path: Path to the file in the repository (including extension, e.g., 'docs/api.md')
            content: Markdown content to save
            title: Title of the document (used for commit message if not provided)
            commit_message: Optional custom commit message
            
        Returns:
            Dictionary with details about the saved file
        """
        try:
            self._log_separator(f"SAVING TO GIT REPO", "=")
            logger.info(f"Saving documentation to {repo_name}/{file_path}")
            
            # If file_path doesn't end with .md, add it
            if not file_path.endswith(('.md', '.markdown')):
                file_path = f"{file_path}.md"
            
            # Get repository
            repo = self.github_client.get_repo(repo_name)
            default_branch = repo.default_branch
            
            # Check if file exists
            file_exists = True
            try:
                file_content = repo.get_contents(file_path, ref=default_branch)
                file_sha = file_content.sha
            except Exception:
                # File doesn't exist
                file_exists = False
                file_sha = None
                logger.info(f"File {file_path} doesn't exist. Creating new file.")
            
            # Create or update file
            if not commit_message:
                commit_message = f"{'Update' if file_exists else 'Add'} documentation: {title}"
            
            # Commit the file
            if file_exists:
                # Update existing file
                result = repo.update_file(
                    path=file_path,
                    message=commit_message,
                    content=content,
                    sha=file_sha,
                    branch=default_branch
                )
                file_url = f"https://github.com/{repo_name}/blob/{default_branch}/{file_path}"
                logger.info(f"Updated file: {file_url}")
            else:
                # Create new file
                result = repo.create_file(
                    path=file_path,
                    message=commit_message,
                    content=content,
                    branch=default_branch
                )
                file_url = f"https://github.com/{repo_name}/blob/{default_branch}/{file_path}"
                logger.info(f"Created file: {file_url}")
            
            self._log_separator(f"END SAVING TO GIT REPO", "=")
            return {
                "status": "success",
                "url": file_url,
                "file_path": file_path,
                "commit_sha": result["commit"].sha if isinstance(result, dict) and "commit" in result else None
            }
        
        except GithubException as e:
            logger.error(f"GitHub API error saving to repository {repo_name}/{file_path}: {e.status} {e.data}", exc_info=True)
            raise ExternalServiceError(service_name="GitHub", original_message=f"Failed to save to Git repo {repo_name}: {e.data.get('message', str(e))}")
        except Exception as e:
            logger.error(f"Error saving to Git repository {repo_name}/{file_path}: {e}", exc_info=True)
            raise AppExceptionBase(f"Unexpected error saving to Git repository {repo_name}: {str(e)}") 