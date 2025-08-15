import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import openai
import requests
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from app.config.settings import settings
from app.integrations.commit_analysis import CommitAnalyzer
from app.models.daily_report import ClarificationRequest, ClarificationStatus

logger = logging.getLogger(__name__)


class AIIntegration:
    """Integration with OpenAI API for various AI-powered tasks."""

    def __init__(self):
        """Initialize the OpenAI integration with API key from settings."""
        self.api_key = settings.OPENAI_API_KEY
        if not self.api_key:
            # In a production system, consider raising an error or having a clear fallback
            logger.error("OpenAI API key not configured in settings. AIIntegration may not function.")
            # raise ValueError("OpenAI API key not configured in settings") # Or handle gracefully
            self.client = None  # Ensure client is None if API key is missing
        else:
            self.client = AsyncOpenAI(api_key=self.api_key)

        self.model = settings.OPENAI_MODEL or "gpt-4-0125-preview"  # General purpose model
        self.code_quality_model = settings.CODE_QUALITY_MODEL or self.model  # Use specific or fallback to general
        self.eod_analysis_model = settings.OPENAI_MODEL or self.model  # Model for EOD analysis

        # Models that might have different parameter support (e.g., for temperature)
        self.reasoning_models = ["o3-mini-", "o4-mini-", "gpt-5", "text-embedding-", "-e-", "text-search-"]

        # Initialize the commit analyzer (assuming it does not need the AI client itself for init)
        self.commit_analyzer = CommitAnalyzer()
        logger.info(
            f"AIIntegration service initialized. General model: {self.model}, Code quality model: {self.code_quality_model}, EOD model: {self.eod_analysis_model}"
        )

    def _is_reasoning_model(self, model_name: str) -> bool:
        """Check if the model is a reasoning model that might not support temperature or other params."""
        if not model_name:
            return False  # Should not happen with proper init
        return any(prefix in model_name for prefix in self.reasoning_models)

    async def _make_openai_call(self, api_params: Dict[str, Any]) -> Optional[ChatCompletion]:
        """Helper function to make calls to OpenAI API, handling cases where client might not be initialized."""
        if not self.client:
            logger.error("OpenAI client not initialized. Cannot make API call.")
            return None
        try:
            model_name = api_params.get("model", "")
            if model_name and (model_name.startswith("gpt-5") or self._is_reasoning_model(model_name)):
                # Convert messages to Responses API input
                messages = api_params.get("messages", [])
                response_format = api_params.get("response_format")
                resp = await self.client.responses.create(
                    model=model_name,
                    input=[{"role": m.get("role"), "content": m.get("content")} for m in messages],
                    response_format=response_format,
                )
                # Normalize to ChatCompletion-like object
                content_text = getattr(resp, "output_text", None) or (
                    resp.choices[0].message.content if hasattr(resp, "choices") and resp.choices else ""
                )

                class _Msg:
                    def __init__(self, content: str):
                        self.content = content

                class _Choice:
                    def __init__(self, content: str):
                        self.message = _Msg(content)

                class _Response:
                    def __init__(self, content: str):
                        self.choices = [_Choice(content)]

                return _Response(content_text or "")
            else:
                response = await self.client.chat.completions.create(**api_params)
                return response
        except openai.APIError as api_err:
            logger.error(f"OpenAI API Error: {api_err}", exc_info=True)
            # Potentially re-raise or return a specific error object/dict
            raise  # Re-raise for the caller to handle or convert to an app-specific exception
        except Exception as e:
            logger.error(f"Unexpected error during OpenAI API call: {e}", exc_info=True)
            raise  # Re-raise

    async def generate_development_task_content(
        self,
        manager_name: str,
        development_area: str,
        task_type: str,
        company_context: Optional[str] = None,
        existing_skills: Optional[List[str]] = None,
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
                "success_metrics": [],
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
            "model": self.model,  # Use the general purpose model or a dedicated one if configured
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert in leadership development and corporate training. Your goal is to create highly relevant and effective development tasks for managers.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }

        try:
            if str(self.model).startswith("gpt-5"):
                # Use Responses API
                resp = await self.client.responses.create(
                    model=self.model,
                    reasoning={"effort": settings.openai_reasoning_effort},
                    input=[
                        {"role": "system", "content": api_params["messages"][0]["content"]},
                        {"role": "user", "content": api_params["messages"][1]["content"]},
                    ],
                    response_format={"type": "json_object"},
                )
                raw_json_output = getattr(resp, "output_text", None) or (
                    resp.choices[0].message.content if hasattr(resp, "choices") and resp.choices else ""
                )
            else:
                response = await self._make_openai_call(api_params)
                raw_json_output = response.choices[0].message.content if response and response.choices else ""
            if not raw_json_output:
                logger.error("AI response for dev task content was empty or malformed.")
                raise ValueError("AI response was empty or malformed.")
            logger.debug(f"Raw AI response for dev task content: {raw_json_output}")
            content = json.loads(raw_json_output)
            for key in ["description", "learning_objectives", "suggested_resources", "success_metrics"]:
                if key not in content:
                    logger.error(f"AI response for dev task content missing key: {key}")
                    raise ValueError(f"AI response malformed, missing key: {key}")
            logger.info(f"Successfully generated development task content for {manager_name} in {development_area}.")
            return content

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse AI-generated JSON for development task content: {e}. Raw: {raw_json_output}",
                exc_info=True,
            )
            # Fallback or error structure
            return {
                "description": "Error: Could not parse AI-generated content.",
                "learning_objectives": [],
                "suggested_resources": [],
                "success_metrics": [],
            }
        except Exception as e:
            logger.error(f"Unexpected error generating development task content: {e}", exc_info=True)
            return {
                "description": f"Error: An unexpected error occurred while generating content: {str(e)}.",
                "learning_objectives": [],
                "suggested_resources": [],
                "success_metrics": [],
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
        return await self.commit_analyzer.analyze_commit_diff(commit_data)

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

        if commit_data := context.get("commit_data"):
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
                {
                    "role": "system",
                    "content": "You are an expert technical writer and documentation specialist. Focus on clarity, completeness, and technical accuracy.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }

        try:
            if str(self.model).startswith("gpt-5"):
                resp = await self.client.responses.create(
                    model=self.model,
                    reasoning={"effort": settings.openai_reasoning_effort},
                    input=[
                        {"role": "system", "content": api_params["messages"][0]["content"]},
                        {"role": "user", "content": api_params["messages"][1]["content"]},
                    ],
                    response_format={"type": "json_object"},
                )
                result_json_str = getattr(resp, "output_text", None) or (
                    resp.choices[0].message.content if hasattr(resp, "choices") and resp.choices else ""
                )
            else:
                response = await self._make_openai_call(api_params)
                result_json_str = response.choices[0].message.content if response and response.choices else ""
            if not result_json_str:
                logger.error("AI response for generate_doc was empty or malformed.")
                return self.error_handling(Exception("AI response was empty or malformed for generate_doc."))
            result = json.loads(result_json_str)
            return {
                **result,
                "metadata": {
                    **(result.get("metadata", {})),
                    "generated_at": datetime.now().isoformat(),
                    "model_used": self.model,
                },
            }
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
        return {"error": True, "message": error_message, "timestamp": datetime.now().isoformat()}

    async def generate_documentation_from_diff(
        self, diff_content: str, existing_docs: Optional[str] = None
    ) -> Dict[str, str]:
        """Generates documentation based on code diffs. Placeholder implementation."""
        logger.warning("generate_documentation_from_diff is a placeholder and not fully implemented.")
        # This would involve a more complex prompt and potentially multiple LLM calls.
        return {
            "new_documentation_section": "Placeholder: Documentation for diff content.",
            "updated_existing_docs": existing_docs or "Placeholder: No existing docs to update.",
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
                {
                    "role": "system",
                    "content": "You are an AI assistant helping to process and understand employee End-of-Day reports.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        raw_json_output = ""  # Initialize for error logging
        try:
            if str(self.eod_analysis_model).startswith("gpt-5"):
                resp = await self.client.responses.create(
                    model=self.eod_analysis_model,
                    reasoning={"effort": settings.openai_reasoning_effort},
                    input=[
                        {"role": "system", "content": api_params["messages"][0]["content"]},
                        {"role": "user", "content": api_params["messages"][1]["content"]},
                    ],
                    response_format={"type": "json_object"},
                )
                raw_json_output = getattr(resp, "output_text", None) or (
                    resp.choices[0].message.content if hasattr(resp, "choices") and resp.choices else ""
                )
            else:
                response = await self._make_openai_call(api_params)
                raw_json_output = response.choices[0].message.content if response and response.choices else ""
            logger.debug(f"Raw AI response for EOD analysis: {raw_json_output}")
            if not raw_json_output:
                logger.error("AI response for EOD analysis was empty or malformed.")
                return self._default_eod_analysis_error_payload("AI response was empty or malformed.")
            analysis_result = json.loads(raw_json_output)

            if "clarification_requests" in analysis_result and isinstance(
                analysis_result["clarification_requests"], list
            ):
                valid_requests = []
                for req_data in analysis_result["clarification_requests"]:
                    if isinstance(req_data, dict) and "question" in req_data and "original_text" in req_data:
                        req_data.setdefault("status", ClarificationStatus.PENDING.value)
                        req_data.setdefault("requested_by_ai", True)
                        try:
                            ClarificationRequest(**req_data)
                            valid_requests.append(req_data)
                        except Exception as val_err:
                            logger.warning(
                                f"Skipping invalid clarification request data (validation error): {req_data}, Error: {val_err}"
                            )
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

        except json.JSONDecodeError as e:
            logger.error(
                f"Error decoding JSON from AI response for EOD analysis: {e}. Raw: {raw_json_output}", exc_info=True
            )
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
            "error_message": error_message,
        }

    async def check_if_clarification_needed(self, report_text: str, ai_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simple check to determine if clarification is needed for a report.
        Returns a single clarification question if needed, or None.
        """
        logger.info("Checking if clarification needed for EOD report")
        if not self.client:
            logger.error("AI client not available for clarification check")
            return {"needs_clarification": False, "clarification_question": None}

        # If AI already found clarification requests, use the first one
        if ai_analysis.get("clarification_requests") and len(ai_analysis["clarification_requests"]) > 0:
            first_request = ai_analysis["clarification_requests"][0]
            return {
                "needs_clarification": True,
                "clarification_question": first_request.get("question"),
                "original_text": first_request.get("original_text"),
            }

        # Otherwise, do a quick check for clarity
        prompt = f"""Review this EOD report and determine if ONE clarification is needed:

{report_text}

If the report is clear and complete, respond with needs_clarification: false.
If ONE specific detail needs clarification to accurately assess the work, provide a single question.

Respond with JSON:
{{
    "needs_clarification": boolean,
    "clarification_question": "single question if needed, null otherwise",
    "original_text": "the specific part needing clarification, null otherwise"
}}
"""

        api_params = {
            "model": self.eod_analysis_model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are reviewing end-of-day reports. Only ask for clarification if absolutely necessary for understanding the work done.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }

        try:
            if str(self.eod_analysis_model).startswith("gpt-5"):
                resp = await self.client.responses.create(
                    model=self.eod_analysis_model,
                    reasoning={"effort": settings.openai_reasoning_effort},
                    input=[
                        {"role": "system", "content": api_params["messages"][0]["content"]},
                        {"role": "user", "content": api_params["messages"][1]["content"]},
                    ],
                    response_format={"type": "json_object"},
                )
                content_text = getattr(resp, "output_text", None) or (
                    resp.choices[0].message.content if hasattr(resp, "choices") and resp.choices else ""
                )
                result = json.loads(content_text or "{}")
            else:
                response = await self._make_openai_call(api_params)
                result = json.loads(response.choices[0].message.content)
            return result
        except Exception as e:
            logger.error(f"Error checking for clarification: {e}", exc_info=True)
            return {"needs_clarification": False, "clarification_question": None}

    async def process_eod_clarification(
        self, original_report: str, user_message: str, conversation_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Process a user's clarification message in the context of their EOD report.
        Determines if more clarification is needed or if the conversation is complete.
        """
        logger.info("Processing EOD clarification conversation")
        if not self.client:
            logger.error("AI client not available for EOD clarification")
            return {
                "response": "I'm having trouble processing your response. Please try again.",
                "needs_clarification": False,
                "conversation_complete": False,
                "error": "AI client not initialized",
            }

        # Build conversation context
        conversation_context = f"Original EOD Report:\n{original_report}\n\n"
        if conversation_history:
            conversation_context += "Previous conversation:\n"
            for exchange in conversation_history[-5:]:  # Last 5 exchanges
                conversation_context += f"User: {exchange.get('user', '')}\n"
                conversation_context += f"AI: {exchange.get('ai', '')}\n\n"

        prompt = f"""{conversation_context}
        
        Latest user message: {user_message}
        
        Based on the original report and conversation, please analyze the user's response and provide a JSON object with:
        - "response": Your response to the user (be conversational and helpful)
        - "needs_clarification": Boolean indicating if you still need more information
        - "conversation_complete": Boolean indicating if you have all the information needed
        - "updated_summary": If you now have enough information, provide an updated summary of their work
        - "updated_hours": If you can now estimate hours more accurately, provide the updated estimate (float)
        - "key_insights": List of any new key achievements or insights from the clarification
        
        Be friendly and conversational. If the user provides the requested clarification, acknowledge it and update your understanding.
        """

        api_params = {
            "model": self.eod_analysis_model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant processing end-of-day work reports. Be conversational and extract clear information about work completed.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }

        try:
            if str(self.eod_analysis_model).startswith("gpt-5"):
                resp = await self.client.responses.create(
                    model=self.eod_analysis_model,
                    input=[
                        {"role": "system", "content": api_params["messages"][0]["content"]},
                        {"role": "user", "content": api_params["messages"][1]["content"]},
                    ],
                    response_format={"type": "json_object"},
                )
                content_text = getattr(resp, "output_text", None) or (
                    resp.choices[0].message.content if hasattr(resp, "choices") and resp.choices else ""
                )
                result = json.loads(content_text or "{}")
            else:
                response = await self._make_openai_call(api_params)
                result = json.loads(response.choices[0].message.content)

                # Ensure all expected fields exist
                result.setdefault("response", "Thank you for the clarification.")
                result.setdefault("needs_clarification", False)
                result.setdefault("conversation_complete", True)
                result.setdefault("updated_summary", None)
                result.setdefault("updated_hours", None)
                result.setdefault("key_insights", [])

                logger.info(f"EOD clarification processed. Needs more info: {result['needs_clarification']}")
                return result
            # If result is empty or missing expected fields, return a friendly fallback
            if not result:
                logger.error("AI response for EOD clarification was empty")
                return {
                    "response": "I understand. Thank you for the information.",
                    "needs_clarification": False,
                    "conversation_complete": True,
                    "error": "Empty AI response",
                }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse EOD clarification response: {e}", exc_info=True)
            return {
                "response": "I understand. Thank you for the clarification.",
                "needs_clarification": False,
                "conversation_complete": True,
                "error": f"JSON decode error: {str(e)}",
            }
        except Exception as e:
            logger.error(f"Error processing EOD clarification: {e}", exc_info=True)
            return {
                "response": "I'm having trouble processing that. Could you please rephrase?",
                "needs_clarification": True,
                "conversation_complete": False,
                "error": str(e),
            }

    async def analyze_semantic_similarity(
        self, text1: str, text2: str, context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze semantic similarity between two pieces of text.
        Used for deduplication between commits and daily reports.
        """
        logger.info("Analyzing semantic similarity for deduplication")
        if not self.client:
            logger.error("AI client not available for similarity analysis")
            return {"similarity_score": 0.0, "is_duplicate": False, "reasoning": "AI client not available"}

        prompt = f"""Compare these two work descriptions and determine if they describe the same work:

        Text 1: {text1}
        Text 2: {text2}
        """

        if context:
            prompt += f"\nAdditional context: {context}"

        prompt += """
        
        Provide a JSON response with:
        - "similarity_score": A float between 0.0 (completely different) and 1.0 (identical work)
        - "is_duplicate": Boolean indicating if these describe the same work (true if similarity > 0.7)
        - "reasoning": Brief explanation of your assessment
        - "overlapping_aspects": List of specific aspects that overlap
        - "unique_to_text1": List of aspects unique to the first text
        - "unique_to_text2": List of aspects unique to the second text
        """

        api_params = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert at analyzing work descriptions and identifying duplicates. Be precise in identifying whether two descriptions refer to the same work.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }

        try:
            response = await self._make_openai_call(api_params)
            if response and response.choices and response.choices[0].message and response.choices[0].message.content:
                result = json.loads(response.choices[0].message.content)

                # Ensure all fields exist
                result.setdefault("similarity_score", 0.0)
                result.setdefault("is_duplicate", result["similarity_score"] > 0.7)
                result.setdefault("reasoning", "")
                result.setdefault("overlapping_aspects", [])
                result.setdefault("unique_to_text1", [])
                result.setdefault("unique_to_text2", [])

                logger.info(f"Similarity analysis complete. Score: {result['similarity_score']}")
                return result
            else:
                logger.error("AI response for similarity analysis was empty")
                return {
                    "similarity_score": 0.0,
                    "is_duplicate": False,
                    "reasoning": "AI response was empty",
                    "overlapping_aspects": [],
                    "unique_to_text1": [],
                    "unique_to_text2": [],
                }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse similarity analysis response: {e}", exc_info=True)
            return {
                "similarity_score": 0.0,
                "is_duplicate": False,
                "reasoning": f"JSON decode error: {str(e)}",
                "overlapping_aspects": [],
                "unique_to_text1": [],
                "unique_to_text2": [],
            }
        except Exception as e:
            logger.error(f"Error in similarity analysis: {e}", exc_info=True)
            return {
                "similarity_score": 0.0,
                "is_duplicate": False,
                "reasoning": f"Error: {str(e)}",
                "overlapping_aspects": [],
                "unique_to_text1": [],
                "unique_to_text2": [],
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
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            "response_format": {"type": "json_object"},
        }

        logger.debug(f"Sending request to LLM for code quality analysis. Model: {self.code_quality_model}")
        raw_json_output = ""  # Initialize for error logging
        try:
            response = await self._make_openai_call(api_params)
            if response and response.choices and response.choices[0].message and response.choices[0].message.content:
                raw_json_output = response.choices[0].message.content
                logger.debug(f"Raw JSON response from LLM for code quality: {raw_json_output}")
                result = json.loads(raw_json_output)

                analysis_result = {
                    **result,
                    "generated_at": datetime.now().isoformat(),
                    "model_used": self.code_quality_model,
                }
                logger.info(f"Successfully completed AI code quality analysis for commit: {commit_message[:70]}")
                return analysis_result
            else:
                logger.error("LLM response for code quality was empty or malformed.")
                return self.error_handling(Exception("LLM response was empty or malformed for code quality."))

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse JSON response from LLM for code quality: {e}. Raw: {raw_json_output}", exc_info=True
            )
            return self.error_handling(Exception(f"LLM returned invalid JSON for code quality: {e}"))
        except Exception as e:
            logger.error(f"Unexpected error during AI code quality analysis: {e}", exc_info=True)
            return self.error_handling(e)

    async def analyze_daily_work(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a full day's worth of commits along with daily report for holistic hour estimation.

        Args:
            context: Dictionary containing:
                - analysis_date: ISO format date string
                - user_name: Name of the developer
                - commits: List of commit summaries
                - total_commits: Number of commits
                - repositories: List of unique repositories
                - total_lines_changed: Sum of additions and deletions
                - daily_report: Optional daily report data

        Returns:
            Dictionary with analysis results including:
                - total_estimated_hours: Total hours for the day
                - average_complexity_score: Average complexity across commits
                - average_seniority_score: Average seniority score
                - work_summary: AI-generated summary of the day's work
                - key_achievements: List of major accomplishments
                - recommendations: Suggestions for improvement
        """
        logger.info(f"Analyzing daily work for {context.get('user_name')} on {context.get('analysis_date')}")

        if not self.client:
            logger.error("AI client not available for daily work analysis")
            return {"total_estimated_hours": 0.0, "error": "AI client not initialized"}

        # Build the prompt using the same calibration guidelines from commit analysis
        prompt = f"""You are analyzing a developer's complete work for {context.get('analysis_date')}.
        
Developer: {context.get('user_name')}
Total Commits: {context.get('total_commits')}
Repositories: {', '.join(context.get('repositories', []))}
Total Lines Changed: {context.get('total_lines_changed')}

"""

        # Add daily report context if available
        if context.get("daily_report"):
            report = context["daily_report"]
            prompt += f"""
Daily Report Summary:
- Summary: {report.get('summary', 'N/A')}
- Hours Reported: {report.get('hours_reported', 0)}
- Challenges: {report.get('challenges', 'None mentioned')}
- Support Needed: {report.get('support_needed', 'None mentioned')}

"""
            if report.get("ai_analysis"):
                ai_analysis = report["ai_analysis"]
                prompt += f"""Previous AI Analysis of Report:
- Estimated Hours: {ai_analysis.get('estimated_hours', 0)}
- Key Achievements: {', '.join(ai_analysis.get('key_achievements', []))}

"""

        # Add commit details
        prompt += "Commits for the day:\n"
        for i, commit in enumerate(context.get("commits", []), 1):
            prompt += f"""
{i}. [{commit['timestamp']}] {commit['repository']}
   Message: {commit['message']}
   Changes: +{commit['additions']} -{commit['deletions']} ({len(commit.get('files_changed', []))} files)
   Previous AI estimate: {commit.get('ai_estimated_hours', 'N/A')} hours
"""

        prompt += """

Based on all commits for the day and any daily report provided, estimate the TOTAL productive hours.

IMPORTANT CALIBRATION GUIDELINES:
- Consider the CUMULATIVE effort across all commits
- Account for context switching between different repositories/features
- Include time for: planning, implementation, testing, code review, documentation
- If commits span different features/repos, add 10-20% overhead for context switching
- If daily report hours differ significantly from commit analysis, provide reasoning

Hours estimation baseline (for the ENTIRE day's work):
• Light day (1-5 small commits, minor fixes): 2-4 hours
• Moderate day (5-15 commits, feature work): 4-6 hours  
• Full day (15-30 commits, complex features): 6-8 hours
• Intensive day (30+ commits, major changes): 8-10 hours

Adjustments:
+10% for work across multiple repositories
+15% for commits showing architectural changes
+20% for commits with extensive testing
-20% for mostly mechanical/generated changes

Respond with a JSON object containing:
{
    "total_estimated_hours": <float with 1 decimal>,
    "average_complexity_score": <int 1-10>,
    "average_seniority_score": <int 1-10>,
    "work_summary": <string summarizing the day's work>,
    "key_achievements": [<list of 3-5 major accomplishments>],
    "hour_estimation_reasoning": <string explaining how you arrived at the total>,
    "consistency_with_report": <boolean, true if aligned with daily report>,
    "recommendations": [<list of 1-3 suggestions for the developer>]
}
"""

        api_params = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a senior engineering manager analyzing developer productivity. Provide accurate hour estimates based on actual work completed.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }

        try:
            response = await self._make_openai_call(api_params)
            if response and response.choices and response.choices[0].message and response.choices[0].message.content:
                result = json.loads(response.choices[0].message.content)

                # Ensure all expected fields exist
                result.setdefault("total_estimated_hours", 0.0)
                result.setdefault("average_complexity_score", 5)
                result.setdefault("average_seniority_score", 5)
                result.setdefault("work_summary", "No summary available")
                result.setdefault("key_achievements", [])
                result.setdefault("hour_estimation_reasoning", "")
                result.setdefault("consistency_with_report", True)
                result.setdefault("recommendations", [])

                # Round hours to 1 decimal place
                result["total_estimated_hours"] = round(float(result["total_estimated_hours"]), 1)

                logger.info(f"✓ Daily work analysis complete: {result['total_estimated_hours']} hours estimated")
                return result
            else:
                logger.error("AI response for daily work analysis was empty")
                return {"total_estimated_hours": 0.0, "error": "Empty AI response"}

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse daily work analysis response: {e}", exc_info=True)
            return {"total_estimated_hours": 0.0, "error": f"JSON decode error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error analyzing daily work: {e}", exc_info=True)
            return {"total_estimated_hours": 0.0, "error": str(e)}

    async def analyze_unified_daily_work(self, prompt: str) -> Dict[str, Any]:
        """
        Analyze unified daily work using a custom prompt provided by the caller.
        This method is designed for flexible analysis of daily work data.

        Args:
            prompt: The complete prompt to send to the AI model

        Returns:
            Dictionary containing the structured response from the AI model
        """
        logger.info("Analyzing unified daily work with custom prompt")

        if not self.client:
            logger.error("AI client not available for unified daily work analysis")
            return {
                "error": "AI client not initialized",
                "message": "OpenAI client is not available. Please check API key configuration.",
                "timestamp": datetime.now().isoformat(),
            }

        # Use gpt-4 for complex reasoning tasks
        model_to_use = self.model

        api_params = {
            "model": model_to_use,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert at analyzing developer work patterns and productivity. Provide detailed, structured analysis based on the data provided.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }

        # Check if model supports temperature parameter
        if not self._is_reasoning_model(model_to_use):
            api_params["temperature"] = 0.7

        try:
            logger.debug(f"Sending unified daily work analysis request to model: {model_to_use}")
            if str(model_to_use).startswith("gpt-5"):
                resp = await self.client.responses.create(
                    model=model_to_use,
                    reasoning={"effort": settings.openai_reasoning_effort},
                    input=[
                        {"role": "system", "content": api_params["messages"][0]["content"]},
                        {"role": "user", "content": api_params["messages"][1]["content"]},
                    ],
                    response_format={"type": "json_object"},
                )
                raw_json_output = getattr(resp, "output_text", None) or (
                    resp.choices[0].message.content if hasattr(resp, "choices") and resp.choices else ""
                )
            else:
                response = await self._make_openai_call(api_params)
                raw_json_output = response.choices[0].message.content if response and response.choices else ""
            logger.debug(f"Raw AI response for unified daily work (first 500 chars): {raw_json_output[:500]}...")
            try:
                result = json.loads(raw_json_output)
                result["_metadata"] = {
                    "generated_at": datetime.now().isoformat(),
                    "model_used": model_to_use,
                    "analysis_type": "unified_daily_work",
                }
                logger.info("Successfully completed unified daily work analysis")
                return result
            except json.JSONDecodeError as json_err:
                logger.error(f"Failed to parse JSON response: {json_err}. Raw output: {raw_json_output}", exc_info=True)
                return {
                    "error": "JSON parsing error",
                    "message": f"Failed to parse AI response as JSON: {str(json_err)}",
                    "raw_response": raw_json_output[:1000],
                    "timestamp": datetime.now().isoformat(),
                }

        except openai.APIError as api_err:
            logger.error(f"OpenAI API error during unified daily work analysis: {api_err}", exc_info=True)
            return {
                "error": "API error",
                "message": f"OpenAI API error: {str(api_err)}",
                "error_type": type(api_err).__name__,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Unexpected error during unified daily work analysis: {e}", exc_info=True)
            return {
                "error": "Unexpected error",
                "message": f"An unexpected error occurred: {str(e)}",
                "error_type": type(e).__name__,
                "timestamp": datetime.now().isoformat(),
            }


# Example of how to potentially get an instance (e.g., using FastAPI dependency injection pattern)
# Needs to be adapted if settings are not directly accessible or if async init is needed.
# _ai_integration_instance = None
# async def get_ai_integration() -> AIIntegration:
#     global _ai_integration_instance
#     if _ai_integration_instance is None:
#         # Consider if AIIntegration init needs to be async if it does IO
#         _ai_integration_instance = AIIntegration()
#     return _ai_integration_instance
