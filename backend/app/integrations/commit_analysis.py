from typing import Dict, Any, List
import json
from datetime import datetime
from openai import OpenAI, AsyncOpenAI

from app.config.settings import settings

class CommitAnalyzer:
    """Integration for analyzing Git commits using AI."""
    
    def __init__(self):
        """Initialize the commit analyzer with API key from settings."""
        self.api_key = settings.openai_api_key
        if not self.api_key:
            raise ValueError("OpenAI API key not configured in settings")
            
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.commit_analysis_model = settings.commit_analysis_model  # Specific model for commit analysis
        
        # Models that don't support temperature parameter (typically reasoning/embedding models)
        self.reasoning_models = [
            "o3-mini-", 
            "o4-mini-",
            "o3-",
            "text-embedding-",
            "-e-",
            "text-search-"
        ]
    
    def _is_reasoning_model(self, model_name: str) -> bool:
        """Check if the model is a reasoning model that doesn't support temperature."""
        return any(prefix in model_name for prefix in self.reasoning_models)
    
    def _format_analysis_log(self, result: Dict[str, Any], commit_hash: str, repository: str) -> str:
        """Create a nicely formatted log string for commit analysis results."""
        horizontal_line = "═" * 80
        header = f"╔{horizontal_line}╗"
        footer = f"╚{horizontal_line}╝"
        
        # Format the main sections
        title = f"║ COMMIT ANALYSIS: {commit_hash[:8]} - {repository}"
        title = f"{title}{' ' * (79 - len(title))}║"
        
        complexity = f"║ Complexity Score: {result.get('complexity_score', 'N/A')}/10"
        complexity = f"{complexity}{' ' * (79 - len(complexity))}║"
        
        hours = f"║ Estimated Hours: {result.get('estimated_hours', 'N/A')}"
        hours = f"{hours}{' ' * (79 - len(hours))}║"
        
        risk = f"║ Risk Level: {result.get('risk_level', 'N/A')}"
        risk = f"{risk}{' ' * (79 - len(risk))}║"
        
        seniority = f"║ Seniority Score: {result.get('seniority_score', 'N/A')}/10"
        seniority = f"{seniority}{' ' * (79 - len(seniority))}║"
        
        # Format key changes
        key_changes = result.get('key_changes', [])
        key_changes_header = "║ Key Changes:"
        key_changes_header = f"{key_changes_header}{' ' * (79 - len(key_changes_header))}║"
        
        key_changes_lines = []
        for change in key_changes:
            if len(change) > 75:  # Truncate long items
                change = change[:72] + "..."
            change_line = f"║   • {change}"
            change_line = f"{change_line}{' ' * (79 - len(change_line))}║"
            key_changes_lines.append(change_line)
        
        # Format seniority rationale (wrap long text)
        rationale_text = result.get('seniority_rationale', '')
        rationale_header = "║ Seniority Rationale:"
        rationale_header = f"{rationale_header}{' ' * (79 - len(rationale_header))}║"
        
        rationale_lines = []
        if rationale_text:
            # Wrap the text at ~72 chars per line
            import textwrap
            wrapped_lines = textwrap.wrap(rationale_text, width=72)
            for line in wrapped_lines:
                line_fmt = f"║   {line}"
                line_fmt = f"{line_fmt}{' ' * (79 - len(line_fmt))}║"
                rationale_lines.append(line_fmt)
        
        # Assemble the complete log message
        divider = f"║{'-' * 78}║"
        log_parts = [
            header,
            title,
            divider,
            complexity,
            hours,
            risk,
            seniority,
            divider,
            key_changes_header
        ]
        
        if key_changes_lines:
            log_parts.extend(key_changes_lines)
        else:
            log_parts.append("║   None specified" + " " * 64 + "║")
            
        if rationale_lines:
            log_parts.append(divider)
            log_parts.append(rationale_header)
            log_parts.extend(rationale_lines)
        
        log_parts.append(footer)
        
        return "\n".join(log_parts)
    
    async def analyze_commit_diff(self, commit_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a commit diff using AI to provide insights and estimates.
        
        Args:
            commit_data: Dictionary containing commit information from GitHub:
                - diff: The commit diff content
                - message: The commit message
                - repository: Repository name
                - author_name: Author name
                - author_email: Author email
                - files_changed: List of files changed
                - additions: Number of lines added
                - deletions: Number of lines deleted
                
        Returns:
            Dictionary with analysis results including:
                - complexity_score: Estimated complexity (1-10)
                - estimated_hours: Estimated time to implement
                - risk_level: Risk assessment (low/medium/high)
                - seniority_score: Code quality and implementation approach rating (1-10)
                - seniority_rationale: Explanation of the seniority score
                - key_changes: List of major changes identified
        """
        try:
            # Prepare a detailed prompt for the analysis
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

            # Set up parameters for the API call
            api_params = {
                "model": self.commit_analysis_model,
                "messages": [
                    {"role": "system", "content": """You are a senior software engineer specialising in effort estimation and code review. Your foremost task is to determine how many engineering hours were required to implement the provided Git commit. Follow the calibration table and modifiers supplied by the user prompt, be deterministic, and output only the JSON described. In addition, evaluate complexity, risk, seniority and improvement suggestions with professional rigour."""},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"}
            }
            
            # Only add temperature for models that support it
            if not self._is_reasoning_model(self.commit_analysis_model):
                api_params["temperature"] = 0.15  # Lower temperature for higher determinism in hour estimation

            # Make API call to OpenAI using the commit-specific model
            response = await self.client.chat.completions.create(**api_params)
            
            # Parse and enhance the response
            result = json.loads(response.choices[0].message.content)
            result.update({
                "analyzed_at": datetime.now().isoformat(),
                "commit_hash": commit_data.get("commit_hash"),
                "repository": commit_data.get("repository"),
                "model_used": self.commit_analysis_model  # Include the model used in the response
            })
            
            # Log formatted analysis results
            commit_hash = commit_data.get("commit_hash", "unknown")
            repository = commit_data.get("repository", "unknown")
            formatted_log = self._format_analysis_log(result, commit_hash, repository)
            print(formatted_log)  # Using print for cleaner formatting in console
            
            return result
            
        except Exception as e:
            return self.error_handling(e)
    
    def error_handling(self, error: Exception) -> Dict[str, Any]:
        """
        Handle errors from OpenAI API.
        
        Args:
            error: The error that occurred
            
        Returns:
            Dictionary with error details
        """
        error_message = str(error)
        
        # Log the error (in a real implementation)
        print(f"OpenAI API Error: {error_message}")
        
        return {
            "error": True,
            "message": error_message,
            "timestamp": datetime.now().isoformat()
        } 