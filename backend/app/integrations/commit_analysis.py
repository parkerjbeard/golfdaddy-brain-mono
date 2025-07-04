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
            prompt = f"""You are a senior software engineer with expertise in code analysis. Analyze the following commit and provide both hours-based estimation and impact points scoring.

## Scoring Guidelines

### 1. HOURS-BASED TRADITIONAL SCORING

Estimate engineering effort considering:
- Actual development time (not AI-assisted time)
- Code review and refinement cycles
- Mental effort and architecture decisions

#### Base Hours Calibration by Code Volume:
• 1-20 lines changed: 0.25-1 hours
• 21-100 lines: 1-2 hours  
• 101-300 lines: 2-4 hours
• 301-800 lines: 4-8 hours
• 800+ lines: 8-20 hours

#### Work Type Modifiers:
• Bug fixes: +25% for investigation time
• New features: +20% for design decisions
• Test additions: +20% for test design
• Infrastructure/CI: +30% for testing and validation
• Database changes: +40% for migration planning
• Security fixes: +50% for careful implementation
• Documentation only: -30%
• Mechanical refactoring: -30%
• Code formatting: -50%

#### File Type Importance:
• Payment/financial code: 1.5x multiplier
• Security/auth code: 1.4x multiplier
• Core business logic: 1.3x multiplier
• API contracts/schemas: 1.2x multiplier
• Comprehensive tests: 1.2x multiplier
• Regular features: 1.0x multiplier
• Config/documentation: 0.8x multiplier
• Generated/formatted code: 0.5x multiplier

### 2. COMPLEXITY SCORING (1-10)

Rate based on:
• 1-2: Trivial (formatting, typos, simple config)
• 3-4: Simple (basic CRUD, straightforward logic)
• 5-6: Moderate (multiple components, some design decisions)
• 7-8: Complex (architectural changes, complex algorithms)
• 9-10: Very complex (distributed systems, critical infrastructure)

### 3. SENIORITY SCORING (1-10)

Evaluate implementation quality against ideal senior-level work:

#### Positive Indicators (increase score):
• Comprehensive error handling and edge cases
• Well-structured tests with good coverage
• Performance optimizations with benchmarks
• Security best practices followed
• Clean abstractions and API design
• Follows and improves existing patterns
• Considers future maintainability

#### Negative Indicators (decrease score):
• Missing error handling
• No tests for complex logic
• Hard-coded values
• Security vulnerabilities
• Performance anti-patterns
• Breaks established patterns
• Short-term thinking

#### IMPORTANT - Trivial Change Detection:
A commit is trivial ONLY when ALL conditions are met:
- Total lines changed ≤ 20
- Complexity score ≤ 2
- No test files added or modified
- No architectural files (migrations, schemas, configs)
- Changes are purely cosmetic (formatting, typos, comments)

For truly trivial commits only:
- Set seniority_score = 10
- Use rationale: "Trivial change – seniority not meaningfully assessable"

For ALL other commits (including test additions):
- Score seniority normally (1-10 range)
- Test-only commits typically score 4-8 based on test quality

### 4. RISK LEVEL

Assess deployment risk:
• low: Unlikely to cause issues (tests, docs, isolated features)
• medium: Some risk (core features, integrations)
• high: Significant risk (payments, auth, data migrations)

## Output Format

Provide a JSON response with this exact structure:
{{
  "complexity_score": <int 1-10>,
  "estimated_hours": <float>,
  "risk_level": "<low|medium|high>",
  "seniority_score": <int 1-10>,
  "seniority_rationale": "<explanation>",
  "key_changes": ["<change1>", "<change2>", ...]
}}

## Consistency Checks

Before finalizing scores, verify:
1. Hours align with complexity (high complexity = more hours)
2. Test commits don't have inflated technical complexity
3. Seniority score reflects actual code quality indicators
4. Business value matches actual user/business impact
5. No commit >20 lines is marked as trivial

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

{prompt}"""
                        }
                    ]
                }
                # Run both analyses in parallel for efficiency
                hours_task = self.client.responses.create(**api_params)
                impact_task = self.analyze_commit_impact(commit_data)
                
                # Wait for both to complete
                hours_response, impact_result = await asyncio.gather(hours_task, impact_task)
                
                # Parse the hours response from responses API
                hours_result = json.loads(hours_response.output_text)
            else:
                # Use chat completions API for non-reasoning models
                api_params = {
                    "model": self.commit_analysis_model,
                    "messages": [
                        {"role": "system", "content": """You are a senior software engineer with deep expertise in effort estimation and code quality assessment. Your task is to analyze commits with extreme consistency by following the provided guidelines exactly. Always compare scores against the examples provided. Be conservative in scoring - when in doubt, score lower. Output only valid JSON with no additional commentary."""},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.15  # Lower temperature for higher determinism
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
                "impact_classification": impact_result.get("classification", {}),
                "impact_validation_notes": impact_result.get("validation_notes"),
                
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
            
            prompt = f"""You are a senior engineering manager with deep experience in evaluating developer contributions. Analyze this commit using the Impact Points System with extreme consistency.

## CRITICAL INSTRUCTIONS
1. You MUST compare every score to the provided examples
2. You MUST provide specific evidence from the diff for each score
3. You MUST follow the scoring rules exactly - no exceptions
4. For ambiguous cases, always score conservatively (lower)

## STEP 1: Initial Classification

First, classify this commit into ONE primary category:
- feature: New functionality added
- bugfix: Fixing broken functionality  
- refactor: Code improvement without behavior change
- test: Test additions or improvements
- infrastructure: Build, CI/CD, deployment changes
- documentation: Docs, comments, README updates
- security: Security fixes or improvements
- performance: Performance optimizations

Then identify ANY of these special flags:
□ Affects payment/financial systems
□ Modifies authentication/authorization
□ Changes data models/migrations
□ Updates external APIs/contracts
□ Adds/modifies significant tests (>50 lines)
□ Emergency/hotfix deployment

## STEP 2: Business Value Score (1-10)

### Canonical Examples by Category:

**Features:**
10: Payment processing, core revenue features
9: Major user-facing features, key differentiators
8: Important features used by many users
7: Moderate features improving user experience
6: Internal tools significantly boosting team productivity
5: Minor features with limited user impact
4: Small convenience features
3: Internal improvements with indirect benefits
2: Cosmetic improvements
1: Negligible impact

**Bugfixes:**
10: Critical data loss/security bugs
9: Major functionality broken for many users
8: Important features broken
7: Moderate bugs affecting user experience
6: Minor bugs with workarounds available
5: Edge case bugs
4: Internal tool bugs
3: Cosmetic bugs
2: Typos in non-user-facing text
1: Code comment typos

**Tests (special scoring):**
- Tests for payment/financial code: 5-6
- Tests for core business logic: 4-5
- Tests for standard features: 3-4
- Tests for internal tools: 2-3
- Test refactoring: 2

**Infrastructure:**
8-10: Critical deployment/security infrastructure
6-7: CI/CD improvements saving significant time
4-5: Build optimizations
2-3: Minor configuration updates

### Scoring Rules:
- If commit spans multiple categories, use the highest applicable score
- Test commits are capped at 6 unless fixing critical test gaps
- Documentation is capped at 4 unless fixing dangerous misinformation
- Consider cumulative impact over time, not just immediate effect

Your Business Value Score: ___

## STEP 3: Technical Complexity Score (1-10)

### Canonical Examples:

10: Distributed consensus, complex ML algorithms, compiler design
9: Multi-service orchestration, complex state machines
8: Database query optimization, caching strategies
7: API design with versioning, complex business rules
6: Integration with external services, moderate algorithms
5: Standard CRUD with validation logic
4: Simple feature implementation
3: Basic logic changes, simple utilities
2: Configuration updates, simple scripts
1: Text changes, formatting

### Special Modifiers:
+2 points if involves: concurrent programming, distributed systems
+1 point if involves: performance optimization, security implementation
+1 point if requires deep domain knowledge

### Test Complexity Rules:
- Test code is typically capped at 3
- Exception: Complex test infrastructure/frameworks can score up to 5
- Mocking distributed systems or complex state: 3
- Standard unit tests: 2
- Simple assertions: 1

Your Technical Complexity Score: ___

## STEP 4: Code Quality Multiplier (0.5-1.5)

Evaluate based on concrete evidence in the diff:

### 1.5 - Exceptional Quality
ALL of the following must be true:
- Comprehensive tests with >90% coverage of new code
- Extensive documentation/comments explaining why, not what
- Follows or establishes design patterns improving codebase
- Handles all edge cases and errors gracefully
- Performance considerations documented

### 1.3 - High Quality  
At least 3 of the following:
- Good test coverage (70-90%) with edge cases
- Clear documentation/comments
- Follows established patterns consistently
- Proper error handling
- Clean, readable code structure

### 1.0 - Standard Quality (default)
- Basic tests for happy path
- Minimal necessary documentation
- No obvious anti-patterns
- Standard error handling

### 0.8 - Below Standard
Any of these issues:
- Missing tests for complex logic
- Poor naming or structure
- Violates established patterns
- Minimal error handling

### 0.5 - Poor Quality
Multiple issues:
- No tests for critical logic
- Unclear/misleading code
- Introduces technical debt
- No error handling

Your Code Quality Multiplier: ___

## STEP 5: Risk Factor (0.8-2.0)

### Risk Assessment:

**0.8 - Over-engineered**
- Solution is unnecessarily complex
- Adds abstraction without clear benefit
- Could be solved more simply

**1.0 - Appropriate (default)**
- Solution matches problem complexity
- Standard approach for the situation
- Well-planned implementation

**1.2 - Elevated Risk**
- Touches payment/financial systems
- Modifies authentication/security
- Changes critical data models
- But: well-tested and reviewed

**1.5 - High Risk**
- Emergency fix under pressure
- Limited testing due to urgency
- Modifies critical systems without full review
- Temporary solution needed

**2.0 - Critical Risk**
- Production hotfix for data loss/security
- Deployed with minimal testing
- Business-critical emergency

Your Risk Factor: ___

## STEP 6: Final Calculation

Impact Score = (Business Value × Technical Complexity × Code Quality) / Risk Factor

## VALIDATION CHECKLIST

Before submitting, verify:
□ Test commits don't have technical complexity >3 (unless test infrastructure)
□ Business value aligns with actual user/business impact
□ Code quality has specific evidence from the diff
□ Risk factor reflects deployment urgency/safety
□ All scores compared against canonical examples

## Commit Details

Repository: {commit_data.get('repository', '')}
Author: {commit_data.get('author_name', '')} <{commit_data.get('author_email', '')}>
Message: {commit_data.get('message', '')}
Files Changed: {', '.join(commit_data.get('files_changed', []))}
Additions: {commit_data.get('additions', 0)} lines
Deletions: {commit_data.get('deletions', 0)} lines

Diff:
{commit_data.get('diff', '')}

## Required Output Format

You MUST output valid JSON only:
{{
  "classification": {{
    "primary_category": "<category>",
    "special_flags": ["<flag1>", "<flag2>"]
  }},
  "business_value": <int 1-10>,
  "business_value_reasoning": "<specific comparison to examples>",
  "technical_complexity": <int 1-10>,
  "technical_complexity_reasoning": "<specific comparison to examples>",
  "code_quality": <float 0.5|0.8|1.0|1.3|1.5>,
  "code_quality_reasoning": "<specific evidence from diff>",
  "risk_factor": <float 0.8|1.0|1.2|1.5|2.0>,
  "risk_factor_reasoning": "<specific assessment>",
  "impact_score": <calculated float>,
  "validation_notes": "<any edge cases or special considerations>"
}}"""

            # Set up parameters for the API call
            if self._is_reasoning_model(self.commit_analysis_model):
                # Use responses API for reasoning models with high effort
                api_params = {
                    "model": self.commit_analysis_model,
                    "reasoning": {"effort": "high"},
                    "input": [
                        {
                            "role": "user",
                            "content": f"""You are a senior engineering manager with extensive experience evaluating developer contributions. Your task is to apply the Impact Points System with extreme consistency. Always compare scores to canonical examples. Be conservative - when uncertain, score lower. Focus on concrete evidence from the diff. Output only valid JSON with no additional commentary.

{prompt}"""
                        }
                    ]
                }
                # Make API call
                response = await self.client.responses.create(**api_params)
                
                # Parse the response from responses API
                result = json.loads(response.output_text)
            else:
                # Use chat completions API for non-reasoning models
                api_params = {
                    "model": self.commit_analysis_model,
                    "messages": [
                        {
                            "role": "system", 
                            "content": """You are a senior engineering manager with extensive experience evaluating developer contributions. Your task is to apply the Impact Points System with extreme consistency. Always compare scores to canonical examples. Be conservative - when uncertain, score lower. Focus on concrete evidence from the diff. Output only valid JSON with no additional commentary."""
                        },
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.15  # Low temperature for consistency
                }
                # Make API call
                response = await self.client.chat.completions.create(**api_params)
                
                # Parse the response from chat completions API
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