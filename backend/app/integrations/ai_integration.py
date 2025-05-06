from typing import Dict, Any, Optional, List
import requests
import json
import os
from datetime import datetime
import openai
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion
import asyncio
import logging

from app.config.settings import settings
from app.integrations.commit_analysis import CommitAnalyzer
from app.models.daily_report import ClarificationRequest, ClarificationStatus

logger = logging.getLogger(__name__)

class AIIntegration:
    """Integration with OpenAI API for documentation generation."""
    
    def __init__(self):
        """Initialize the OpenAI integration with API key from settings."""
        self.api_key = settings.openai_api_key
        if not self.api_key:
            raise ValueError("OpenAI API key not configured in settings")
            
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = settings.openai_model or "gpt-4-0125-preview"  # General purpose model
        self.code_quality_model = settings.code_quality_model or self.model # Use specific or fallback to general
        
        # Models that don't support temperature parameter (typically reasoning/embedding models)
        self.reasoning_models = [
            "o3-mini-", 
            "text-embedding-",
            "-e-",
            "text-search-"
        ]
        
        # Initialize the commit analyzer
        self.commit_analyzer = CommitAnalyzer()
    
    def _is_reasoning_model(self, model_name: str) -> bool:
        """Check if the model is a reasoning model that doesn't support temperature."""
        return any(prefix in model_name for prefix in self.reasoning_models)
    
    async def analyze_commit_diff(self, commit_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a commit diff using OpenAI to provide insights and estimates.
        
        This method delegates to the CommitAnalyzer class.
        
        Args:
            commit_data: Dictionary containing commit information from GitHub
                
        Returns:
            Dictionary with analysis results
        """
        return await self.commit_analyzer.analyze_commit_diff(commit_data)
    
    async def generate_doc(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate documentation using OpenAI's API.
        
        Args:
            context: Dictionary containing:
                - text: The text to use as context
                - file_references: Optional list of file contents
                - doc_type: Type of documentation to generate
                - format: Output format (markdown, html, etc.)
                - commit_data: Optional commit data from GitHub integration
                
        Returns:
            Dictionary with generated documentation
        """
        try:
            # Prepare the prompt for documentation generation
            prompt = f"""Generate comprehensive documentation for the following context and provide a JSON response.

            Please format your response as a JSON object with the following structure:
            {{
                "content": <string>,
                "format": <string>,
                "sections": [
                    {{
                        "title": <string>,
                        "content": <string>
                    }}
                ],
                "metadata": {{
                    "generated_at": <timestamp>,
                    "doc_type": <string>,
                    "format": <string>
                }}
            }}

            Documentation Type: {context.get('doc_type', 'general')}
            Format: {context.get('format', 'markdown')}
            
            Context:
            {context.get('text', '')}
            
            File References:
            {json.dumps(context.get('file_references', []), indent=2)}"""

            # Add commit information if available
            if commit_data := context.get('commit_data'):
                prompt += f"""
                
                Commit Information:
                Repository: {commit_data.get('repository', '')}
                Author: {commit_data.get('author_name', '')}
                Message: {commit_data.get('message', '')}
                Files Changed: {', '.join(commit_data.get('files_changed', []))}
                """

            # Set up parameters for the API call
            api_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are an expert technical writer and documentation specialist. Focus on clarity, completeness, and technical accuracy."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"}
            }
            
            # Only add temperature for models that support it
            if not self._is_reasoning_model(self.model):
                api_params["temperature"] = 0.7  # Higher temperature for more creative documentation
            
            # Make API call to OpenAI with structured output
            response = await self.client.chat.completions.create(**api_params)
            
            # Parse the response
            result = json.loads(response.choices[0].message.content)
            
            return {
                **result,
                "generated_at": datetime.now().isoformat()
            }
            
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

    async def generate_documentation_from_diff(self, diff_content: str, existing_docs: Optional[str] = None) -> Dict[str, str]:
        """Generates documentation based on code diffs."""
        # This method might also need to be async if it uses self.client
        # For now, assuming it's handled or not called in the failing path
        pass

    # Placeholder for EOD Report Analysis
    async def analyze_eod_report_text(self, report_text: str) -> Dict[str, Any]:
        """
        Analyzes the raw text of an EOD report using an LLM.
        - Identifies distinct tasks and key achievements.
        - Estimates hours and difficulty for reported tasks.
        - Generates clarification questions for ambiguities.
        - Assesses overall sentiment.
        - Provides an overall summary.
        Returns a dictionary structured like the AiAnalysis Pydantic model.
        """
        logger.info(f"Analyzing EOD report text (first 100 chars): {report_text[:100]}...")

        prompt = f"""Please analyze the following End-of-Day (EOD) report submitted by an employee.
The report consists of bullet points detailing their work. Your goal is to extract structured information.

EOD Report Text:
---
{report_text}
---

Based on the report, provide a JSON object with the following fields:
- "key_achievements": A list of strings, where each string is a concise summary of a distinct task or achievement mentioned.
- "estimated_hours": A float representing the total estimated hours for all tasks reasonably discernible from the report. If not clearly estimable, default to 0.0 or provide a best guess.
- "estimated_difficulty": A string describing the overall estimated difficulty of the work reported (e.g., "Low", "Medium", "High").
- "sentiment": A string indicating the overall sentiment of the report (e.g., "Positive", "Neutral", "Negative", "Mixed").
- "potential_blockers": A list of strings, each describing a potential blocker or challenge mentioned or implied.
- "summary": A brief (2-4 sentences) textual summary of the EOD report.
- "clarification_requests": A list of JSON objects. Each object should represent a specific point in the EOD report that is unclear and requires clarification to accurately assess the work or estimate time/difficulty. Each object in this list must have the following structure:
    - "question": A string containing the specific question to ask the employee for clarification.
    - "original_text": A string snippet from the EOD report that this question pertains to.
    - "status": Initialize this to "{ClarificationStatus.PENDING.value}".
    - "requested_by_ai": Initialize this to true.

Example of a single clarification_request object:
{{
    "question": "Could you please provide more details on the 'database optimization' task, such as what specific areas were optimized or the approach taken? This will help in estimating the effort.",
    "original_text": "- Worked on database optimization",
    "status": "{ClarificationStatus.PENDING.value}",
    "requested_by_ai": true
}}

If there are no ambiguities requiring clarification, the "clarification_requests" list should be empty.
Ensure your entire response is a single, valid JSON object. Do not include any explanatory text outside of this JSON object.
"""
        try:
            response = await self.client.chat.completions.create(
                model=settings.openai_model,  # Or a specific model for EOD analysis if preferred
                messages=[
                    {"role": "system", "content": "You are an AI assistant helping to process and understand employee End-of-Day reports."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2, # Lower temperature for more deterministic structured output
            )
            
            analysis_json_str = response.choices[0].message.content
            logger.debug(f"Raw AI response for EOD analysis: {analysis_json_str}")
            
            analysis_result = json.loads(analysis_json_str)

            # Validate and structure clarification requests
            if "clarification_requests" in analysis_result and isinstance(analysis_result["clarification_requests"], list):
                valid_requests = []
                for req_data in analysis_result["clarification_requests"]:
                    if isinstance(req_data, dict) and "question" in req_data and "original_text" in req_data:
                        # Ensure default values are set if not provided by AI, though prompt asks for them
                        req_data.setdefault("status", ClarificationStatus.PENDING.value)
                        req_data.setdefault("requested_by_ai", True)
                        valid_requests.append(req_data)
                    else:
                        logger.warning(f"Skipping invalid clarification request data: {req_data}")
                analysis_result["clarification_requests"] = valid_requests
            else:
                analysis_result["clarification_requests"] = [] # Ensure it's an empty list if missing or invalid

            # Ensure all keys from AiAnalysis model are present, defaulting if necessary
            analysis_result.setdefault("key_achievements", [])
            analysis_result.setdefault("estimated_hours", 0.0)
            analysis_result.setdefault("estimated_difficulty", "Unknown")
            analysis_result.setdefault("sentiment", "Neutral")
            analysis_result.setdefault("potential_blockers", [])
            analysis_result.setdefault("summary", "No summary provided.")
            
            logger.info(f"Successfully analyzed EOD report. Summary: {analysis_result.get('summary')}")
            return analysis_result

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from AI response for EOD analysis: {e}")
            logger.error(f"Problematic JSON string: {analysis_json_str}")
            return self._default_eod_analysis_error_payload(f"AI response was not valid JSON: {e}")
        except Exception as e:
            logger.exception(f"Error during AI EOD report analysis: {e}")
            return self._default_eod_analysis_error_payload(str(e))

    def _default_eod_analysis_error_payload(self, error_message: str) -> Dict[str, Any]:
        """Returns a default payload for EOD analysis in case of an error."""
        return {
            "key_achievements": [],
            "estimated_hours": 0.0,
            "estimated_difficulty": "Error",
            "sentiment": "Error",
            "potential_blockers": ["Error during analysis."],
            "summary": f"Failed to analyze EOD report: {error_message}",
            "clarification_requests": [],
            "error": error_message  # Include an error field
        }

    # Placeholder for Code Quality Analysis
    async def analyze_commit_code_quality(self, commit_diff: str, commit_message: str) -> Dict[str, Any]:
        """
        Analyzes a commit diff and message for code quality using an LLM.
        Returns a dictionary with various quality metrics and suggestions.
        """
        logger.info(f"Initiating AI code quality analysis for commit: {commit_message[:70]}...")

        system_prompt = """You are an expert senior software engineer and code reviewer. 
Your task is to meticulously analyze the provided commit diff and commit message. 
Evaluate the code for readability, complexity, maintainability, test coverage, security, performance, and adherence to best practices. 
Provide an estimated seniority level required to produce such a commit. 
Offer constructive feedback, including specific suggestions for improvement and highlighting positive aspects. 
Your response MUST be a single, valid JSON object."""

        user_prompt = f"""Please analyze the following code changes (git diff format) and commit message.

Commit Message:
{commit_message}

Commit Diff:
```diff
{commit_diff}
```

Based on your analysis, provide a JSON object with the following fields:
- "readability_score": A float between 0.0 (very poor) and 1.0 (excellent) assessing code clarity and ease of understanding.
- "complexity_score": A float between 0.0 (very simple) and 1.0 (very complex) considering factors like cyclomatic complexity, cognitive load, and algorithmic complexity.
- "maintainability_score": A float between 0.0 (very difficult to maintain) and 1.0 (very easy to maintain) based on modularity, code structure, and documentation (if any in diff).
- "test_coverage_estimation": A float between 0.0 (no tests or inadequate) and 1.0 (comprehensive tests) based on the changes and any visible test additions/modifications. If no test files are part of the diff, provide a general assessment or indicate inability to determine.
- "security_concerns": A list of strings, each describing a potential security vulnerability or concern identified in the changes. Empty list if none.
- "performance_issues": A list of strings, each describing a potential performance bottleneck or inefficiency. Empty list if none.
- "best_practices_adherence": A list of strings, noting adherence to or violations of common software development best practices (e.g., DRY, SOLID, naming conventions, error handling).
- "suggestions_for_improvement": A list of strings, providing specific, actionable suggestions to improve the code.
- "positive_feedback": A list of strings, highlighting well-implemented patterns, clean code sections, or good practices observed.
- "estimated_seniority_level": A string estimating the seniority level of the developer who might have written this code (e.g., "Junior", "Mid-Level", "Senior", "Staff/Principal").
- "overall_assessment_summary": A brief (2-3 sentences) textual summary of the code quality and the key findings.

Ensure your entire response is a single, valid JSON object.
"""

        try:
            api_params = {
                "model": self.code_quality_model, # Use the dedicated code quality model
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"}
            }

            # Add temperature for models that support it (typically creative tasks, but can be useful for nuanced analysis)
            if not self._is_reasoning_model(self.code_quality_model):
                api_params["temperature"] = 0.5 # Moderate temperature for balanced analysis

            logger.debug(f"Sending request to LLM for code quality analysis. Model: {self.code_quality_model}")
            
            # Make API call to OpenAI (or configured LLM provider)
            response = await self.client.chat.completions.create(**api_params) # Use await for async call
            
            if response.choices and response.choices[0].message and response.choices[0].message.content:
                raw_json_output = response.choices[0].message.content
                logger.debug(f"Raw JSON response from LLM: {raw_json_output}")
                
                try:
                    result = json.loads(raw_json_output)
                except json.JSONDecodeError as json_err:
                    logger.error(f"Failed to parse JSON response from LLM: {json_err}")
                    logger.error(f"LLM Raw Output that caused error: {raw_json_output}")
                    return self.error_handling(Exception(f"LLM returned invalid JSON: {json_err}"))

                analysis_result = {
                    **result, # Spread the LLM's parsed JSON content
                    "generated_at": datetime.now().isoformat(),
                    "model_used": self.code_quality_model # Add model info for tracking
                }
                logger.info(f"Successfully completed AI code quality analysis for commit: {commit_message[:70]}")
                return analysis_result
            else:
                logger.error("LLM response was empty or malformed.")
                return self.error_handling(Exception("LLM response was empty or malformed."))

        except openai.APIError as api_err:
            logger.error(f"OpenAI API Error during code quality analysis: {api_err}", exc_info=True)
            return self.error_handling(api_err)
        except Exception as e:
            logger.error(f"Unexpected error during AI code quality analysis: {e}", exc_info=True)
            return self.error_handling(e)