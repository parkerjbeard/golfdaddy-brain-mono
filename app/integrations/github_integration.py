from typing import Dict, Any, Optional, List
import requests
import json
import os
import hmac
import hashlib
from datetime import datetime
from urllib.parse import urlparse

from app.config.settings import settings

class GitHubIntegration:
    """Integration with GitHub API for commit data."""
    
    def __init__(self):
        """Initialize the GitHub integration with token from settings."""
        self.token = settings.github_token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    def get_commit_diff(self, repository: str, commit_hash: str) -> Dict[str, Any]:
        """
        Get the diff for a specific commit from GitHub.
        
        Args:
            repository: Repository name (format: "owner/repo")
            commit_hash: Commit hash
            
        Returns:
            Dictionary with commit data including diff
        """
        try:
            # Parse repository name
            owner, repo = repository.split("/")
            
            # Make API request to get commit details
            url = f"{self.base_url}/repos/{owner}/{repo}/commits/{commit_hash}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            commit_data = response.json()
            
            # Extract relevant information
            files_changed = []
            additions = 0
            deletions = 0
            
            for file in commit_data.get("files", []):
                files_changed.append(file["filename"])
                additions += file.get("additions", 0)
                deletions += file.get("deletions", 0)
            
            return {
                "commit_hash": commit_hash,
                "repository": repository,
                "diff": commit_data.get("diff", ""),
                "files_changed": files_changed,
                "additions": additions,
                "deletions": deletions,
                "retrieved_at": datetime.now().isoformat(),
                "author": commit_data.get("commit", {}).get("author", {}),
                "message": commit_data.get("commit", {}).get("message", ""),
                "url": commit_data.get("html_url", "")
            }
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch commit diff: {str(e)}")
    
    def verify_webhook(self, signature: str, body: str) -> bool:
        """
        Verify the signature of a GitHub webhook.
        
        Args:
            signature: X-Hub-Signature-256 header
            body: Raw request body
            
        Returns:
            Boolean indicating if the signature is valid
        """
        webhook_secret = settings.github_webhook_secret
        
        if not webhook_secret:
            raise ValueError("GitHub webhook secret not configured")
        
        # Compute signature
        computed_signature = "sha256=" + hmac.new(
            bytes(webhook_secret, "utf-8"),
            bytes(body, "utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures using constant-time comparison
        return hmac.compare_digest(computed_signature, signature)
    
    def parse_push_event(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse a GitHub push event payload into commit data.
        
        Args:
            payload: The webhook payload from GitHub
            
        Returns:
            List of dictionaries with commit data
        """
        try:
            commits = []
            repository = payload.get("repository", {}).get("full_name")
            if not repository:
                raise ValueError("Repository information not found in payload")
                
            ref = payload.get("ref", "")
            branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref
            
            for commit_data in payload.get("commits", []):
                commit = {
                    "commit_hash": commit_data.get("id"),
                    "author_name": commit_data.get("author", {}).get("name"),
                    "author_email": commit_data.get("author", {}).get("email"),
                    "message": commit_data.get("message"),
                    "url": commit_data.get("url"),
                    "timestamp": commit_data.get("timestamp"),
                    "repository": repository,
                    "branch": branch,
                    "added": commit_data.get("added", []),
                    "removed": commit_data.get("removed", []),
                    "modified": commit_data.get("modified", []),
                    "distinct": commit_data.get("distinct", True)
                }
                
                # Fetch detailed diff information
                try:
                    diff_data = self.get_commit_diff(repository, commit["commit_hash"])
                    commit.update({
                        "files_changed": diff_data["files_changed"],
                        "additions": diff_data["additions"],
                        "deletions": diff_data["deletions"],
                        "diff": diff_data["diff"]
                    })
                except Exception as e:
                    # Log the error but continue processing other commits
                    print(f"Failed to fetch diff for commit {commit['commit_hash']}: {str(e)}")
                
                commits.append(commit)
            
            return commits
            
        except Exception as e:
            raise Exception(f"Failed to parse push event: {str(e)}")