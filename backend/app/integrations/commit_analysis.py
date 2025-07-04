from typing import Dict, Any, List
import json
import asyncio
import textwrap
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
        
        # Impact scoring calibration examples
        self.CALIBRATION_EXAMPLES = {
            "business_value": {
                "10": "Payment processing system, auth system, core business logic",
                "8": "Customer-facing feature with direct revenue impact",
                "6": "Internal tool that improves team productivity significantly",
                "4": "Nice-to-have feature, UI improvements",
                "2": "Code cleanup, non-critical refactoring",
                "1": "Typo fixes, comment updates"
            },
            "technical_complexity": {
                "10": "Distributed system coordination, complex algorithms (e.g., physics engine)",
                "8": "New service architecture, complex state management",
                "6": "Multi-service integration, moderate algorithmic work",
                "4": "Standard CRUD operations with some business logic",
                "2": "Simple API endpoint, basic UI component",
                "1": "Config changes, simple bug fixes"
            },
            "code_quality": {
                "1.5": "Comprehensive tests (>90% coverage), excellent documentation, follows all patterns",
                "1.2": "Good test coverage (70-90%), clear documentation",
                "1.0": "Adequate tests (50-70%), basic documentation",
                "0.8": "Minimal tests (<50%), sparse documentation",
                "0.5": "No tests, no documentation, technical debt introduced"
            }
        }
    
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
            # Wrap long changes instead of truncating
            wrapped_changes = textwrap.wrap(change, width=72, initial_indent="   • ", subsequent_indent="     ")
            for i, wrapped_line in enumerate(wrapped_changes):
                if i == 0:
                    change_line = f"║{wrapped_line}"
                else:
                    change_line = f"║{wrapped_line}"
                change_line = f"{change_line}{' ' * (79 - len(change_line))}║"
                key_changes_lines.append(change_line)
        
        # Format seniority rationale (wrap long text)
        rationale_text = result.get('seniority_rationale', '')
        rationale_header = "║ Seniority Rationale:"
        rationale_header = f"{rationale_header}{' ' * (79 - len(rationale_header))}║"
        
        rationale_lines = []
        if rationale_text:
            # Wrap the text at ~72 chars per line
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
    
    def _format_impact_analysis_log(self, result: Dict[str, Any], commit_hash: str, repository: str) -> str:
        """Create a nicely formatted log string for impact analysis results."""
        horizontal_line = "═" * 80
        header = f"╔{horizontal_line}╗"
        footer = f"╚{horizontal_line}╝"
        
        # Format the main sections
        title = f"║ IMPACT ANALYSIS: {commit_hash[:8]} - {repository}"
        title = f"{title}{' ' * (79 - len(title))}║"
        
        business_value = f"║ Business Value: {result.get('business_value', 'N/A')}/10"
        business_value = f"{business_value}{' ' * (79 - len(business_value))}║"
        
        technical_complexity = f"║ Technical Complexity: {result.get('technical_complexity', 'N/A')}/10"
        technical_complexity = f"{technical_complexity}{' ' * (79 - len(technical_complexity))}║"
        
        code_quality = f"║ Code Quality: {result.get('code_quality', 'N/A')}x"
        code_quality = f"{code_quality}{' ' * (79 - len(code_quality))}║"
        
        risk_factor = f"║ Risk Factor: {result.get('risk_factor', 'N/A')}x"
        risk_factor = f"{risk_factor}{' ' * (79 - len(risk_factor))}║"
        
        # Calculate impact score for display
        impact_score = result.get('impact_score', 0)
        impact_calc = f"({result.get('business_value', 0)} × {result.get('technical_complexity', 0)} × {result.get('code_quality', 1.0)}) ÷ {result.get('risk_factor', 1.0)}"
        impact_line = f"║ Impact Score: {impact_score} points {impact_calc}"
        impact_line = f"{impact_line}{' ' * (79 - len(impact_line))}║"
        
        # Format dominant category
        category = result.get('dominant_category', 'N/A')
        category_line = f"║ Commit Type: {category}"
        category_line = f"{category_line}{' ' * (79 - len(category_line))}║"
        
        # Format reasoning sections
        divider = f"║{'-' * 78}║"
        
        # Business Value Reasoning
        bv_reasoning_header = "║ Business Value Reasoning:"
        bv_reasoning_header = f"{bv_reasoning_header}{' ' * (79 - len(bv_reasoning_header))}║"
        bv_reasoning_lines = []
        bv_text = result.get('business_value_reasoning', '')
        if bv_text:
            wrapped_lines = textwrap.wrap(bv_text, width=72)
            for line in wrapped_lines:
                line_fmt = f"║   {line}"
                line_fmt = f"{line_fmt}{' ' * (79 - len(line_fmt))}║"
                bv_reasoning_lines.append(line_fmt)
        
        # Technical Complexity Reasoning
        tc_reasoning_header = "║ Technical Complexity Reasoning:"
        tc_reasoning_header = f"{tc_reasoning_header}{' ' * (79 - len(tc_reasoning_header))}║"
        tc_reasoning_lines = []
        tc_text = result.get('technical_complexity_reasoning', '')
        if tc_text:
            wrapped_lines = textwrap.wrap(tc_text, width=72)
            for line in wrapped_lines:
                line_fmt = f"║   {line}"
                line_fmt = f"{line_fmt}{' ' * (79 - len(line_fmt))}║"
                tc_reasoning_lines.append(line_fmt)
        
        # Code Quality Reasoning
        cq_reasoning_header = "║ Code Quality Reasoning:"
        cq_reasoning_header = f"{cq_reasoning_header}{' ' * (79 - len(cq_reasoning_header))}║"
        cq_reasoning_lines = []
        cq_text = result.get('code_quality_reasoning', '')
        if cq_text:
            wrapped_lines = textwrap.wrap(cq_text, width=72)
            for line in wrapped_lines:
                line_fmt = f"║   {line}"
                line_fmt = f"{line_fmt}{' ' * (79 - len(line_fmt))}║"
                cq_reasoning_lines.append(line_fmt)
        
        # Risk Factor Reasoning
        rf_reasoning_header = "║ Risk Factor Reasoning:"
        rf_reasoning_header = f"{rf_reasoning_header}{' ' * (79 - len(rf_reasoning_header))}║"
        rf_reasoning_lines = []
        rf_text = result.get('risk_factor_reasoning', '')
        if rf_text:
            wrapped_lines = textwrap.wrap(rf_text, width=72)
            for line in wrapped_lines:
                line_fmt = f"║   {line}"
                line_fmt = f"{line_fmt}{' ' * (79 - len(line_fmt))}║"
                rf_reasoning_lines.append(line_fmt)
        
        # Assemble the complete log message
        log_parts = [
            "\n",  # Add space before impact analysis
            header,
            title,
            divider,
            business_value,
            technical_complexity,
            code_quality,
            risk_factor,
            divider,
            impact_line,
            category_line,
            divider
        ]
        
        # Add reasoning sections
        if bv_reasoning_lines:
            log_parts.append(bv_reasoning_header)
            log_parts.extend(bv_reasoning_lines)
            log_parts.append(divider)
        
        if tc_reasoning_lines:
            log_parts.append(tc_reasoning_header)
            log_parts.extend(tc_reasoning_lines)
            log_parts.append(divider)
            
        if cq_reasoning_lines:
            log_parts.append(cq_reasoning_header)
            log_parts.extend(cq_reasoning_lines)
            log_parts.append(divider)
            
        if rf_reasoning_lines:
            log_parts.append(rf_reasoning_header)
            log_parts.extend(rf_reasoning_lines)
        
        log_parts.append(footer)
        
        return "\n".join(log_parts)
    
    async def analyze_commit_diff(self, commit_data: Dict[str, Any], ai_client=None, model_name=None) -> Dict[str, Any]:
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
            Dictionary with analysis results including both traditional and impact scoring:
                Traditional scoring:
                - complexity_score: Estimated complexity (1-10)
                - estimated_hours: Estimated time to implement
                - risk_level: Risk assessment (low/medium/high)
                - seniority_score: Code quality and implementation approach rating (1-10)
                - seniority_rationale: Explanation of the seniority score
                - key_changes: List of major changes identified
                
                Impact scoring:
                - impact_business_value: Business impact score (1-10)
                - impact_technical_complexity: Technical complexity score (1-10)
                - impact_code_quality: Code quality multiplier (0.5-1.5)
                - impact_risk_factor: Risk adjustment factor (0.8-2.0)
                - impact_score: Final calculated impact score
                - Various impact reasoning fields
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

            # Run both analyses in parallel for efficiency
            hours_task = self.client.chat.completions.create(**api_params)
            impact_task = self.analyze_commit_impact(commit_data)
            
            # Wait for both to complete
            hours_response, impact_result = await asyncio.gather(hours_task, impact_task)
            
            # Parse the hours response
            hours_result = json.loads(hours_response.choices[0].message.content)
            
            # Combine both results
            combined_result = {
                # Traditional hours-based analysis
                "complexity_score": hours_result.get("complexity_score"),
                "estimated_hours": hours_result.get("estimated_hours"),
                "risk_level": hours_result.get("risk_level"),
                "seniority_score": hours_result.get("seniority_score"),
                "seniority_rationale": hours_result.get("seniority_rationale"),
                "key_changes": hours_result.get("key_changes"),
                
                # Impact scoring analysis (prefixed with impact_)
                "impact_business_value": impact_result.get("business_value"),
                "impact_business_value_reasoning": impact_result.get("business_value_reasoning"),
                "impact_technical_complexity": impact_result.get("technical_complexity"),
                "impact_technical_complexity_reasoning": impact_result.get("technical_complexity_reasoning"),
                "impact_code_quality": impact_result.get("code_quality"),
                "impact_code_quality_reasoning": impact_result.get("code_quality_reasoning"),
                "impact_risk_factor": impact_result.get("risk_factor"),
                "impact_risk_factor_reasoning": impact_result.get("risk_factor_reasoning"),
                "impact_score": impact_result.get("impact_score"),
                "impact_dominant_category": impact_result.get("dominant_category"),
                
                # Metadata
                "analyzed_at": datetime.now().isoformat(),
                "commit_hash": commit_data.get("commit_hash"),
                "repository": commit_data.get("repository"),
                "model_used": self.commit_analysis_model,
                "scoring_methods": ["hours_estimation", "impact_points"]
            }
            
            # Log formatted analysis results (traditional format)
            commit_hash = commit_data.get("commit_hash", "unknown")
            repository = commit_data.get("repository", "unknown")
            formatted_log = self._format_analysis_log(hours_result, commit_hash, repository)
            print(formatted_log)  # Using print for cleaner formatting in console
            
            # Also log impact scoring with detailed format
            if combined_result.get('impact_score'):
                formatted_impact_log = self._format_impact_analysis_log(impact_result, commit_hash, repository)
                print(formatted_impact_log)
            
            return combined_result
            
        except Exception as e:
            return self.error_handling(e)
    
    async def analyze_commit_impact(self, commit_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a commit using the Impact Points System.
        
        Args:
            commit_data: Dictionary containing commit information
            
        Returns:
            Dictionary with impact analysis results including:
                - business_value: Business impact score (1-10)
                - technical_complexity: Technical complexity score (1-10)
                - code_quality: Code quality multiplier (0.5-1.5)
                - risk_factor: Risk adjustment factor (0.8-2.0)
                - impact_score: Final calculated impact score
                - Various reasoning fields for each component
        """
        try:
            # Format calibration examples for the prompt
            business_value_examples = "\n".join([f"Score {k}: {v}" for k, v in self.CALIBRATION_EXAMPLES["business_value"].items()])
            technical_complexity_examples = "\n".join([f"Score {k}: {v}" for k, v in self.CALIBRATION_EXAMPLES["technical_complexity"].items()])
            code_quality_examples = "\n".join([f"Multiplier {k}: {v}" for k, v in self.CALIBRATION_EXAMPLES["code_quality"].items()])
            
            prompt = f"""Analyze this commit using the Impact Points System. You must score exactly according to these definitions.

STEP 1: Classify the commit type
- What type of change is this? (feature/bugfix/refactor/infrastructure/etc)
- What is the primary purpose?

STEP 2: Business Value Score (1-10)
Compare this commit to these canonical examples:
{business_value_examples}

Questions to consider:
- Does this directly impact users or revenue?
- How critical is this to core business operations?
- What happens if this feature/fix doesn't exist?

Your score: ___ (you MUST pick a whole number 1-10)

STEP 3: Technical Complexity Score (1-10)
Compare this commit to these canonical examples:
{technical_complexity_examples}

Questions to consider:
- How many systems/services are involved?
- What's the algorithmic complexity?
- How much domain knowledge is required?
- For game dev: involves physics/rendering/AI? (+2-3 points)

Your score: ___ (you MUST pick a whole number 1-10)

STEP 4: Code Quality Multiplier (0.5-1.5)
{code_quality_examples}

Evaluate:
- Test coverage added/modified
- Documentation completeness
- Code maintainability
- Design patterns used

Your multiplier: ___ (pick from: 0.5, 0.8, 1.0, 1.2, 1.5)

STEP 5: Risk Factor (0.8-2.0)
- 0.8 = Over-engineered for the problem
- 1.0 = Appropriate solution (default)
- 1.2 = Touching critical systems
- 1.5 = High security/financial risk
- 2.0 = Emergency production fix

Your factor: ___

FINAL CALCULATION:
Impact Score = (Business Value × Technical Complexity × Code Quality) / Risk Factor

Commit metadata for context:
Repository: {commit_data.get('repository', '')}
Author: {commit_data.get('author_name', '')} <{commit_data.get('author_email', '')}>
Message: {commit_data.get('message', '')}
Files Changed: {', '.join(commit_data.get('files_changed', []))}
Lines Added: {commit_data.get('additions', 0)}
Lines Deleted: {commit_data.get('deletions', 0)}

Diff:
{commit_data.get('diff', '')}

Output JSON only:
{{
    "business_value": <int>,
    "business_value_reasoning": "<compare to examples>",
    "technical_complexity": <int>,
    "technical_complexity_reasoning": "<compare to examples>",
    "code_quality": <float>,
    "code_quality_reasoning": "<specific evidence>",
    "risk_factor": <float>,
    "risk_factor_reasoning": "<specific evidence>",
    "impact_score": <calculated float>,
    "dominant_category": "<feature|bugfix|refactor|etc>"
}}"""

            # Set up parameters for the API call
            api_params = {
                "model": self.commit_analysis_model,
                "messages": [
                    {
                        "role": "system", 
                        "content": """You are a senior engineering manager analyzing developer productivity using the Impact Points System. 
                        Focus on business value delivered and technical achievement rather than time spent. 
                        Be consistent in scoring by always comparing to the provided examples."""
                    },
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"}
            }
            
            # Only add temperature for models that support it
            if not self._is_reasoning_model(self.commit_analysis_model):
                api_params["temperature"] = 0.15  # Low temperature for consistency

            # Make API call
            response = await self.client.chat.completions.create(**api_params)
            
            # Parse the response
            result = json.loads(response.choices[0].message.content)
            
            # Calculate impact score if not provided
            if "impact_score" not in result or result["impact_score"] is None:
                result["impact_score"] = (
                    result["business_value"] * 
                    result["technical_complexity"] * 
                    result["code_quality"]
                ) / result["risk_factor"]
            
            # Round impact score to 1 decimal place
            result["impact_score"] = round(result["impact_score"], 1)
            
            # Add metadata
            result.update({
                "analyzed_at": datetime.now().isoformat(),
                "commit_hash": commit_data.get("commit_hash"),
                "repository": commit_data.get("repository"),
                "model_used": self.commit_analysis_model,
                "scoring_method": "impact_points"
            })
            
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