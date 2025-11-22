import asyncio
import json
import textwrap
from datetime import datetime
from typing import Any, Dict

from openai import AsyncOpenAI

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

        # Models that don't support temperature parameter (typically reasoning-focused models)
        self.reasoning_models = ["o3-mini-", "o4-mini-", "o3-", "gpt-5"]

        # Impact scoring calibration examples
        self.CALIBRATION_EXAMPLES = {
            "business_value": {
                "10": "Payment processing system, auth system, core business logic",
                "8": "Customer-facing feature with direct revenue impact",
                "6": "Internal tool that improves team productivity significantly",
                "4": "Nice-to-have feature, UI improvements",
                "2": "Code cleanup, non-critical refactoring",
                "1": "Typo fixes, comment updates",
            },
            "technical_complexity": {
                "10": "Distributed system coordination, complex algorithms (e.g., physics engine)",
                "8": "New service architecture, complex state management",
                "6": "Multi-service integration, moderate algorithmic work",
                "4": "Standard CRUD operations with some business logic",
                "2": "Simple API endpoint, basic UI component",
                "1": "Config changes, simple bug fixes",
            },
            "code_quality": {
                "1.5": "Comprehensive tests (>90% coverage), excellent documentation, follows all patterns",
                "1.2": "Good test coverage (70-90%), clear documentation",
                "1.0": "Adequate tests (50-70%), basic documentation",
                "0.8": "Minimal tests (<50%), sparse documentation",
                "0.5": "No tests, no documentation, technical debt introduced",
            },
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
        key_changes = result.get("key_changes", [])
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
        rationale_text = result.get("seniority_rationale", "")
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
        log_parts = [header, title, divider, complexity, hours, risk, seniority, divider, key_changes_header]

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

        # Extract values from nested structure
        bv_score = result.get("business_value", {}).get("score", "N/A")
        tc_score = result.get("technical_complexity", {}).get("score", "N/A")
        cq_score = result.get("code_quality_points", {}).get("score", "N/A")
        risk_score = result.get("risk_penalty", {}).get("score", "N/A")
        impact_score = result.get("impact_score", 0)

        # Get classification info
        classification = result.get("classification", {})
        category = classification.get("primary_category", "N/A")

        # Format the main sections
        title = f"║ IMPACT ANALYSIS: {commit_hash[:8]} - {repository}"
        title = f"{title}{' ' * (79 - len(title))}║"

        business_value = f"║ Business Value: {bv_score}/10"
        business_value = f"{business_value}{' ' * (79 - len(business_value))}║"

        technical_complexity = f"║ Technical Complexity: {tc_score}/10"
        technical_complexity = f"{technical_complexity}{' ' * (79 - len(technical_complexity))}║"

        code_quality = f"║ Code Quality Points: {cq_score}/5"
        code_quality = f"{code_quality}{' ' * (79 - len(code_quality))}║"

        risk_penalty = f"║ Risk Penalty: -{risk_score}"
        risk_penalty = f"{risk_penalty}{' ' * (79 - len(risk_penalty))}║"

        # Calculate impact score display with new formula
        impact_calc = f"({bv_score}×2) + ({tc_score}×1.5) + {cq_score} - {risk_score}"
        impact_line = f"║ Impact Score: {impact_score} points = {impact_calc}"
        impact_line = f"{impact_line}{' ' * (79 - len(impact_line))}║"

        # Format category
        category_line = f"║ Commit Type: {category}"
        category_line = f"{category_line}{' ' * (79 - len(category_line))}║"

        # Format reasoning sections
        divider = f"║{'-' * 78}║"

        # Business Value Reasoning
        bv_reasoning_header = "║ Business Value Reasoning:"
        bv_reasoning_header = f"{bv_reasoning_header}{' ' * (79 - len(bv_reasoning_header))}║"
        bv_reasoning_lines = []
        bv_data = result.get("business_value", {})
        bv_text = bv_data.get("evidence", "")
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
        tc_data = result.get("technical_complexity", {})
        tc_text = tc_data.get("evidence", "")
        if tc_text:
            wrapped_lines = textwrap.wrap(tc_text, width=72)
            for line in wrapped_lines:
                line_fmt = f"║   {line}"
                line_fmt = f"{line_fmt}{' ' * (79 - len(line_fmt))}║"
                tc_reasoning_lines.append(line_fmt)

        # Code Quality Checklist
        cq_reasoning_header = "║ Code Quality Checklist:"
        cq_reasoning_header = f"{cq_reasoning_header}{' ' * (79 - len(cq_reasoning_header))}║"
        cq_reasoning_lines = []
        cq_data = result.get("code_quality_points", {})
        checklist = cq_data.get("checklist", {})
        if checklist:
            checklist_items = [
                ("Tests included", checklist.get("tests_included", False)),
                ("High coverage", checklist.get("high_coverage", False)),
                ("Documentation updated", checklist.get("documentation_updated", False)),
                ("Follows patterns", checklist.get("follows_patterns", False)),
                ("Handles errors", checklist.get("handles_errors", False)),
            ]
            for item_name, item_value in checklist_items:
                check_mark = "✓" if item_value else "✗"
                item_line = f"║   {check_mark} {item_name}"
                item_line = f"{item_line}{' ' * (79 - len(item_line))}║"
                cq_reasoning_lines.append(item_line)

        # Risk Reasoning
        rf_reasoning_header = "║ Risk Assessment:"
        rf_reasoning_header = f"{rf_reasoning_header}{' ' * (79 - len(rf_reasoning_header))}║"
        rf_reasoning_lines = []
        rf_data = result.get("risk_penalty", {})
        rf_text = rf_data.get("reasoning", "")
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
            risk_penalty,
            divider,
            impact_line,
            category_line,
            divider,
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
            prompt = f"""You are a senior software engineer with expertise in code analysis. Analyze the following commit and provide both hours-based estimation and impact points scoring.

## Scoring Guidelines

### 1. HOURS-BASED TRADITIONAL SCORING

Estimate engineering effort considering:
- Actual development time (not AI-assisted time)
- Code review and refinement cycles
- Mental effort and architecture decisions

#### Reference Anchors - STRUCTURED SELECTION

**STEP 1: Initial Classification**
Based on total lines (additions + deletions):
- Under 50 lines → Start with Anchor A
- 50-199 lines → Start with Anchor B  
- 200-499 lines → Start with Anchor C
- 500-1499 lines → Start with Anchor D
- 1500+ lines → Consider Anchor D or E (see Step 2)

**STEP 2: Refinement Checks**
Apply these checks IN ORDER:

1. **Major Change Detection** (can upgrade D→E):
   □ Commit message says "new system", "new service", "new framework", or "breaking change"?
   □ Creates 5+ new files in a new top-level directory?
   □ Changes 20+ files across 3+ different top-level directories?
   □ Adds new technology/dependency to the project (new language, database, framework)?
   If 2+ checked → Upgrade to Anchor E

2. **File Count Override** (supersedes Step 1):
   □ Changes 25+ files regardless of content?
   If checked → Set to Anchor E

3. **Simplicity Reduction** (can downgrade by one level):
   □ >70% of changes are tests, docs, or comments?
   □ Commit message contains "refactor", "rename", "move", "cleanup"?
   □ Only changes configs, constants, or data files?
   If any checked → Downgrade one anchor level (but never below A)

**ANCHOR VALUES:**
- A: Minimal (0.5h) - Typos, configs, small fixes
- B: Simple (2.5h) - Single-purpose changes, basic features
- C: Standard (6.0h) - Multi-file features, moderate complexity
- D: Complex (12.0h) - Cross-component changes, significant logic
- E: Major (20.0h) - Architectural changes, new subsystems

#### Universal Multipliers:
• Involves concurrent/parallel code: +40%
• Modifies critical path (commit message indicates): +30%
• Includes comprehensive tests (>50% of changes): +20%
• Performance-critical changes: +20%
• Security-sensitive code: +30%
• Documentation only: -50%
• Formatting/refactoring only: -30%

#### Final Calculation:
1. Select anchor from table (no averaging needed)
2. Multiply by applicable multipliers
3. Round to nearest 0.5 hour

Example: 1200 lines in 8 files with parallel code
- Anchor D: 12.0 hours (from table)
- Multiplier: ×1.4 (parallel code)
- Final: 16.8 → 17.0 hours

### 2. COMPLEXITY SCORING (1-10)

Count these objective factors:
□ Changes core functionality (+3)
□ Modifies multiple components (+2)
□ Adds new abstractions/patterns (+2)
□ Requires algorithmic thinking (+2)
□ Handles error cases (+1)
Total: Min 1, Max 10

### 3. SENIORITY SCORING (1-10)

Score implementation quality:
□ Comprehensive error handling (+2)
□ Well-structured tests (+2)
□ Follows established patterns (+2)
□ Good abstractions (+2)
□ Forward-thinking design (+2)
Total: Min 1, Max 10

For trivial changes (<20 lines AND complexity ≤ 2 AND no tests):
Set seniority = 10 with rationale "Trivial change"

### 4. RISK LEVEL

Assess deployment risk:
• low: Unlikely to cause issues (tests, docs, isolated changes)
• medium: Some risk (core features, integrations)
• high: Significant risk (critical path, data changes, security)

## Scoring Process - COMPLETE ALL STEPS

HOURS ESTIMATION:
1. Total lines changed: ___ (additions + deletions from diff)
2. Total files changed: ___ (count from files list)
3. Initial anchor from Step 1: ___ (based on lines)
4. Major change detection:
   □ Message has "new system/service/framework/breaking"? ___
   □ Creates 5+ files in new directory? ___
   □ Changes 20+ files across 3+ directories? ___
   □ Adds new technology/dependency? ___
   COUNT: ___/4 (if 2+, upgrade D→E)
5. File count override: 25+ files? ___ (if yes, force E)
6. Simplicity checks:
   □ >70% tests/docs/comments? ___
   □ Message has "refactor/rename/move/cleanup"? ___
   □ Only configs/constants/data? ___
   ANY TRUE? ___ (if yes, downgrade one level)
7. Final anchor: ___
8. Base hours: ___
9. Multipliers: ___ Final hours: ___

VALUE & COMPLEXITY:
10. Primary beneficiary: END USERS or DEVELOPERS? ___
11. Value score (with cap if applicable): ___
12. Check for complexity caps:
    - Message contains tool/script/benchmark keywords? ___
    - >50% files in tool/script folders? ___
    - Apply cap? ___ Final complexity: ___

## Output Format

Provide a JSON response with this exact structure:
{{
  "total_lines": <int>,
  "total_files": <int>,
  "initial_anchor": "<A/B/C/D/E>",
  "major_change_checks": ["<specific checks that were true>"],
  "major_change_count": <int>,
  "file_count_override": <boolean>,
  "simplicity_reduction_checks": ["<specific checks that were true>"],
  "final_anchor": "<A/B/C/D/E>",
  "base_hours": <float>,
  "multipliers_applied": ["<multiplier1>", "<multiplier2>"],
  "complexity_score": <int 1-10>,
  "complexity_cap_applied": "<none|tooling|test|doc>",
  "estimated_hours": <float>,
  "risk_level": "<low|medium|high>",
  "seniority_score": <int 1-10>,
  "seniority_rationale": "<explanation>",
  "key_changes": ["<change1>", "<change2>", ...]
}}

## Commit to Analyze

Repository: {commit_data.get('repository', '')}
Author: {commit_data.get('author_name', '')} <{commit_data.get('author_email', '')}>
Message: {commit_data.get('message', '')}
Files Changed: {', '.join(commit_data.get('files_changed', []))}
Additions: {commit_data.get('additions', 0)}
Deletions: {commit_data.get('deletions', 0)}

Diff:
{commit_data.get('diff', '')}"""

            # Set up parameters for the API call
            if self._is_reasoning_model(self.commit_analysis_model):
                # Use responses API for reasoning models with medium effort
                api_params = {
                    "model": self.commit_analysis_model,
                    "reasoning": {"effort": settings.openai_reasoning_effort},
                    "input": [
                        {
                            "role": "user",
                            "content": f"""You are a senior software engineer with deep expertise in effort estimation and code quality assessment. Your task is to analyze commits with extreme consistency by following the provided guidelines exactly. Always compare scores against the examples provided. Be conservative in scoring - when in doubt, score lower. Output only valid JSON with no additional commentary.

{prompt}""",
                        }
                    ],
                }
                # Run both analyses in parallel for efficiency
                hours_task = self.client.responses.create(**api_params)
                impact_task = self.analyze_commit_impact(commit_data)

                # Wait for both to complete
                hours_response, impact_result = await asyncio.gather(hours_task, impact_task)

                # Parse the hours response from responses API
                try:
                    # Extract the text content
                    text_content = None
                    if hasattr(hours_response, "output_text") and hours_response.output_text:
                        text_content = hours_response.output_text
                    elif hasattr(hours_response, "output") and hasattr(hours_response.output, "text"):
                        text_content = hours_response.output.text
                    elif hasattr(hours_response, "choices") and hours_response.choices:
                        # Sometimes responses API returns choices format
                        text_content = hours_response.choices[0].message.content
                    else:
                        # Log the response structure for debugging
                        print(f"Unexpected hours response structure: {hours_response}")
                        print(f"Response type: {type(hours_response)}")
                        print(f"Response attributes: {dir(hours_response)}")
                        raise ValueError("Unable to extract text from responses API response")

                    # Clean up markdown code blocks if present
                    if text_content.strip().startswith("```json"):
                        text_content = text_content.strip()[7:]  # Remove ```json
                        if text_content.endswith("```"):
                            text_content = text_content[:-3]  # Remove closing ```
                    elif text_content.strip().startswith("```"):
                        text_content = text_content.strip()[3:]  # Remove ```
                        if text_content.endswith("```"):
                            text_content = text_content[:-3]  # Remove closing ```

                    hours_result = json.loads(text_content.strip())
                except (json.JSONDecodeError, AttributeError) as e:
                    print(f"Error parsing hours response: {e}")
                    print(f"Response content: {getattr(hours_response, 'output_text', 'No output_text attribute')}")
                    raise
            else:
                # Use chat completions API for non-reasoning models
                api_params = {
                    "model": self.commit_analysis_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": """You are a senior software engineer with deep expertise in effort estimation and code quality assessment. Your task is to analyze commits with extreme consistency by following the provided guidelines exactly. Always compare scores against the examples provided. Be conservative in scoring - when in doubt, score lower. Output only valid JSON with no additional commentary.""",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.15,  # Lower temperature for higher determinism
                }
                # Run both analyses in parallel for efficiency
                hours_task = self.client.chat.completions.create(**api_params)
                impact_task = self.analyze_commit_impact(commit_data)

                # Wait for both to complete
                hours_response, impact_result = await asyncio.gather(hours_task, impact_task)

                # Parse the hours response from chat completions API
                hours_result = json.loads(hours_response.choices[0].message.content)

            # Combine both results
            combined_result = {
                # Traditional hours-based analysis with structured anchors
                "total_lines": hours_result.get("total_lines"),
                "total_files": hours_result.get("total_files"),
                "initial_anchor": hours_result.get("initial_anchor"),
                "major_change_checks": hours_result.get("major_change_checks", []),
                "complexity_boost_checks": hours_result.get("complexity_boost_checks", []),
                "simplicity_reduction_checks": hours_result.get("simplicity_reduction_checks", []),
                "final_anchor": hours_result.get("final_anchor"),
                "base_hours": hours_result.get("base_hours"),
                "multipliers_applied": hours_result.get("multipliers_applied"),
                "complexity_score": hours_result.get("complexity_score"),
                "estimated_hours": hours_result.get("estimated_hours"),
                "risk_level": hours_result.get("risk_level"),
                "seniority_score": hours_result.get("seniority_score"),
                "seniority_rationale": hours_result.get("seniority_rationale"),
                "key_changes": hours_result.get("key_changes"),
                # Impact scoring analysis (v2.0 with nested structure)
                "impact_business_value": impact_result.get("business_value", {}).get("score"),
                "impact_business_value_reasoning": impact_result.get("business_value", {}).get("evidence"),
                "impact_business_value_decision_path": impact_result.get("business_value", {}).get("decision_path"),
                "impact_technical_complexity": impact_result.get("technical_complexity", {}).get("score"),
                "impact_technical_complexity_reasoning": impact_result.get("technical_complexity", {}).get("evidence"),
                "impact_code_quality_points": impact_result.get("code_quality_points", {}).get("score"),
                "impact_code_quality_checklist": impact_result.get("code_quality_points", {}).get("checklist"),
                "impact_risk_penalty": impact_result.get("risk_penalty", {}).get("score"),
                "impact_risk_reasoning": impact_result.get("risk_penalty", {}).get("reasoning"),
                "impact_score": impact_result.get("impact_score"),
                "impact_classification": impact_result.get("classification", {}),
                "impact_calculation_breakdown": impact_result.get("calculation_breakdown"),
                # Metadata
                "analyzed_at": datetime.now().isoformat(),
                "commit_hash": commit_data.get("commit_hash"),
                "repository": commit_data.get("repository"),
                "model_used": self.commit_analysis_model,
                "scoring_methods": ["hours_estimation", "impact_points"],
            }

            # Log formatted analysis results (traditional format)
            commit_hash = commit_data.get("commit_hash", "unknown")
            repository = commit_data.get("repository", "unknown")
            formatted_log = self._format_analysis_log(hours_result, commit_hash, repository)
            print(formatted_log)  # Using print for cleaner formatting in console

            # Also log impact scoring with detailed format
            if combined_result.get("impact_score"):
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
            business_value_examples = "\n".join(
                [f"Score {k}: {v}" for k, v in self.CALIBRATION_EXAMPLES["business_value"].items()]
            )
            technical_complexity_examples = "\n".join(
                [f"Score {k}: {v}" for k, v in self.CALIBRATION_EXAMPLES["technical_complexity"].items()]
            )
            code_quality_examples = "\n".join(
                [f"Multiplier {k}: {v}" for k, v in self.CALIBRATION_EXAMPLES["code_quality"].items()]
            )

            prompt = f"""You are a senior engineering manager evaluating developer contributions using the NEW Impact Points System (v2.0) with ADDITIVE scoring for better consistency.

## CRITICAL CHANGES IN V2.0
1. Impact Score is now ADDITIVE, not multiplicative
2. Code Quality is now a points checklist (0-5), not a multiplier
3. Use decision trees for scoring - no guessing
4. Two-pass scoring with self-justification required

## PASS 1: Initial Analysis

### STEP 1: Commit Classification

Primary type:
- capability: New functionality
- fix: Repairing broken functionality
- improvement: Enhancing existing functionality
- foundation: Tests, refactoring, infrastructure
- maintenance: Docs, configs, cleanup

Heuristic subtypes (to guide conservative scoring):
- deletions-heavy cleanup: predominately deletions, minimal additions, few or no new files, no new capabilities

Check ALL that apply:
□ Test code >80% of changes
□ Modifies critical path (per commit message)
□ Changes security-related code
□ Alters data structures/storage
□ Updates interfaces/contracts
□ Emergency/hotfix

### STEP 2: Value Assessment (1-10)

Universal Decision Tree:
```
START: Who benefits from this change?
├─ END USERS (those who use the software's primary purpose)
│   ├─ Critical to core functionality?
│   │   ├─ YES → Score 8-10
│   │   └─ NO → Score 5-7
│   └─ Nice to have?
│       └─ Score 3-4
└─ DEVELOPERS/MAINTAINERS ONLY
    ├─ Pure cleanup (deletions-heavy, no new capability) → Score 1-2
    ├─ Refactor that improves structure/maintainability (no new capability) → Score 2-4
    └─ Clear improvements to development velocity/operational efficiency → Score 4-5
```

HARD CAPS:
- Test-only commits (>80% test code): MAX 4
- Documentation-only commits: MAX 3
- Refactoring with no new functionality: MAX 4

Deletions-heavy maintenance caps (apply when the work is predominately deletions with little/no new code):
- Business Value: MAX 2
- Technical Complexity: MAX 2
- Overall Impact: MAX 8

NOTE: Developer productivity tools, CI/CD improvements, monitoring, and infrastructure 
changes provide measurable business value through reduced costs, faster delivery, 
and improved system reliability. Do not penalize changes for being "internal-only."

### STEP 3: Technical Complexity (1-10)

Base Complexity Scale:
1: Trivial (configs, constants, single-line changes)
2: Simple (basic logic, single function/method)
3: Standard (common patterns, single module)
4: Moderate (multiple modules, standard integration)
5: Substantial (complex logic, multiple integrations)
6: Challenging (concurrent/async, performance-critical)
7: Complex (distributed systems, complex algorithms)
8: Very Complex (novel approaches, system architecture)
9: Extremely Complex (breakthrough algorithms)
10: Exceptional (paradigm-shifting implementation)

AUTOMATIC CAPS (check in order):
1. If commit message contains "test", "benchmark", "script", "tool", "CI", "CD": CAP AT 5
2. If >50% of changed files are in folders named "test", "tests", "scripts", "tools", "benchmarks", "ci", ".github": CAP AT 5
3. If primarily test code (>70% of changes): CAP AT 3
4. If only documentation changes: CAP AT 2
5. Apply the LOWER of: base score OR cap

### STEP 4: Quality Indicators (0-5 points)

Universal Quality Checklist:
□ Includes tests (+1)
□ Handles edge cases (+1)
□ Well-documented (+1)
□ Follows patterns (+1)
□ Future-proof design (+1)

### STEP 5: Risk Assessment (0-3 points)

Universal Risk Factors:
- 0: Standard, well-tested
- 1: Some untested paths
- 2: Limited testing, rushed
- 3: Emergency fix, high blast radius

## PASS 2: Scoring Verification

MANDATORY CHECKS:
1. If primary beneficiary = DEVELOPERS ONLY → Business Value CANNOT exceed 5
2. If commit message/files indicate tooling → Technical Complexity CANNOT exceed 5
3. If >80% test code → Both Value and Complexity capped appropriately
4. Verify all caps were applied correctly

For deletions-heavy maintenance (predominately deletions and minimal/no new code), apply the specific caps above before computing final Impact.

For EACH score, confirm:
- Does it respect all applicable caps?
- Is there specific evidence from the diff?

## Final Formula

Impact = (Value × 2) + (Complexity × 1.5) + Quality - Risk

Range: 0.5 to 40 points

## Commit Details

Repository: {commit_data.get('repository', '')}
Author: {commit_data.get('author_name', '')} <{commit_data.get('author_email', '')}>
Message: {commit_data.get('message', '')}
Files Changed: {', '.join(commit_data.get('files_changed', []))}
Additions: {commit_data.get('additions', 0)} lines
Deletions: {commit_data.get('deletions', 0)} lines

Diff:
{commit_data.get('diff', '')}

## Required JSON Output

{{
  "classification": {{
    "primary_category": "<category>",
    "is_test_heavy": <boolean>,
    "special_flags": ["<flag1>", "<flag2>"]
  }},
  "business_value": {{
    "score": <int 1-10>,
    "decision_path": "<path taken in decision tree>",
    "why_not_lower": "<specific reason>",
    "why_not_higher": "<specific reason>",
    "evidence": "<specific evidence from diff>"
  }},
  "technical_complexity": {{
    "score": <int 1-10>,
    "why_not_lower": "<specific reason>",
    "why_not_higher": "<specific reason>",
    "evidence": "<specific evidence from diff>"
  }},
  "code_quality_points": {{
    "score": <int 0-5>,
    "checklist": {{
      "tests_included": <boolean>,
      "high_coverage": <boolean>,
      "documentation_updated": <boolean>,
      "follows_patterns": <boolean>,
      "handles_errors": <boolean>
    }},
    "evidence": "<specific evidence for each true item>"
  }},
  "risk_penalty": {{
    "score": <int 0-3>,
    "reasoning": "<specific risks identified>"
  }},
  "impact_score": <calculated float>,
  "calculation_breakdown": "<show the calculation>"
}}"""

            # Set up parameters for the API call
            if self._is_reasoning_model(self.commit_analysis_model):
                # Use responses API for reasoning models with medium effort
                api_params = {
                    "model": self.commit_analysis_model,
                    "reasoning": {"effort": settings.openai_reasoning_effort},
                    "input": [
                        {
                            "role": "user",
                            "content": f"""You are a senior engineering manager with extensive experience evaluating developer contributions. Your task is to apply the Impact Points System with extreme consistency. Always compare scores to canonical examples. Be conservative - when uncertain, score lower. Focus on concrete evidence from the diff. Output only valid JSON with no additional commentary.

{prompt}""",
                        }
                    ],
                }
                # Make API call
                response = await self.client.responses.create(**api_params)

                # Parse the response from responses API
                try:
                    # Extract the text content
                    text_content = None
                    if hasattr(response, "output_text") and response.output_text:
                        text_content = response.output_text
                    elif hasattr(response, "output") and hasattr(response.output, "text"):
                        text_content = response.output.text
                    elif hasattr(response, "choices") and response.choices:
                        # Sometimes responses API returns choices format
                        text_content = response.choices[0].message.content
                    else:
                        # Log the response structure for debugging
                        print(f"Unexpected response structure: {response}")
                        print(f"Response type: {type(response)}")
                        print(f"Response attributes: {dir(response)}")
                        raise ValueError("Unable to extract text from responses API response")

                    # Clean up markdown code blocks if present
                    if text_content.strip().startswith("```json"):
                        text_content = text_content.strip()[7:]  # Remove ```json
                        if text_content.endswith("```"):
                            text_content = text_content[:-3]  # Remove closing ```
                    elif text_content.strip().startswith("```"):
                        text_content = text_content.strip()[3:]  # Remove ```
                        if text_content.endswith("```"):
                            text_content = text_content[:-3]  # Remove closing ```

                    result = json.loads(text_content.strip())
                except (json.JSONDecodeError, AttributeError) as e:
                    print(f"Error parsing impact response: {e}")
                    print(f"Response content: {getattr(response, 'output_text', 'No output_text attribute')}")
                    raise
            else:
                # Use chat completions API for non-reasoning models
                api_params = {
                    "model": self.commit_analysis_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": """You are a senior engineering manager with extensive experience evaluating developer contributions. Your task is to apply the Impact Points System with extreme consistency. Always compare scores to canonical examples. Be conservative - when uncertain, score lower. Focus on concrete evidence from the diff. Output only valid JSON with no additional commentary.""",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.15,  # Low temperature for consistency
                }
                # Make API call
                response = await self.client.chat.completions.create(**api_params)

                # Parse the response from chat completions API
                result = json.loads(response.choices[0].message.content)

            # Extract scores from nested structure
            business_value = result.get("business_value", {}).get("score", 5)
            technical_complexity = result.get("technical_complexity", {}).get("score", 5)
            code_quality_points = result.get("code_quality_points", {}).get("score", 2)
            risk_penalty = result.get("risk_penalty", {}).get("score", 0)

            # Calculate impact score using new additive formula
            if "impact_score" not in result or result["impact_score"] is None:
                result["impact_score"] = (
                    (business_value * 2) + (technical_complexity * 1.5) + code_quality_points - risk_penalty
                )

            # Round impact score to 1 decimal place
            result["impact_score"] = round(result["impact_score"], 1)

            # Add metadata
            result.update(
                {
                    "analyzed_at": datetime.now().isoformat(),
                    "commit_hash": commit_data.get("commit_hash"),
                    "repository": commit_data.get("repository"),
                    "model_used": self.commit_analysis_model,
                    "scoring_method": "impact_points",
                }
            )

            return result

        except json.JSONDecodeError as e:
            print(f"JSON parsing error in analyze_commit_impact: {e}")
            return {
                "error": True,
                "message": f"Failed to parse API response: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return self.error_handling(e)

    async def analyze_commit_traditional_only(self, commit_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a commit using ONLY the traditional hours-based method.
        This is for benchmarking to isolate scoring methods.
        """
        try:
            # Prepare the traditional hours prompt
            prompt = f"""You are a senior software engineer with expertise in code analysis. Analyze the following commit and provide ONLY hours-based estimation.

## Scoring Guidelines

### 1. HOURS-BASED TRADITIONAL SCORING

Estimate engineering effort considering:
- Actual development time (not AI-assisted time)
- Code review and refinement cycles
- Mental effort and architecture decisions

#### Reference Anchors - STRUCTURED SELECTION

**STEP 1: Initial Classification**
Based on total lines (additions + deletions):
- Under 50 lines → Start with Anchor A
- 50-199 lines → Start with Anchor B  
- 200-499 lines → Start with Anchor C
- 500-1499 lines → Start with Anchor D
- 1500+ lines → Consider Anchor D or E (see Step 2)

**STEP 2: Refinement Checks**
Apply these checks IN ORDER:

1. **Major Change Detection** (can upgrade D→E):
   □ Commit message says "new system", "new service", "new framework", or "breaking change"?
   □ Creates 5+ new files in a new top-level directory?
   □ Changes 20+ files across 3+ different top-level directories?
   □ Adds new technology/dependency to the project (new language, database, framework)?
   If 2+ checked → Upgrade to Anchor E

2. **File Count Override** (supersedes Step 1):
   □ Changes 25+ files regardless of content?
   If checked → Set to Anchor E

3. **Simplicity Reduction** (can downgrade by one level):
   □ >70% of changes are tests, docs, or comments?
   □ Commit message contains "refactor", "rename", "move", "cleanup"?
   □ Only changes configs, constants, or data files?
   If any checked → Downgrade one anchor level (but never below A)

**ANCHOR VALUES:**
- A: Minimal (0.5h) - Typos, configs, small fixes
- B: Simple (2.5h) - Single-purpose changes, basic features
- C: Standard (6.0h) - Multi-file features, moderate complexity
- D: Complex (12.0h) - Cross-component changes, significant logic
- E: Major (20.0h) - Architectural changes, new subsystems

#### Universal Multipliers:
• Involves concurrent/parallel code: +40%
• Modifies critical path (commit message indicates): +30%
• Includes comprehensive tests (>50% of changes): +20%
• Performance-critical changes: +20%
• Security-sensitive code: +30%
• Documentation only: -50%
• Formatting/refactoring only: -30%

#### Final Calculation:
1. Select anchor from table (no averaging needed)
2. Multiply by applicable multipliers
3. Round to nearest 0.5 hour

Example: 1200 lines in 8 files with parallel code
- Anchor D: 12.0 hours (from table)
- Multiplier: ×1.4 (parallel code)
- Final: 16.8 → 17.0 hours

### 2. COMPLEXITY SCORING (1-10)

Count these objective factors:
□ Changes core functionality (+3)
□ Modifies multiple components (+2)
□ Adds new abstractions/patterns (+2)
□ Requires algorithmic thinking (+2)
□ Handles error cases (+1)
Total: Min 1, Max 10

### 3. SENIORITY SCORING (1-10)

Score implementation quality:
□ Comprehensive error handling (+2)
□ Well-structured tests (+2)
□ Follows established patterns (+2)
□ Good abstractions (+2)
□ Forward-thinking design (+2)
Total: Min 1, Max 10

For trivial changes (<20 lines AND complexity ≤ 2 AND no tests):
Set seniority = 10 with rationale "Trivial change"

### 4. RISK LEVEL

Assess deployment risk:
• low: Unlikely to cause issues (tests, docs, isolated changes)
• medium: Some risk (core features, integrations)
• high: Significant risk (critical path, data changes, security)

## Output Format

Provide a JSON response with this exact structure:
{{
  "total_lines": <int>,
  "total_files": <int>,
  "initial_anchor": "<A/B/C/D/E>",
  "major_change_checks": ["<specific checks that were true>"],
  "major_change_count": <int>,
  "file_count_override": <boolean>,
  "simplicity_reduction_checks": ["<specific checks that were true>"],
  "final_anchor": "<A/B/C/D/E>",
  "base_hours": <float>,
  "multipliers_applied": ["<multiplier1>", "<multiplier2>"],
  "complexity_score": <int 1-10>,
  "complexity_cap_applied": "<none|tooling|test|doc>",
  "estimated_hours": <float>,
  "risk_level": "<low|medium|high>",
  "seniority_score": <int 1-10>,
  "seniority_rationale": "<explanation>",
  "key_changes": ["<change1>", "<change2>", ...]
}}

## Commit to Analyze

Repository: {commit_data.get('repository', '')}
Author: {commit_data.get('author_name', '')} <{commit_data.get('author_email', '')}>
Message: {commit_data.get('message', '')}
Files Changed: {', '.join(commit_data.get('files_changed', []))}
Additions: {commit_data.get('additions', 0)}
Deletions: {commit_data.get('deletions', 0)}

Diff:
{commit_data.get('diff', '')}"""

            # Set up parameters for the API call
            if self._is_reasoning_model(self.commit_analysis_model):
                # Use responses API for reasoning models with high effort
                api_params = {
                    "model": self.commit_analysis_model,
                    "reasoning": {"effort": "high"},
                    "input": [
                        {
                            "role": "user",
                            "content": f"""You are a senior software engineer with deep expertise in effort estimation and code quality assessment. Your task is to analyze commits with extreme consistency by following the provided guidelines exactly. Always compare scores against the examples provided. Be conservative in scoring - when in doubt, score lower. Output only valid JSON with no additional commentary.

{prompt}""",
                        }
                    ],
                }
                response = await self.client.responses.create(**api_params)

                # Parse the response from responses API
                try:
                    # Extract the text content
                    text_content = None
                    if hasattr(response, "output_text") and response.output_text:
                        text_content = response.output_text
                    elif hasattr(response, "output") and hasattr(response.output, "text"):
                        text_content = response.output.text
                    elif hasattr(response, "choices") and response.choices:
                        text_content = response.choices[0].message.content
                    else:
                        raise ValueError("Unable to extract text from responses API response")

                    # Clean up markdown code blocks if present
                    if text_content.strip().startswith("```json"):
                        text_content = text_content.strip()[7:]
                        if text_content.endswith("```"):
                            text_content = text_content[:-3]
                    elif text_content.strip().startswith("```"):
                        text_content = text_content.strip()[3:]
                        if text_content.endswith("```"):
                            text_content = text_content[:-3]

                    result = json.loads(text_content.strip())
                except (json.JSONDecodeError, AttributeError) as e:
                    print(f"Error parsing traditional response: {e}")
                    raise
            else:
                # Use chat completions API for non-reasoning models
                api_params = {
                    "model": self.commit_analysis_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": """You are a senior software engineer with deep expertise in effort estimation and code quality assessment. Your task is to analyze commits with extreme consistency by following the provided guidelines exactly. Always compare scores against the examples provided. Be conservative in scoring - when in doubt, score lower. Output only valid JSON with no additional commentary.""",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.15,
                }
                response = await self.client.chat.completions.create(**api_params)
                result = json.loads(response.choices[0].message.content)

            # Add metadata
            result.update(
                {
                    "analyzed_at": datetime.now().isoformat(),
                    "commit_hash": commit_data.get("commit_hash"),
                    "repository": commit_data.get("repository"),
                    "model_used": self.commit_analysis_model,
                    "scoring_method": "traditional_hours_only",
                }
            )

            return result

        except Exception as e:
            return self.error_handling(e)

    async def benchmark_separate_analyses(self, commit_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run traditional hours and impact scoring completely separately for benchmarking.
        This ensures no cross-contamination between scoring methods.
        """
        try:
            # Run both analyses completely independently
            traditional_task = self.analyze_commit_traditional_only(commit_data)
            impact_task = self.analyze_commit_impact(commit_data)

            # Wait for both to complete
            traditional_result, impact_result = await asyncio.gather(traditional_task, impact_task)

            # Combine results
            combined_result = {
                "traditional_hours": traditional_result,
                "impact_points": impact_result,
                "analyzed_at": datetime.now().isoformat(),
                "commit_hash": commit_data.get("commit_hash"),
                "repository": commit_data.get("repository"),
                "model_used": self.commit_analysis_model,
                "scoring_methods": ["traditional_hours", "impact_points"],
                "benchmark_mode": "separate_analyses",
            }

            return combined_result

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

        return {"error": True, "message": error_message, "timestamp": datetime.now().isoformat()}
