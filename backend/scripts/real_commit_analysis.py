import sys
import os
import asyncio
import argparse
import requests
from dotenv import load_dotenv
import json
from datetime import datetime

# Load environment variables from backend .env file first
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

# Set minimal required environment variables to avoid validation errors
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", os.getenv("SUPABASE_SERVICE_KEY", "dummy_key_for_testing"))
os.environ.setdefault("SUPABASE_URL", os.getenv("SUPABASE_URL", "https://dummy.supabase.co"))

# Add the app directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.integrations.github_integration import GitHubIntegration
from app.integrations.commit_analysis import CommitAnalyzer
from app.config import settings
from openai import AsyncOpenAI

class PatchedCommitAnalyzer(CommitAnalyzer):
    """A patched version of CommitAnalyzer that properly handles errors for our script."""
    
    def __init__(self):
        """Initialize with AsyncOpenAI client."""
        super().__init__()
        # Override the client to ensure it's async
        self.client = AsyncOpenAI(api_key=self.api_key)
    
    def _is_reasoning_model(self, model_name: str) -> bool:
        """Check if the model is a reasoning model that doesn't support temperature."""
        reasoning_models = [
            "o3-mini-", 
            "o4-mini-",
            "o3-",
            "gpt-5",
            "text-embedding-",
            "-e-",
            "text-search-"
        ]
        result = any(prefix in model_name for prefix in reasoning_models)
        print(f"🔧 Checking model '{model_name}' against prefixes: {reasoning_models}")
        print(f"🔧 Reasoning model result: {result}")
        return result
    
    async def analyze_commit_diff(self, commit_data):
        """
        Analyze a commit diff using AI - patched version that raises exceptions on errors.
        """
        try:
            # Prepare the same prompt as the original
            prompt = f"""You are analyzing a single Git commit with the primary objective of
            estimating the real engineering effort (in hours) required to author
            the change.  After estimating the effort you will also rate the
            complexity and risk, and identify key changes. If the diff reveals
            significant technical debt concerns, reflect that in a lower
            seniority score and mention it in the rationale.  Respond **only**
            with a single
            valid JSON object using the exact keys listed below – no markdown or
            extra commentary.

            Required JSON schema:
                {{
                    "complexity_score": <integer 1-10>,
                    "estimated_hours": <float>,
                    "risk_level": <"low"|"medium"|"high">,
                    "seniority_score": <integer 1-10>,
                    "seniority_rationale": <string>,
                    "key_changes": [<string>]
                }}

            Hours-estimation calibration table (baseline per commit – include
            time for tests, docs and validation):
                • Very simple (≤20 changed lines, trivial fix)……………… 0.25-1 h
                • Simple       (21-100 lines or isolated feature)……… 1-2 h
                • Moderate     (101-300 lines or multi-file feature)… 2-4 h
                • Complex      (301-800 lines or architectural change) 4-8 h
                • Extensive    (>800 lines or large scale refactor)…  8-20 h

            Adjustment modifiers (apply cumulatively then round to 1 decimal):
                +20 %  – non-trivial unit tests or documentation added/updated
                +25 %  – new external integration or infrastructure work
                −30 %  – mostly mechanical or generated changes
                +15 %  – security-critical or high-risk code paths

            Complexity, seniority and risk should be evaluated using standard
            industry heuristics (see OWASP, clean-code, SOLID, etc.).  Make sure
            the final **estimated_hours** is a single floating-point number with
            one decimal place and never zero.

            Seniority-scoring procedure (use every time):
                1. Identify the intended function/purpose of the change.
                2. Envision what an ideal senior-level implementation would look like (architecture, testing, error-handling, perf, security).
                3. Compare the actual diff against this ideal.
                4. Map the result to the 1-10 scale:
                   • 1-3  – Junior-level, basic or naive implementation
                   • 4-6  – Mid-level, competent but with notable gaps
                   • 7-10 – Senior-level craftsmanship and forethought

            Special case – trivial commits:
                If the change is extremely small or mechanical (complexity_score ≤ 3 or ≤ 20 changed lines)
                the seniority dimension is largely irrelevant.  In such cases:
                    • Set seniority_score equal to 10.
                    • Provide a brief seniority_rationale such as "Trivial change – seniority not meaningfully assessable."

            Commit metadata for context – use it but do **not** echo it back:
            Repository: {commit_data.get('repository', '')}
            Author: {commit_data.get('author_name', '')} <{commit_data.get('author_email', '')}>
            Message: {commit_data.get('message', '')}
            Files Changed: {', '.join(commit_data.get('files_changed', []))}
            Lines Added: {commit_data.get('additions', 0)}
            Lines Deleted: {commit_data.get('deletions', 0)}

            Diff:
            {commit_data.get('diff', '')}"""

            # Set up parameters for the API call - no temperature for reasoning models
            api_params = {
                "model": self.commit_analysis_model,
                "messages": [
                    {"role": "system", "content": """You are a senior software engineer specialising in effort estimation and code review. Your foremost task is to determine how many engineering hours were required to implement the provided Git commit. Follow the calibration table and modifiers supplied by the user prompt, be deterministic, and output only the JSON described. In addition, evaluate complexity, risk, seniority and improvement suggestions with professional rigour."""},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"}
            }
            
            # Only add temperature for models that support it
            is_reasoning = self._is_reasoning_model(self.commit_analysis_model)
            print(f"🔧 Is reasoning model: {is_reasoning}")
            if not is_reasoning:
                api_params["temperature"] = 0.15

            print(f"🔧 Using model: {self.commit_analysis_model}")
            print(f"🔧 Temperature included: {'temperature' in api_params}")
            print(f"🔧 Client type: {type(self.client)}")

            # Make API call to OpenAI (Responses API for reasoning/GPT-5)
            if is_reasoning:
                resp = await self.client.responses.create(
                    model=api_params["model"],
                    reasoning={"effort": settings.openai_reasoning_effort},
                    input=[
                        {"role": "system", "content": api_params["messages"][0]["content"]},
                        {"role": "user", "content": api_params["messages"][1]["content"]},
                    ],
                    response_format={"type": "json_object"}
                )
                content_text = getattr(resp, "output_text", None) or (
                    resp.choices[0].message.content if hasattr(resp, "choices") and resp.choices else ""
                )
                response_content = content_text
            else:
                response = await self.client.chat.completions.create(**api_params)
                response_content = response.choices[0].message.content
            
            # Parse and enhance the response
            result = json.loads(response_content)
            result.update({
                "analyzed_at": datetime.now().isoformat(),
                "commit_hash": commit_data.get("commit_hash"),
                "repository": commit_data.get("repository"),
                "model_used": self.commit_analysis_model
            })
            
            # Log formatted analysis results
            commit_hash = commit_data.get("commit_hash", "unknown")
            repository = commit_data.get("repository", "unknown")
            formatted_log = self._format_analysis_log(result, commit_hash, repository)
            print(formatted_log)
            
            return result
            
        except Exception as e:
            print(f"❌ OpenAI API Error: {e}")
            raise e  # Re-raise the exception instead of returning error dict

def get_commit_data_with_fallback(repository: str, commit_hash: str, token: str = None) -> dict:
    """
    Get commit data from GitHub with fallback to unauthenticated requests for public repos.
    """
    owner, repo = repository.split("/")
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_hash}"
    
    # Try with authentication first if token is provided
    if token:
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 401:
                print("⚠️  GitHub token appears to be invalid or expired. Trying without authentication...")
                # Fall back to unauthenticated request
                headers = {"Accept": "application/vnd.github.v3+json"}
                response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch commit with authentication: {e}")
            # Fall back to unauthenticated request
            pass
    
    # Try without authentication (for public repos)
    print("🔓 Attempting to fetch commit data without authentication (public repo)...")
    headers = {"Accept": "application/vnd.github.v3+json"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def get_commit_raw_diff(repository: str, commit_hash: str, token: str = None) -> str:
    """
    Get the raw diff for a specific commit from GitHub with fallback.
    """
    owner, repo = repository.split("/")
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_hash}"
    
    # Try with authentication first if token is provided
    if token:
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3.diff"
        }
        try:
            response = requests.get(url, headers=headers)
            if response.status_code != 401:
                response.raise_for_status()
                return response.text
        except requests.exceptions.RequestException:
            pass
    
    # Try without authentication
    headers = {"Accept": "application/vnd.github.v3.diff"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text

async def main():
    """
    Main function to run the real commit analysis.
    """
    parser = argparse.ArgumentParser(description="Run a real AI analysis on a GitHub commit.")
    parser.add_argument(
        "--repo",
        type=str,
        default="parker84/golfdaddy",
        help="The GitHub repository in 'owner/repo' format."
    )
    parser.add_argument(
        "--commit",
        type=str,
        required=True,
        help="The commit hash to analyze."
    )
    args = parser.parse_args()

    # Check for API keys in environment
    github_token = os.getenv("GITHUB_TOKEN")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not github_token:
        print("⚠️  GITHUB_TOKEN not found. Will try to access public repositories without authentication.")
        print("   For private repos, get a token at: https://github.com/settings/tokens")
    
    if not openai_key:
        print("❌ Error: OPENAI_API_KEY must be set in your environment or .env file.")
        print("   You can get an OpenAI API key at: https://platform.openai.com/api-keys")
        sys.exit(1)

    print(f"🔍 Analyzing commit {args.commit} in repository {args.repo}")

    try:
        # 1. Fetch commit data from GitHub using our fallback method
        print("📡 Fetching commit data from GitHub...")
        
        commit_details_raw = get_commit_data_with_fallback(args.repo, args.commit, github_token)
        
        # Extract relevant information similar to GitHubIntegration.get_commit_diff
        files_changed = []
        additions = 0
        deletions = 0
        
        for file in commit_details_raw.get("files", []):
            files_changed.append(file.get("filename"))
            additions += file.get("additions", 0)
            deletions += file.get("deletions", 0)
        
        commit_details = {
            "commit_hash": args.commit,
            "repository": args.repo,
            "files_changed": files_changed,
            "additions": additions,
            "deletions": deletions,
            "message": commit_details_raw.get("commit", {}).get("message", ""),
            "author": {
                "name": commit_details_raw.get("commit", {}).get("author", {}).get("name"),
                "email": commit_details_raw.get("commit", {}).get("author", {}).get("email"),
                "date": commit_details_raw.get("commit", {}).get("author", {}).get("date"),
            }
        }

        # Get the raw diff
        print("📄 Fetching commit diff...")
        raw_diff = get_commit_raw_diff(args.repo, args.commit, github_token)

        # 2. Prepare data for analysis
        commit_data = {
            "commit_hash": commit_details["commit_hash"],
            "repository": commit_details["repository"],
            "diff": raw_diff,
            "message": commit_details["message"],
            "author_name": commit_details["author"]["name"],
            "author_email": commit_details["author"]["email"],
            "files_changed": commit_details["files_changed"],
            "additions": commit_details["additions"],
            "deletions": commit_details["deletions"],
        }
        
        print("✅ Commit data prepared. Submitting for AI analysis...")
        print(f"📊 Files changed: {len(commit_data['files_changed'])}")
        print(f"📈 Lines added: {commit_data['additions']}, deleted: {commit_data['deletions']}")

        # 3. Analyze the commit data
        print("🤖 Running AI analysis...")
        commit_analyzer = PatchedCommitAnalyzer()
        analysis_result = await commit_analyzer.analyze_commit_diff(commit_data)

        # The result is already logged nicely by the analyzer, but we can print a final confirmation
        if analysis_result and not analysis_result.get("error"):
            print("\n🎉 --- Analysis completed successfully! ---")
        else:
            print("\n❌ --- Analysis failed. ---")
            if analysis_result:
                print(f"Error: {analysis_result.get('message')}")

    except Exception as e:
        print(f"\n💥 An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # The script is async, so we run it in an event loop
    asyncio.run(main()) 