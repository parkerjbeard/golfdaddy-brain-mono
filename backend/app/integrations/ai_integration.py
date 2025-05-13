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
    """Integration with OpenAI API for various AI-powered tasks."""
    
    def __init__(self):
        """Initialize the OpenAI integration with API key from settings."""
        self.api_key = settings.openai_api_key
        if not self.api_key:
            # In a production system, consider raising an error or having a clear fallback
            logger.error("OpenAI API key not configured in settings. AIIntegration may not function.")
            # raise ValueError("OpenAI API key not configured in settings") # Or handle gracefully
            self.client = None # Ensure client is None if API key is missing
        else:
            self.client = AsyncOpenAI(api_key=self.api_key)
        
        self.model = settings.openai_model or "gpt-4-0125-preview"  # General purpose model
        self.code_quality_model = settings.code_quality_model or self.model # Use specific or fallback to general
        self.eod_analysis_model = settings.eod_analysis_model or self.model # Model for EOD analysis
        
        # Models that might have different parameter support (e.g., for temperature)
        self.reasoning_models = [
            "o3-mini-", 
            "o4-mini-",
            "text-embedding-",
            "-e-",
            "text-search-"
        ]
        
        # Initialize the commit analyzer (assuming it does not need the AI client itself for init)
        self.commit_analyzer = CommitAnalyzer()
        logger.info(f"AIIntegration service initialized. General model: {self.model}, Code quality model: {self.code_quality_model}, EOD model: {self.eod_analysis_model}")

    def _is_reasoning_model(self, model_name: str) -> bool:
        """Check if the model is a reasoning model that might not support temperature or other params."""
        if not model_name: return False # Should not happen with proper init
        return any(prefix in model_name for prefix in self.reasoning_models)

    async def _make_openai_call(self, api_params: Dict[str, Any]) -> Optional[ChatCompletion]:
        """Helper function to make calls to OpenAI API, handling cases where client might not be initialized."""
        if not self.client:
            logger.error("OpenAI client not initialized. Cannot make API call.")
            return None
        try:
            response = await self.client.chat.completions.create(**api_params)
            return response
        except openai.APIError as api_err:
            logger.error(f"OpenAI API Error: {api_err}", exc_info=True)
            # Potentially re-raise or return a specific error object/dict
            raise # Re-raise for the caller to handle or convert to an app-specific exception
        except Exception as e:
            logger.error(f"Unexpected error during OpenAI API call: {e}", exc_info=True)
            raise # Re-raise

    async def generate_development_task_content(
        self, 
        manager_name: str, 
        development_area: str, 
        task_type: str,
        company_context: Optional[str] = None,
        existing_skills: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generates content for a manager development task using an AI model.
        """
        logger.info(
            f"Generating development task content for {manager_name} in area '{development_area}' (type: {task_type})."
        )
        if not self.client:
            logger.error("AI client not available for generating development task content.")
            # Return a default/error structure
            return {
                "description": "Error: AI service not available.",
                "learning_objectives": [],
                "suggested_resources": [],
                "success_metrics": []
            }

        prompt = (
            f"Create a detailed and actionable development task for a manager named {manager_name}.\n"
            f"The primary development area is: {development_area}.\n"
            f"This task is a '{task_type}' type task.\n"
        )
        if company_context:
            prompt += f"Consider the following company context: {company_context}\n"
        if existing_skills:
            prompt += f"The manager's existing relevant skills include: {', '.join(existing_skills)}.\n"
        prompt += (
            "Based on this, provide the following as a JSON object:\n"
            "- 'description': A comprehensive description of the development task. This should be specific, measurable, achievable, relevant, and time-bound (SMART) if possible, or guide the manager in setting SMART goals.\n"
            "- 'learning_objectives': A list of 2-4 key learning objectives for this task. Each objective should clearly state what the manager will learn or be able to do upon completion.\n"
            "- 'suggested_resources': A list of 2-4 diverse suggested resources. Examples: specific articles (mention title/source if possible), types of online courses, relevant books, potential mentorship opportunities, or internal company resources/playbooks.\n"
            "- 'success_metrics': A list of 2-4 clear metrics to evaluate the successful completion and impact of this task. These should be observable and, where possible, quantifiable.\n"
            "Ensure the entire output is a single, valid JSON object with only these keys."
        )
        
        api_params = {
            "model": self.model, # Use the general purpose model or a dedicated one if configured
            "messages": [
                {"role": "system", "content": "You are an expert in leadership development and corporate training. Your goal is to create highly relevant and effective development tasks for managers."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.6 # Moderate temperature for creative yet focused content
        }

        try:
            response = await self._make_openai_call(api_params)
            if response and response.choices and response.choices[0].message and response.choices[0].message.content:
                raw_json_output = response.choices[0].message.content
                logger.debug(f"Raw AI response for dev task content: {raw_json_output}")
                content = json.loads(raw_json_output)
                # Basic validation of expected keys
                for key in ["description", "learning_objectives", "suggested_resources", "success_metrics"]:
                    if key not in content:
                        logger.error(f"AI response for dev task content missing key: {key}")
                        raise ValueError(f"AI response malformed, missing key: {key}")
                logger.info(f"Successfully generated development task content for {manager_name} in {development_area}.")
                return content
            else:
                logger.error("AI response for dev task content was empty or malformed.")
                raise ValueError("AI response was empty or malformed.")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI-generated JSON for development task content: {e}. Raw: {raw_json_output}", exc_info=True)
            # Fallback or error structure
            return {
                "description": "Error: Could not parse AI-generated content.",
                "learning_objectives": [],
                "suggested_resources": [],
                "success_metrics": []
            }
        except Exception as e:
            logger.error(f"Unexpected error generating development task content: {e}", exc_info=True)
            return {
                "description": f"Error: An unexpected error occurred while generating content: {str(e)}.",
                "learning_objectives": [],
                "suggested_resources": [],
                "success_metrics": []
            }
    
    # --- Methods from the original file (potentially with minor adjustments for consistency) ---

    async def analyze_commit_diff(self, commit_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a commit diff using OpenAI to provide insights and estimates.
        This method delegates to the CommitAnalyzer class.
        """
        # Assuming CommitAnalyzer is initialized in __init__ and handles its own AI calls if any, or is refactored.
        # If CommitAnalyzer needs self.client, it should be passed during its init or to this method.
        if not self.commit_analyzer:
             logger.error("CommitAnalyzer not initialized.")
             return {"error": "CommitAnalyzer not available"}
        return await self.commit_analyzer.analyze_commit_diff(commit_data, ai_client=self.client, model_name=self.model) # Pass client if needed
    
    async def generate_doc(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate documentation using OpenAI's API.
        """
        logger.info(f"Generating documentation for doc_type: {context.get('doc_type', 'general')}")
        if not self.client:
            logger.error("AI client not available for generating documentation.")
            return self.error_handling(Exception("AI client not initialized"))

        prompt = f"""Generate comprehensive documentation for the following context and provide a JSON response.

        Please format your response as a JSON object with the following structure:
        {{
            "content": "<string>",
            "format": "<string>",
            "sections": [
                {{
                    "title": "<string>",
                    "content": "<string>"
                }}
            ],
            "metadata": {{
                "generated_at": "<timestamp>",
                "doc_type": "<string>",
                "format": "<string>"
            }}
        }}

        Documentation Type: {context.get('doc_type', 'general')}
        Format: {context.get('format', 'markdown')}
        
        Context:
        {context.get('text', '')}
        
        File References:
        {json.dumps(context.get('file_references', []), indent=2)}"""

        if commit_data := context.get('commit_data'):
            prompt += f"""
            
            Commit Information:
            Repository: {commit_data.get('repository', '')}
            Author: {commit_data.get('author_name', '')}
            Message: {commit_data.get('message', '')}
            Files Changed: {', '.join(commit_data.get('files_changed', []))}
            """

        api_params = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are an expert technical writer and documentation specialist. Focus on clarity, completeness, and technical accuracy."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"}
        }
        
        if not self._is_reasoning_model(self.model):
            api_params["temperature"] = 0.7
        
        try:
            response = await self._make_openai_call(api_params)
            if response and response.choices and response.choices[0].message and response.choices[0].message.content:
                result_json_str = response.choices[0].message.content
                result = json.loads(result_json_str)
                return {
                    **result,
                    "metadata": {
                        **(result.get("metadata", {})),
                        "generated_at": datetime.now().isoformat(),
                        "model_used": self.model
                    }
                }
            else:
                logger.error("AI response for generate_doc was empty or malformed.")
                return self.error_handling(Exception("AI response was empty or malformed for generate_doc."))    
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON in generate_doc: {e}. Raw: {result_json_str}", exc_info=True)
            return self.error_handling(e)
        except Exception as e:
            logger.error(f"Error in generate_doc: {e}", exc_info=True)
            return self.error_handling(e)
    
    def error_handling(self, error: Exception) -> Dict[str, Any]:
        """
        Handle errors from OpenAI API.
        """
        error_message = str(error)
        logger.error(f"AIIntegration Error: {error_message}", exc_info=True)
        return {
            "error": True,
            "message": error_message,
            "timestamp": datetime.now().isoformat()
        }

    async def generate_documentation_from_diff(self, diff_content: str, existing_docs: Optional[str] = None) -> Dict[str, str]:
        """Generates documentation based on code diffs. Placeholder implementation."""
        logger.warning("generate_documentation_from_diff is a placeholder and not fully implemented.")
        # This would involve a more complex prompt and potentially multiple LLM calls.
        return {
            "new_documentation_section": "Placeholder: Documentation for diff content.",
            "updated_existing_docs": existing_docs or "Placeholder: No existing docs to update."
        }

    async def analyze_eod_report_text(self, report_text: str) -> Dict[str, Any]:
        """
        Analyzes the raw text of an EOD report using an LLM.
        """
        logger.info(f"Analyzing EOD report text (first 100 chars): {report_text[:100]}...")
        if not self.client:
            logger.error("AI client not available for EOD report analysis.")
            return self._default_eod_analysis_error_payload("AI client not initialized.")

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
        api_params = {
            "model": self.eod_analysis_model,
            "messages": [
                {"role": "system", "content": "You are an AI assistant helping to process and understand employee End-of-Day reports."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2, 
        }
        raw_json_output = "" # Initialize for error logging
        try:
            response = await self._make_openai_call(api_params)
            if response and response.choices and response.choices[0].message and response.choices[0].message.content:
                raw_json_output = response.choices[0].message.content
                logger.debug(f"Raw AI response for EOD analysis: {raw_json_output}")
                analysis_result = json.loads(raw_json_output)

                if "clarification_requests" in analysis_result and isinstance(analysis_result["clarification_requests"], list):
                    valid_requests = []
                    for req_data in analysis_result["clarification_requests"]:
                        if isinstance(req_data, dict) and "question" in req_data and "original_text" in req_data:
                            req_data.setdefault("status", ClarificationStatus.PENDING.value)
                            req_data.setdefault("requested_by_ai", True)
                            # Attempt to create ClarificationRequest model for validation, though we return dict
                            try:
                                ClarificationRequest(**req_data)
                                valid_requests.append(req_data)
                            except Exception as val_err:
                                logger.warning(f"Skipping invalid clarification request data (validation error): {req_data}, Error: {val_err}")
                        else:
                            logger.warning(f"Skipping invalid clarification request data (missing keys): {req_data}")
                    analysis_result["clarification_requests"] = valid_requests
                else:
                    analysis_result["clarification_requests"] = []

                analysis_result.setdefault("key_achievements", [])
                analysis_result.setdefault("estimated_hours", 0.0)
                analysis_result.setdefault("estimated_difficulty", "Unknown")
                analysis_result.setdefault("sentiment", "Neutral")
                analysis_result.setdefault("potential_blockers", [])
                analysis_result.setdefault("summary", "No summary provided.")
                
                logger.info(f"Successfully analyzed EOD report. Summary: {analysis_result.get('summary')}")
                return analysis_result
            else:
                logger.error("AI response for EOD analysis was empty or malformed.")
                return self._default_eod_analysis_error_payload("AI response was empty or malformed.")

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from AI response for EOD analysis: {e}. Raw: {raw_json_output}", exc_info=True)
            return self._default_eod_analysis_error_payload(f"AI response was not valid JSON: {e}")
        except Exception as e:
            logger.error(f"Error during AI EOD report analysis: {e}", exc_info=True)
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
            "error_message": error_message
        }

    async def analyze_commit_code_quality(self, commit_diff: str, commit_message: str) -> Dict[str, Any]:
        """
        Analyzes a commit diff and message for code quality using an LLM.
        """
        logger.info(f"Initiating AI code quality analysis for commit: {commit_message[:70]}...")
        if not self.client:
            logger.error("AI client not available for code quality analysis.")
            return self.error_handling(Exception("AI client not initialized for code quality analysis."))

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

        api_params = {
            "model": self.code_quality_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"}
        }

        if not self._is_reasoning_model(self.code_quality_model):
            api_params["temperature"] = 0.5

        logger.debug(f"Sending request to LLM for code quality analysis. Model: {self.code_quality_model}")
        raw_json_output = "" # Initialize for error logging
        try:
            response = await self._make_openai_call(api_params)
            if response and response.choices and response.choices[0].message and response.choices[0].message.content:
                raw_json_output = response.choices[0].message.content
                logger.debug(f"Raw JSON response from LLM for code quality: {raw_json_output}")
                result = json.loads(raw_json_output)

                analysis_result = {
                    **result,
                    "generated_at": datetime.now().isoformat(),
                    "model_used": self.code_quality_model
                }
                logger.info(f"Successfully completed AI code quality analysis for commit: {commit_message[:70]}")
                return analysis_result
            else:
                logger.error("LLM response for code quality was empty or malformed.")
                return self.error_handling(Exception("LLM response was empty or malformed for code quality."))    

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response from LLM for code quality: {e}. Raw: {raw_json_output}", exc_info=True)
            return self.error_handling(Exception(f"LLM returned invalid JSON for code quality: {e}"))
        except Exception as e:
            logger.error(f"Unexpected error during AI code quality analysis: {e}", exc_info=True)
            return self.error_handling(e)

# Example of how to potentially get an instance (e.g., using FastAPI dependency injection pattern)
# Needs to be adapted if settings are not directly accessible or if async init is needed.
# _ai_integration_instance = None
# async def get_ai_integration() -> AIIntegration:
#     global _ai_integration_instance
#     if _ai_integration_instance is None:
#         # Consider if AIIntegration init needs to be async if it does IO
#         _ai_integration_instance = AIIntegration() 
#     return _ai_integration_instance