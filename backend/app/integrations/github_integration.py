import hashlib
import hmac
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from app.config.settings import settings


class GitHubIntegration:
    """Integration with GitHub API for commit data."""

    def __init__(self):
        """Initialize the GitHub integration with token from settings."""
        self.token = settings.github_token
        self.base_url = "https://api.github.com"
        self.headers = {"Authorization": f"token {self.token}", "Accept": "application/vnd.github.v3+json"}

    def get_commit_diff(self, repository: str, commit_hash: str) -> Dict[str, Any]:
        """
        Get the diff for a specific commit from GitHub, using the GitHub REST API.

        Args:
            repository: Repository name (format: "owner/repo")
            commit_hash: Commit hash/SHA

        Returns:
            Dictionary with commit data including diff and files changed
        """
        try:
            # Parse repository name
            owner, repo = repository.split("/") if "/" in repository else (repository, None)

            if not repo:
                raise ValueError(f"Invalid repository format. Expected 'owner/repo', got '{repository}'")

            # Make API request to get commit details
            url = f"{self.base_url}/repos/{owner}/{repo}/commits/{commit_hash}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()

            # Parse JSON response
            commit_data = response.json()

            # Extract relevant information
            files_changed = []
            additions = 0
            deletions = 0

            # Process files data
            for file in commit_data.get("files", []):
                files_changed.append(file.get("filename"))
                additions += file.get("additions", 0)
                deletions += file.get("deletions", 0)

            # Extract commit verification data
            verification = commit_data.get("commit", {}).get("verification", {})

            # Build and return result
            return {
                "commit_hash": commit_hash,
                "repository": repository,
                "files_changed": files_changed,
                "additions": additions,
                "deletions": deletions,
                "retrieved_at": datetime.now().isoformat(),
                "author": {
                    "name": commit_data.get("commit", {}).get("author", {}).get("name"),
                    "email": commit_data.get("commit", {}).get("author", {}).get("email"),
                    "date": commit_data.get("commit", {}).get("author", {}).get("date"),
                    "login": commit_data.get("author", {}).get("login") if commit_data.get("author") else None,
                },
                "committer": {
                    "name": commit_data.get("commit", {}).get("committer", {}).get("name"),
                    "email": commit_data.get("commit", {}).get("committer", {}).get("email"),
                    "date": commit_data.get("commit", {}).get("committer", {}).get("date"),
                    "login": commit_data.get("committer", {}).get("login") if commit_data.get("committer") else None,
                },
                "message": commit_data.get("commit", {}).get("message", ""),
                "url": commit_data.get("html_url", ""),
                "verification": {
                    "verified": verification.get("verified", False),
                    "reason": verification.get("reason", ""),
                    "signature": verification.get("signature"),
                    "payload": verification.get("payload"),
                },
                "files": [
                    {
                        "filename": file.get("filename"),
                        "status": file.get("status"),
                        "additions": file.get("additions", 0),
                        "deletions": file.get("deletions", 0),
                        "changes": file.get("changes", 0),
                        "patch": file.get("patch", ""),
                    }
                    for file in commit_data.get("files", [])
                ],
            }

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch commit diff: {str(e)}")
        except ValueError as e:
            raise Exception(f"Error processing repository: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error retrieving commit data: {str(e)}")

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
        computed_signature = (
            "sha256=" + hmac.new(bytes(webhook_secret, "utf-8"), bytes(body, "utf-8"), hashlib.sha256).hexdigest()
        )

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
                    "distinct": commit_data.get("distinct", True),
                }

                # Fetch detailed diff information
                try:
                    diff_data = self.get_commit_diff(repository, commit["commit_hash"])
                    commit.update(
                        {
                            "files_changed": diff_data["files_changed"],
                            "additions": diff_data["additions"],
                            "deletions": diff_data["deletions"],
                            "diff": diff_data["diff"],
                        }
                    )
                except Exception as e:
                    # Log the error but continue processing other commits
                    print(f"Failed to fetch diff for commit {commit['commit_hash']}: {str(e)}")

                commits.append(commit)

            return commits

        except Exception as e:
            raise Exception(f"Failed to parse push event: {str(e)}")

    def compare_commits(self, repository: str, base: str, head: str) -> Dict[str, Any]:
        """
        Compare two commits in a repository using the GitHub REST API.

        Args:
            repository: Repository name (format: "owner/repo")
            base: Base commit SHA to compare from
            head: Head commit SHA to compare to

        Returns:
            Dictionary with comparison data including files changed
        """
        try:
            # Parse repository name
            owner, repo = repository.split("/") if "/" in repository else (repository, None)

            if not repo:
                raise ValueError(f"Invalid repository format. Expected 'owner/repo', got '{repository}'")

            # Make API request to get comparison data
            url = f"{self.base_url}/repos/{owner}/{repo}/compare/{base}...{head}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()

            # Parse JSON response
            comparison_data = response.json()

            # Extract relevant information for the response
            return {
                "repository": repository,
                "base_commit": base,
                "head_commit": head,
                "status": comparison_data.get("status"),
                "ahead_by": comparison_data.get("ahead_by"),
                "behind_by": comparison_data.get("behind_by"),
                "total_commits": comparison_data.get("total_commits"),
                "retrieved_at": datetime.now().isoformat(),
                "commits": [
                    {
                        "commit_hash": commit.get("sha"),
                        "message": commit.get("commit", {}).get("message", ""),
                        "author": {
                            "name": commit.get("commit", {}).get("author", {}).get("name"),
                            "email": commit.get("commit", {}).get("author", {}).get("email"),
                            "date": commit.get("commit", {}).get("author", {}).get("date"),
                        },
                        "url": commit.get("html_url", ""),
                    }
                    for commit in comparison_data.get("commits", [])
                ],
                "files": [
                    {
                        "filename": file.get("filename"),
                        "status": file.get("status"),
                        "additions": file.get("additions", 0),
                        "deletions": file.get("deletions", 0),
                        "changes": file.get("changes", 0),
                        "patch": file.get("patch", ""),
                    }
                    for file in comparison_data.get("files", [])
                ],
            }

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to compare commits: {str(e)}")
        except ValueError as e:
            raise Exception(f"Error processing repository: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error comparing commits: {str(e)}")
