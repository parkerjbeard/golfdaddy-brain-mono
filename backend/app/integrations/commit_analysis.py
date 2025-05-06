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
        
        # Format tech debt
        tech_debt = result.get('technical_debt', [])
        tech_debt_header = "║ Technical Debt:"
        tech_debt_header = f"{tech_debt_header}{' ' * (79 - len(tech_debt_header))}║"
        
        tech_debt_lines = []
        for debt in tech_debt:
            if len(debt) > 75:  # Truncate long items
                debt = debt[:72] + "..."
            debt_line = f"║   • {debt}"
            debt_line = f"{debt_line}{' ' * (79 - len(debt_line))}║"
            tech_debt_lines.append(debt_line)
        
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
            
        log_parts.append(divider)
        log_parts.append(tech_debt_header)
        
        if tech_debt_lines:
            log_parts.extend(tech_debt_lines)
        else:
            log_parts.append("║   None specified" + " " * 64 + "║")
            
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
                - key_changes: List of major changes identified
                - technical_debt: Potential technical debt concerns
                - suggestions: Improvement suggestions
        """
        try:
            # Prepare a detailed prompt for the analysis
            prompt = f"""Analyze the following commit and provide a comprehensive technical assessment based on the code changes.
            
            Your goal is to evaluate the code quality, complexity, potential risks, and implementation effort required.
            Carefully examine file types, code patterns, architectural changes, and potential impact on the codebase.
            
            Please format your response as a JSON object with the following structure:
            {{
                "complexity_score": <integer 1-10>,
                "estimated_hours": <number>,
                "risk_level": <"low"|"medium"|"high">, 
                "seniority_score": <integer 1-10>,
                "key_changes": [<string>],
                "technical_debt": [<string>],
                "suggestions": [<string>]
            }}
            
            Analysis guidelines:
            
            - complexity_score: Rate from 1-10 where:
              * 1-3: Simple changes (typo fixes, documentation, minor refactoring)
              * 4-6: Moderate changes (new features, bug fixes, medium refactoring)
              * 7-10: Complex changes (architectural changes, critical system components, high cognitive load)
              
            - estimated_hours: Provide realistic implementation time for an average developer familiar with the codebase.
              Consider testing, documentation, and potential integration challenges.
              
            - risk_level: Assess based on:
              * low: Isolated changes with minimal risk of regression or side effects
              * medium: Changes that touch multiple components or introduce new patterns
              * high: Changes to core functionality, critical paths, or security components
              
            - seniority_score: Rate from 1-10 using this structured evaluation approach:
              1. Analyze the intended function and purpose of the code
              2. Assess implementation quality based on industry best practices
              3. Compare against what an ideal senior implementation would include
              
              Scoring criteria:
              * 1-3: Basic implementation that fulfills functional requirements but shows limited engineering maturity.
                    - Uses simplistic or naive approaches to problems
                    - Lacks appropriate design patterns where beneficial
                    - Minimal consideration of edge cases or error scenarios
                    - Limited abstraction or poor separation of concerns
                    - Little evidence of architectural thinking
              
              * 4-6: Competent implementation showing solid engineering practices.
                    - Appropriate use of common design patterns
                    - Reasonable component structure and organization
                    - Standard error handling strategies
                    - Some consideration for maintainability and readability
                    - Evidence of testing and validation approaches
              
              * 7-10: Sophisticated implementation demonstrating senior-level engineering excellence:
                    - Strategic application of advanced design patterns appropriate to the context
                    - Elegant architectural solutions balancing flexibility and simplicity
                    - Thoughtful abstraction with clear separation of concerns
                    - Performance considerations and optimizations where relevant
                    - Comprehensive handling of edge cases and failure modes
                    - Forward-thinking design enabling future extension and maintenance
                    - Security-conscious implementation where applicable
                    - Evidence of systems thinking beyond the immediate code changes
            
            - key_changes: List the most significant changes, focusing on:
              * Architectural modifications
              * API changes or new endpoints
              * Database schema changes
              * New dependencies or third-party integrations
              * Performance optimizations
              * Security-related changes
              
            - technical_debt: Identify any of the following:
              * Workarounds or temporary solutions
              * Inconsistent patterns or anti-patterns
              * Hardcoded values that should be configurable
              * Missing tests or documentation
              * Potential scalability issues
              * Redundant or duplicate code
              
            - suggestions: Provide actionable recommendations for:
              * Code quality improvements
              * Better architectural approaches
              * Testing strategies
              * Performance optimizations
              * Maintainability enhancements
              * Security improvements
            
            Commit Details:
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
                    {"role": "system", "content": """You are an expert code reviewer and technical analyst with extensive experience in software development.
Your task is to analyze git commit diffs and provide detailed, actionable insights.

When analyzing commits:
1. Focus on the technical impact rather than superficial changes
2. Identify architectural patterns and anti-patterns
3. Assess potential risks to system stability, security, and performance
4. Consider maintainability, readability, and adherence to best practices
5. Provide specific, actionable recommendations (not generic advice)
6. Be objective and thorough in your assessment
7. Pay special attention to security vulnerabilities and edge cases
8. Consider the broader context of the codebase beyond just the changed lines

Your analysis should be technically precise, balanced, and presented in the requested JSON format."""},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"}
            }
            
            # Only add temperature for models that support it
            if not self._is_reasoning_model(self.commit_analysis_model):
                api_params["temperature"] = 0.3  # Lower temperature for more consistent analysis

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