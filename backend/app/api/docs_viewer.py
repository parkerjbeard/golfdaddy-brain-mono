import base64
import logging
from typing import Any, Dict, List, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Query

from app.integrations.github_app import GitHubApp

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Documentation Viewer"])


def _gh() -> GitHubApp:
  return GitHubApp()


@router.get("/repos/{owner}/{repo}/prs")
def list_pull_requests(owner: str, repo: str, state: str = Query("open", regex="^(open|closed|all)$")) -> Dict[str, Any]:
  """List pull requests with basic metadata and head SHAs."""
  gh = _gh()
  url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
  params = {"state": state}
  try:
    resp = requests.get(url, headers=gh.get_headers(), params=params)
    resp.raise_for_status()
    data = resp.json()
    prs = [
      {
        "number": pr.get("number"),
        "title": pr.get("title"),
        "state": pr.get("state"),
        "html_url": pr.get("html_url"),
        "head": {
          "label": pr.get("head", {}).get("label"),
          "ref": pr.get("head", {}).get("ref"),
          "sha": pr.get("head", {}).get("sha"),
        },
        "base": {
          "label": pr.get("base", {}).get("label"),
          "ref": pr.get("base", {}).get("ref"),
          "sha": pr.get("base", {}).get("sha"),
        },
        "updated_at": pr.get("updated_at"),
        "user": {"login": (pr.get("user") or {}).get("login")},
      }
      for pr in data
    ]
    return {"items": prs, "count": len(prs)}
  except Exception as e:
    logger.error(f"Failed to list PRs for {owner}/{repo}: {e}")
    raise HTTPException(status_code=502, detail="Failed to list pull requests")


@router.get("/docs/{owner}/{repo}/{pr_number}")
def get_pr_overview(owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
  """Get PR overview including head sha and files changed."""
  gh = _gh()
  try:
    # Fetch PR details
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    pr_resp = requests.get(url, headers=gh.get_headers())
    pr_resp.raise_for_status()
    pr = pr_resp.json()

    # List files in PR
    files_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
    files_resp = requests.get(files_url, headers=gh.get_headers())
    files_resp.raise_for_status()
    files_json = files_resp.json()
    files = [
      {
        "filename": f.get("filename"),
        "status": f.get("status"),
        "additions": f.get("additions"),
        "deletions": f.get("deletions"),
        "changes": f.get("changes"),
      }
      for f in files_json
    ]

    return {
      "number": pr.get("number"),
      "title": pr.get("title"),
      "state": pr.get("state"),
      "head": pr.get("head", {}),
      "base": pr.get("base", {}),
      "files": files,
      "html_url": pr.get("html_url"),
    }
  except Exception as e:
    logger.error(f"Failed to fetch PR overview for {owner}/{repo}#{pr_number}: {e}")
    raise HTTPException(status_code=502, detail="Failed to fetch PR overview")


@router.get("/docs/{owner}/{repo}/{pr_number}/tree")
def get_pr_tree(owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
  """Get repository tree (all files) at PR head SHA."""
  gh = _gh()
  try:
    # Get PR to fetch head sha
    pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    pr_resp = requests.get(pr_url, headers=gh.get_headers())
    pr_resp.raise_for_status()
    head_sha = (pr_resp.json().get("head") or {}).get("sha")
    if not head_sha:
      raise HTTPException(status_code=404, detail="PR head SHA not found")

    # Use Git Trees API
    tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{head_sha}"
    params = {"recursive": "1"}
    tree_resp = requests.get(tree_url, headers=gh.get_headers(), params=params)
    tree_resp.raise_for_status()
    tree = tree_resp.json()
    # Return a list of paths; the frontend can filter for markdown
    files = [
      {"path": n.get("path"), "type": n.get("type"), "size": n.get("size")}
      for n in tree.get("tree", [])
      if n.get("type") == "blob"
    ]
    return {"head_sha": head_sha, "files": files}
  except HTTPException:
    raise
  except Exception as e:
    logger.error(f"Failed to fetch PR tree for {owner}/{repo}#{pr_number}: {e}")
    raise HTTPException(status_code=502, detail="Failed to fetch PR tree")


@router.get("/docs/{owner}/{repo}/{pr_number}/file")
def get_pr_file(owner: str, repo: str, pr_number: int, path: str) -> Dict[str, Any]:
  """Get raw file content at PR head via Contents API (ref=head sha)."""
  gh = _gh()
  try:
    pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    pr_resp = requests.get(pr_url, headers=gh.get_headers())
    pr_resp.raise_for_status()
    head_sha = (pr_resp.json().get("head") or {}).get("sha")
    if not head_sha:
      raise HTTPException(status_code=404, detail="PR head SHA not found")

    file_data = gh.get_file_contents(owner, repo, path, ref=head_sha)
    content_b64 = file_data.get("content")
    if not content_b64:
      return {"path": path, "encoding": file_data.get("encoding"), "content": ""}

    # Contents API includes newlines in base64 output
    try:
      raw = base64.b64decode(content_b64).decode("utf-8", errors="ignore")
    except Exception:
      raw = ""
    return {"path": path, "ref": head_sha, "content": raw}
  except HTTPException:
    raise
  except Exception as e:
    logger.error(f"Failed to fetch file {path} for {owner}/{repo}#{pr_number}: {e}")
    raise HTTPException(status_code=502, detail="Failed to fetch file content")


@router.get("/diff/{owner}/{repo}/{pr_number}")
def get_pr_diff(owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
  """Get unified diff for PR."""
  gh = _gh()
  try:
    diff_text = gh.get_pull_request_diff(owner, repo, pr_number)
    return {"diff": diff_text}
  except Exception as e:
    logger.error(f"Failed to fetch diff for {owner}/{repo}#{pr_number}: {e}")
    raise HTTPException(status_code=502, detail="Failed to fetch PR diff")


