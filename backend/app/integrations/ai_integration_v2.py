"""
Standardized AI Integration with consistent API usage.
Removes branchy gpt-5 conditional code and uses Structured Outputs consistently.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from app.config.settings import settings
from app.models.daily_report import ClarificationStatus

logger = logging.getLogger(__name__)


class AIIntegrationV2:
    """Standardized integration with OpenAI API using consistent patterns."""

    def __init__(self):
        """Initialize the OpenAI integration with standardized configuration."""
        self.api_key = settings.OPENAI_API_KEY
        if not self.api_key:
            logger.error("OpenAI API key not configured in settings")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=self.api_key)

        # Use standardized models
        self.model = settings.OPENAI_MODEL or "gpt-4-turbo-preview"
        self.code_quality_model = settings.CODE_QUALITY_MODEL or self.model
        self.eod_analysis_model = settings.OPENAI_MODEL or self.model
        logger.info(f"AIIntegrationV2 initialized. Model: {self.model}")

    async def _make_completion_request(
        self,
        messages: List[ChatCompletionMessageParam],
        model: Optional[str] = None,
        response_format: Optional[Dict[str, str]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        """
        Make a standardized completion request to OpenAI.

        Args:
            messages: Chat messages
            model: Model to use (defaults to self.model)
            response_format: Response format (e.g., {"type": "json_object"})
            temperature: Temperature for sampling
            max_tokens: Maximum tokens in response

        Returns:
            Response content as string
        """
        if not self.client:
            logger.error("OpenAI client not initialized")
            return None

        model = model or self.model

        try:
            # Build request parameters
            params = {"model": model, "messages": messages, "temperature": temperature}

            if response_format:
                params["response_format"] = response_format

            if max_tokens:
                params["max_tokens"] = max_tokens

            # Make request
            response = await self.client.chat.completions.create(**params)

            # Extract content
            if response.choices and response.choices[0].message:
                return response.choices[0].message.content

            logger.error("Empty response from OpenAI")
            return None

        except Exception as e:
            logger.error(f"OpenAI API error: {e}", exc_info=True)
            return None

    async def analyze_commit_diff(self, commit_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a commit diff using standardized API calls.

        Args:
            commit_data: Commit data including diff

        Returns:
            Analysis results
        """
        diff = commit_data.get("diff", "")
        message = commit_data.get("message", "")

        if not diff:
            return {"error": "No diff provided"}

        prompt = f"""Analyze this commit and provide structured insights.

Commit Message: {message}

Diff:
```diff
{diff[:3000]}  # Truncate for token limits
```

Provide a JSON response with:
- estimated_hours: Float, estimated hours to complete this work
- complexity_score: Integer 1-10
- seniority_score: Integer 1-10 (junior to principal)
- key_changes: List of key changes made
- potential_issues: List of potential issues or concerns
- suggestions: List of improvement suggestions
"""

        messages = [
            {"role": "system", "content": "You are an expert code reviewer analyzing commit changes."},
            {"role": "user", "content": prompt},
        ]

        response = await self._make_completion_request(
            messages, response_format={"type": "json_object"}, temperature=0.3
        )

        if not response:
            return {"error": "Failed to analyze commit"}

        try:
            result = json.loads(response)
            result["analyzed_at"] = datetime.now().isoformat()
            result["model_used"] = self.model
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return {"error": "Invalid response format"}

    async def generate_development_task_content(
        self,
        manager_name: str,
        development_area: str,
        task_type: str,
        company_context: Optional[str] = None,
        existing_skills: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        v1 compatibility: generate development task content. Prompt retained verbatim.
        """
        if not self.client:
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

        messages: List[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": "You are an expert in leadership development and corporate training. Your goal is to create highly relevant and effective development tasks for managers.",
            },
            {"role": "user", "content": prompt},
        ]
        raw = await self._make_completion_request(messages, response_format={"type": "json_object"})
        if not raw:
            return {
                "description": "Error: Could not generate content.",
                "learning_objectives": [],
                "suggested_resources": [],
                "success_metrics": [],
            }
        try:
            data = json.loads(raw)
            for k in ("description", "learning_objectives", "suggested_resources", "success_metrics"):
                data.setdefault(k, [] if k != "description" else "")
            return data
        except json.JSONDecodeError:
            return {
                "description": "Error: Could not parse AI-generated content.",
                "learning_objectives": [],
                "suggested_resources": [],
                "success_metrics": [],
            }

    async def generate_documentation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate documentation using standardized API.

        Args:
            context: Documentation context

        Returns:
            Generated documentation
        """
        doc_type = context.get("doc_type", "general")
        content = context.get("text", "")

        prompt = f"""Generate comprehensive {doc_type} documentation.

Context:
{content}

Provide a JSON response with:
- content: Main documentation content (markdown)
- sections: Array of sections with title and content
- metadata: Object with doc_type, format, keywords
- summary: Brief summary of the documentation
"""

        messages = [
            {
                "role": "system",
                "content": "You are an expert technical writer creating clear, comprehensive documentation.",
            },
            {"role": "user", "content": prompt},
        ]

        response = await self._make_completion_request(
            messages, response_format={"type": "json_object"}, temperature=0.5, max_tokens=2000
        )

        if not response:
            return {"error": "Failed to generate documentation"}

        try:
            result = json.loads(response)
            result["generated_at"] = datetime.now().isoformat()
            result["model_used"] = self.model
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return {"error": "Invalid response format"}

    async def analyze_eod_report(self, report_text: str) -> Dict[str, Any]:
        """
        Analyze an end-of-day report using standardized API.

        Args:
            report_text: EOD report text

        Returns:
            Analysis results
        """
        prompt = f"""Analyze this End-of-Day report and extract structured information.

Report:
{report_text}

Provide a JSON response with:
- key_achievements: List of key accomplishments
- estimated_hours: Total estimated hours worked
- estimated_difficulty: Overall difficulty (Low/Medium/High)
- sentiment: Overall sentiment (Positive/Neutral/Negative)
- potential_blockers: List of potential blockers mentioned
- summary: 2-3 sentence summary
- clarification_requests: List of items needing clarification
  Each item should have:
  - question: The clarification question
  - original_text: The unclear text from the report
  - status: "pending"
  - requested_by_ai: true
"""

        messages = [
            {
                "role": "system",
                "content": "You are analyzing employee work reports to extract insights and identify areas needing clarification.",
            },
            {"role": "user", "content": prompt},
        ]

        response = await self._make_completion_request(
            messages, response_format={"type": "json_object"}, temperature=0.3
        )

        if not response:
            return {"key_achievements": [], "estimated_hours": 0.0, "error": "Failed to analyze report"}

        try:
            result = json.loads(response)

            # Ensure all fields exist with defaults
            result.setdefault("key_achievements", [])
            result.setdefault("estimated_hours", 0.0)
            result.setdefault("estimated_difficulty", "Unknown")
            result.setdefault("sentiment", "Neutral")
            result.setdefault("potential_blockers", [])
            result.setdefault("summary", "No summary available")
            result.setdefault("clarification_requests", [])

            # Validate clarification requests
            valid_requests = []
            for req in result.get("clarification_requests", []):
                if isinstance(req, dict) and "question" in req and "original_text" in req:
                    req.setdefault("status", ClarificationStatus.PENDING.value)
                    req.setdefault("requested_by_ai", True)
                    valid_requests.append(req)
            result["clarification_requests"] = valid_requests

            result["analyzed_at"] = datetime.now().isoformat()
            result["model_used"] = self.model

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return {"key_achievements": [], "estimated_hours": 0.0, "error": "Invalid response format"}

    async def analyze_eod_report_text(self, report_text: str) -> Dict[str, Any]:
        """
        v1 compatibility: analyze raw EOD report text. Prompt retained verbatim.
        """
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

If there are no ambiguities requiring clarification, the "clarification_requests" list should be empty.
Ensure your entire response is a single, valid JSON object. Do not include any explanatory text outside of this JSON object.
"""
        messages: List[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": "You are an AI assistant helping to process and understand employee End-of-Day reports.",
            },
            {"role": "user", "content": prompt},
        ]
        raw = await self._make_completion_request(
            messages, model=self.eod_analysis_model, response_format={"type": "json_object"}, temperature=0.3
        )
        if not raw:
            return {"key_achievements": [], "estimated_hours": 0.0, "error": "Failed to analyze report"}
        try:
            data = json.loads(raw)
            data.setdefault("clarification_requests", [])
            data.setdefault("key_achievements", [])
            data.setdefault("estimated_hours", 0.0)
            data.setdefault("estimated_difficulty", "Unknown")
            data.setdefault("sentiment", "Neutral")
            data.setdefault("potential_blockers", [])
            data.setdefault("summary", "No summary provided.")
            valid = []
            for req in data.get("clarification_requests", []):
                if isinstance(req, dict) and "question" in req and "original_text" in req:
                    req.setdefault("status", ClarificationStatus.PENDING.value)
                    req.setdefault("requested_by_ai", True)
                    valid.append(req)
            data["clarification_requests"] = valid
            return data
        except json.JSONDecodeError:
            return {"key_achievements": [], "estimated_hours": 0.0, "error": "Invalid response format"}

    async def analyze_code_quality(self, commit_diff: str, commit_message: str) -> Dict[str, Any]:
        """
        Analyze code quality using standardized API.

        Args:
            commit_diff: Git diff content
            commit_message: Commit message

        Returns:
            Code quality analysis
        """
        prompt = f"""Analyze the code quality of these changes.

Commit Message: {commit_message}

Diff:
```diff
{commit_diff[:5000]}  # Truncate for token limits
```

Provide a JSON response with:
- readability_score: Float 0-1 (clarity and ease of understanding)
- complexity_score: Float 0-1 (cyclomatic complexity, cognitive load)
- maintainability_score: Float 0-1 (modularity, structure, documentation)
- test_coverage_estimation: Float 0-1 (test adequacy)
- security_concerns: List of security issues
- performance_issues: List of performance concerns
- best_practices_adherence: List of best practice observations
- suggestions_for_improvement: List of specific suggestions
- positive_feedback: List of well-done aspects
- estimated_seniority_level: Junior/Mid-Level/Senior/Staff/Principal
- overall_assessment_summary: 2-3 sentence summary
"""

        messages = [
            {
                "role": "system",
                "content": "You are an expert senior software engineer performing thorough code review.",
            },
            {"role": "user", "content": prompt},
        ]

        response = await self._make_completion_request(
            messages, model=self.code_quality_model, response_format={"type": "json_object"}, temperature=0.3
        )

        if not response:
            return {"error": "Failed to analyze code quality"}

        try:
            result = json.loads(response)
            result["analyzed_at"] = datetime.now().isoformat()
            result["model_used"] = self.code_quality_model
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return {"error": "Invalid response format"}

    async def analyze_commit_code_quality(self, commit_diff: str, commit_message: str) -> Dict[str, Any]:
        """
        v1 compatibility: code quality analysis. Prompt retained verbatim.
        """
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
- "readability_score": A float 0-1
- "complexity_score": A float 0-1
- "maintainability_score": A float 0-1
- "test_coverage_estimation": A float 0-1
- "security_concerns": A list of strings describing any potential security issues
- "performance_issues": A list of strings describing any potential performance issues
- "best_practices_adherence": A list of observations regarding adherence to best practices
- "suggestions_for_improvement": A list of concrete suggestions for improvement
- "positive_feedback": A list of aspects that are well-done
- "estimated_seniority_level": One of: Junior, Mid-Level, Senior, Staff, Principal
- "overall_assessment_summary": A brief 2-3 sentence summary of the overall code quality
"""

        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        raw = await self._make_completion_request(
            messages, model=self.code_quality_model, response_format={"type": "json_object"}, temperature=0.3
        )
        if not raw:
            return {"error": "Failed to analyze code quality"}
        try:
            data = json.loads(raw)
            data.setdefault("readability_score", 0.0)
            data.setdefault("complexity_score", 0.0)
            data.setdefault("maintainability_score", 0.0)
            data.setdefault("test_coverage_estimation", 0.0)
            data.setdefault("security_concerns", [])
            data.setdefault("performance_issues", [])
            data.setdefault("best_practices_adherence", [])
            data.setdefault("suggestions_for_improvement", [])
            data.setdefault("positive_feedback", [])
            data.setdefault("estimated_seniority_level", "Unknown")
            data.setdefault("overall_assessment_summary", "")
            data["analyzed_at"] = datetime.now().isoformat()
            data["model_used"] = self.code_quality_model
            return data
        except json.JSONDecodeError:
            return {"error": "Invalid response format"}

    async def analyze_semantic_similarity(
        self, text1: str, text2: str, context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze semantic similarity between two texts.

        Args:
            text1: First text
            text2: Second text
            context: Additional context

        Returns:
            Similarity analysis
        """
        prompt = f"""Compare these two work descriptions for similarity.

Text 1: {text1}
Text 2: {text2}
"""

        if context:
            prompt += f"\nContext: {context}"

        prompt += """

Provide a JSON response with:
- similarity_score: Float 0-1 (0=different, 1=identical)
- is_duplicate: Boolean (true if similarity > 0.7)
- reasoning: Brief explanation
- overlapping_aspects: List of common elements
- unique_to_text1: List of unique elements in text 1
- unique_to_text2: List of unique elements in text 2
"""

        messages = [
            {
                "role": "system",
                "content": "You are analyzing work descriptions to identify duplicates and similarities.",
            },
            {"role": "user", "content": prompt},
        ]

        response = await self._make_completion_request(
            messages, response_format={"type": "json_object"}, temperature=0.3
        )

        if not response:
            return {"similarity_score": 0.0, "is_duplicate": False, "error": "Failed to analyze similarity"}

        try:
            result = json.loads(response)

            # Ensure all fields exist
            result.setdefault("similarity_score", 0.0)
            result.setdefault("is_duplicate", result["similarity_score"] > 0.7)
            result.setdefault("reasoning", "")
            result.setdefault("overlapping_aspects", [])
            result.setdefault("unique_to_text1", [])
            result.setdefault("unique_to_text2", [])

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return {"similarity_score": 0.0, "is_duplicate": False, "error": "Invalid response format"}

    async def check_if_clarification_needed(self, report_text: str, ai_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        v1 compatibility: quick check for clarification. Prompt retained verbatim.
        """
        if ai_analysis.get("clarification_requests"):
            first = ai_analysis["clarification_requests"][0]
            return {
                "needs_clarification": True,
                "clarification_question": first.get("question"),
                "original_text": first.get("original_text"),
            }

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

        messages: List[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": "You are reviewing end-of-day reports. Only ask for clarification if absolutely necessary for understanding the work done.",
            },
            {"role": "user", "content": prompt},
        ]
        raw = await self._make_completion_request(
            messages, model=self.eod_analysis_model, response_format={"type": "json_object"}, temperature=0.3
        )
        if not raw:
            return {"needs_clarification": False, "clarification_question": None}
        try:
            data = json.loads(raw)
            data.setdefault("needs_clarification", False)
            data.setdefault("clarification_question", None)
            data.setdefault("original_text", None)
            return data
        except json.JSONDecodeError:
            return {"needs_clarification": False, "clarification_question": None}

    async def process_eod_clarification(
        self,
        user_message: str,
        original_report: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        v1 compatibility: process a clarification reply. Prompt retained verbatim.
        """
        conversation_context = f"Original EOD Report:\n{original_report}\n\n"
        if conversation_history:
            conversation_context += "Previous conversation:\n"
            for exchange in conversation_history[-5:]:
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

        messages: List[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": "You are a helpful AI assistant processing end-of-day work reports. Be conversational and extract clear information about work completed.",
            },
            {"role": "user", "content": prompt},
        ]
        raw = await self._make_completion_request(
            messages, model=self.eod_analysis_model, response_format={"type": "json_object"}, temperature=0.3
        )
        if not raw:
            return {
                "response": "I'm having trouble processing your response. Please try again.",
                "needs_clarification": False,
                "conversation_complete": False,
                "error": "AI client not available or empty response",
            }
        try:
            data = json.loads(raw)
            data.setdefault("response", "Thank you for the clarification.")
            data.setdefault("needs_clarification", False)
            data.setdefault("conversation_complete", True)
            data.setdefault("updated_summary", None)
            data.setdefault("updated_hours", None)
            data.setdefault("key_insights", [])
            return data
        except json.JSONDecodeError:
            return {
                "response": "I understand. Thank you for the clarification.",
                "needs_clarification": False,
                "conversation_complete": True,
                "error": "Invalid response format",
            }

    async def refine_document(self, original_content: str, feedback: str, path: Optional[str] = None) -> Optional[str]:
        """Refine markdown documentation based on feedback and return updated content."""
        messages: List[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": "You are an expert technical writer. Improve the provided markdown based on the user's feedback. Keep the structure, accuracy, and frontmatter. Return only full updated markdown, no extra commentary.",
            },
            {
                "role": "user",
                "content": (
                    f"File: {path or 'document.md'}\n\n"
                    f"Original Markdown:\n\n{original_content}\n\n"
                    f"Feedback:\n\n{feedback}\n\n"
                    "Please produce the refined full markdown document."
                ),
            },
        ]
        return await self._make_completion_request(messages, temperature=0.3, max_tokens=3000)

    async def update_doc(self, ai_input: Dict[str, Any]) -> Optional[str]:
        """Backward-compatible alias used by services. ai_input requires original_content and feedback."""
        original = ai_input.get("original_content", "")
        feedback = ai_input.get("feedback", "")
        path = ai_input.get("path")
        return await self.refine_document(original, feedback, path)

    async def refine_patch(self, patch_diff: str, feedback: str) -> Optional[str]:
        """Refine a unified diff patch based on feedback; return an updated unified diff only."""
        messages: List[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": "You are an expert documentation editor. Given a unified diff and feedback, return an improved unified diff making the requested changes. Output ONLY the diff, no prose.",
            },
            {
                "role": "user",
                "content": (
                    "Original patch (unified diff):\n\n"
                    + patch_diff[:12000]
                    + "\n\nFeedback:\n\n"
                    + feedback
                    + "\n\nReturn only the updated unified diff."
                ),
            },
        ]
        return await self._make_completion_request(messages, temperature=0.3, max_tokens=3000)

    async def analyze_daily_work(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a full day's work using standardized API.

        Args:
            context: Daily work context

        Returns:
            Daily analysis
        """
        user_name = context.get("user_name", "Unknown")
        analysis_date = context.get("analysis_date", "Unknown")
        total_commits = context.get("total_commits", 0)
        repositories = context.get("repositories", [])
        total_lines = context.get("total_lines_changed", 0)

        prompt = f"""Analyze this developer's complete work for {analysis_date}.

Developer: {user_name}
Total Commits: {total_commits}
Repositories: {', '.join(repositories)}
Total Lines Changed: {total_lines}

Commits:
"""

        for i, commit in enumerate(context.get("commits", [])[:20], 1):
            prompt += f"""
{i}. [{commit['timestamp']}] {commit['repository']}
   Message: {commit['message']}
   Changes: +{commit['additions']} -{commit['deletions']}
"""

        prompt += """

Provide a JSON response with:
- total_estimated_hours: Float, total productive hours
- average_complexity_score: Integer 1-10
- average_seniority_score: Integer 1-10
- work_summary: Summary of the day's work
- key_achievements: List of 3-5 major accomplishments
- hour_estimation_reasoning: Explanation of hour estimate
- consistency_with_report: Boolean
- recommendations: List of 1-3 suggestions
"""

        messages = [
            {"role": "system", "content": "You are a senior engineering manager analyzing developer productivity."},
            {"role": "user", "content": prompt},
        ]

        response = await self._make_completion_request(
            messages, response_format={"type": "json_object"}, temperature=0.5
        )

        if not response:
            return {"total_estimated_hours": 0.0, "error": "Failed to analyze daily work"}

        try:
            result = json.loads(response)

            # Ensure all fields exist
            result.setdefault("total_estimated_hours", 0.0)
            result.setdefault("average_complexity_score", 5)
            result.setdefault("average_seniority_score", 5)
            result.setdefault("work_summary", "No summary available")
            result.setdefault("key_achievements", [])
            result.setdefault("hour_estimation_reasoning", "")
            result.setdefault("consistency_with_report", True)
            result.setdefault("recommendations", [])

            # Round hours
            result["total_estimated_hours"] = round(float(result["total_estimated_hours"]), 1)

            result["analyzed_at"] = datetime.now().isoformat()
            result["model_used"] = self.model

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return {"total_estimated_hours": 0.0, "error": "Invalid response format"}

    async def analyze_unified_daily_work(self, prompt: str) -> Dict[str, Any]:
        """
        v1 compatibility: analyze unified daily work using a custom prompt string.
        """
        messages: List[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": "You are an expert at analyzing developer work patterns and productivity. Provide detailed, structured analysis based on the data provided.",
            },
            {"role": "user", "content": prompt},
        ]
        raw = await self._make_completion_request(messages, response_format={"type": "json_object"}, temperature=0.7)
        if not raw:
            return {"error": "Empty AI response"}
        try:
            data = json.loads(raw)
            data["_metadata"] = {
                "generated_at": datetime.now().isoformat(),
                "model_used": self.model,
                "analysis_type": "unified_daily_work",
            }
            return data
        except json.JSONDecodeError:
            return {"error": "JSON parsing error", "raw_response": raw[:1000]}
