"""
Documentation Quality Validation Service

Provides AI-powered quality scoring and validation for documentation content.
Includes metrics for completeness, clarity, accuracy, and consistency.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from openai import OpenAI, APIError as OpenAIAPIError

from app.config.settings import settings
from app.core.exceptions import AIIntegrationError, ValidationError
from app.core.circuit_breaker import create_openai_circuit_breaker
from app.core.rate_limiter import create_openai_rate_limiter
from app.services.doc_cache_service import cached, cache_service

logger = logging.getLogger(__name__)


class QualityLevel(Enum):
    """Documentation quality levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


@dataclass
class QualityMetrics:
    """Detailed quality metrics for documentation."""
    overall_score: float  # 0-100
    completeness_score: float  # 0-100
    clarity_score: float  # 0-100
    accuracy_score: float  # 0-100
    consistency_score: float  # 0-100
    grammar_score: float  # 0-100
    structure_score: float  # 0-100
    
    level: QualityLevel
    issues: List[str]
    suggestions: List[str]
    word_count: int
    readability_score: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "overall_score": self.overall_score,
            "completeness_score": self.completeness_score,
            "clarity_score": self.clarity_score,
            "accuracy_score": self.accuracy_score,
            "consistency_score": self.consistency_score,
            "grammar_score": self.grammar_score,
            "structure_score": self.structure_score,
            "level": self.level.value,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "word_count": self.word_count,
            "readability_score": self.readability_score
        }


@dataclass
class ValidationRule:
    """Documentation validation rule."""
    name: str
    description: str
    pattern: Optional[str] = None
    weight: float = 1.0
    severity: str = "warning"  # "error", "warning", "info"


class DocQualityService:
    """Service for validating and scoring documentation quality."""
    
    def __init__(self):
        """Initialize the documentation quality service."""
        self.openai_api_key = settings.OPENAI_API_KEY
        
        if not self.openai_api_key:
            logger.warning("OpenAI API key not configured. Quality validation will be limited.")
            self.openai_client = None
        else:
            self.openai_client = OpenAI(api_key=self.openai_api_key)
        
        self.openai_model = getattr(settings, 'DOCUMENTATION_OPENAI_MODEL', 'gpt-4-turbo-preview')
        
        # Initialize circuit breaker and rate limiter
        self.circuit_breaker = create_openai_circuit_breaker()
        self.rate_limiter = create_openai_rate_limiter()
        
        # Load validation rules
        self.validation_rules = self._load_validation_rules()
    
    def _load_validation_rules(self) -> List[ValidationRule]:
        """Load documentation validation rules."""
        return [
            ValidationRule(
                name="headings_structure",
                description="Documentation should have proper heading hierarchy",
                pattern=r"^#{1,6}\s+.+",
                weight=2.0,
                severity="warning"
            ),
            ValidationRule(
                name="code_blocks",
                description="Code examples should be properly formatted",
                pattern=r"```[\w]*\n.*?\n```",
                weight=1.5,
                severity="info"
            ),
            ValidationRule(
                name="links_format",
                description="Links should be properly formatted",
                pattern=r"\[.*?\]\(.*?\)",
                weight=1.0,
                severity="warning"
            ),
            ValidationRule(
                name="minimum_length",
                description="Documentation should have sufficient content",
                weight=2.0,
                severity="error"
            ),
            ValidationRule(
                name="spelling_grammar",
                description="Documentation should be free of spelling and grammar errors",
                weight=1.5,
                severity="warning"
            ),
            ValidationRule(
                name="consistency",
                description="Documentation should use consistent terminology and style",
                weight=1.0,
                severity="info"
            )
        ]
    
    @cached("quality_validation", ttl_seconds=1800, key_params=["content", "doc_type"])
    async def validate_documentation(self, content: str, doc_type: str = "general", 
                                   context: Optional[Dict[str, Any]] = None) -> QualityMetrics:
        """
        Validate documentation quality and return detailed metrics.
        
        Args:
            content: Documentation content to validate
            doc_type: Type of documentation (api, guide, reference, etc.)
            context: Additional context for validation
            
        Returns:
            QualityMetrics with detailed scoring and feedback
        """
        logger.info(f"Validating documentation quality for {doc_type} document")
        
        try:
            # Basic metrics
            word_count = len(content.split())
            
            # Rule-based validation
            rule_results = self._apply_validation_rules(content)
            
            # AI-powered quality assessment (if available)
            ai_metrics = None
            if self.openai_client:
                ai_metrics = await self._ai_quality_assessment(content, doc_type, context)
            
            # Readability analysis
            readability_score = self._calculate_readability(content)
            
            # Combine results
            metrics = self._combine_quality_metrics(
                content, rule_results, ai_metrics, readability_score, word_count
            )
            
            logger.info(f"Documentation quality validation completed. Overall score: {metrics.overall_score}")
            return metrics
            
        except Exception as e:
            logger.error(f"Error during documentation quality validation: {e}", exc_info=True)
            raise ValidationError(f"Quality validation failed: {str(e)}")
    
    def _apply_validation_rules(self, content: str) -> Dict[str, Any]:
        """Apply rule-based validation to documentation content."""
        results = {
            "issues": [],
            "suggestions": [],
            "scores": {}
        }
        
        # Check heading structure
        headings = re.findall(r"^#{1,6}\s+.+", content, re.MULTILINE)
        if len(headings) == 0:
            results["issues"].append("No headings found - consider adding section headings")
            results["scores"]["structure"] = 30
        elif len(headings) < 3:
            results["issues"].append("Limited heading structure - consider adding more sections")
            results["scores"]["structure"] = 60
        else:
            results["scores"]["structure"] = 90
        
        # Check for code blocks
        code_blocks = re.findall(r"```[\w]*\n.*?\n```", content, re.DOTALL)
        if "api" in content.lower() or "code" in content.lower():
            if len(code_blocks) == 0:
                results["suggestions"].append("Consider adding code examples for better clarity")
                results["scores"]["completeness"] = 70
            else:
                results["scores"]["completeness"] = 95
        else:
            results["scores"]["completeness"] = 85
        
        # Check for links
        links = re.findall(r"\[.*?\]\(.*?\)", content)
        if len(links) > 0:
            results["scores"]["consistency"] = 90
        else:
            results["suggestions"].append("Consider adding relevant links to external resources")
            results["scores"]["consistency"] = 75
        
        # Check minimum length
        word_count = len(content.split())
        if word_count < 50:
            results["issues"].append("Documentation is very brief - consider adding more detail")
            results["scores"]["completeness"] = min(results["scores"].get("completeness", 85), 40)
        elif word_count < 100:
            results["suggestions"].append("Documentation could benefit from additional detail")
            results["scores"]["completeness"] = min(results["scores"].get("completeness", 85), 70)
        
        return results
    
    async def _ai_quality_assessment(self, content: str, doc_type: str, 
                                   context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Use AI to assess documentation quality."""
        try:
            prompt = self._create_quality_assessment_prompt(content, doc_type, context)
            
            # Apply rate limiting and circuit breaker
            await self.rate_limiter.acquire(1)
            response = await self.circuit_breaker.call(
                self.openai_client.chat.completions.create,
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": "You are an expert technical writing analyst. Evaluate documentation quality and provide detailed feedback in JSON format."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            
            # Parse AI response
            import json
            ai_response = json.loads(response.choices[0].message.content)
            
            return ai_response
            
        except Exception as e:
            logger.error(f"AI quality assessment failed: {e}")
            # Return fallback scores if AI fails
            return {
                "scores": {
                    "clarity": 75,
                    "accuracy": 80,
                    "grammar": 85
                },
                "issues": ["AI assessment unavailable"],
                "suggestions": ["Manual review recommended"]
            }
    
    def _create_quality_assessment_prompt(self, content: str, doc_type: str, 
                                        context: Optional[Dict[str, Any]]) -> str:
        """Create prompt for AI quality assessment."""
        context_info = ""
        if context:
            if context.get("file_references"):
                context_info += f"Related files: {', '.join(context['file_references'])}\n"
            if context.get("purpose"):
                context_info += f"Purpose: {context['purpose']}\n"
        
        return f"""
        Analyze the following {doc_type} documentation for quality. Provide scores (0-100) and specific feedback.
        
        {context_info}
        
        Documentation content:
        ```
        {content}
        ```
        
        Please evaluate and return a JSON response with this exact structure:
        {{
            "scores": {{
                "clarity": <0-100>,
                "accuracy": <0-100>, 
                "grammar": <0-100>,
                "completeness": <0-100>
            }},
            "issues": [
                "<specific issue 1>",
                "<specific issue 2>"
            ],
            "suggestions": [
                "<specific suggestion 1>",
                "<specific suggestion 2>"
            ],
            "strengths": [
                "<strength 1>",
                "<strength 2>"
            ]
        }}
        
        Focus on:
        1. Clarity: Is the documentation easy to understand?
        2. Accuracy: Is the information correct and up-to-date?
        3. Grammar: Are there spelling, grammar, or style issues?
        4. Completeness: Does it cover all necessary information?
        
        Be specific in your feedback and provide actionable suggestions.
        """
    
    def _calculate_readability(self, content: str) -> float:
        """Calculate readability score using simplified metrics."""
        try:
            # Simple readability calculation based on sentence and word length
            sentences = re.split(r'[.!?]+', content)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            if not sentences:
                return 0.0
            
            words = content.split()
            avg_sentence_length = len(words) / len(sentences)
            
            # Count syllables (simplified - count vowel groups)
            syllables = 0
            for word in words:
                word = word.lower().strip('.,!?;:"()[]{}')
                syllable_count = len(re.findall(r'[aeiouy]+', word))
                syllables += max(1, syllable_count)
            
            avg_syllables_per_word = syllables / len(words) if words else 0
            
            # Simplified Flesch Reading Ease approximation
            # Higher score = easier to read
            readability = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
            
            # Normalize to 0-100 range
            return max(0, min(100, readability))
            
        except Exception as e:
            logger.warning(f"Readability calculation failed: {e}")
            return 50.0  # Default neutral score
    
    def _combine_quality_metrics(self, content: str, rule_results: Dict[str, Any], 
                                ai_metrics: Optional[Dict[str, Any]], 
                                readability_score: float, word_count: int) -> QualityMetrics:
        """Combine all quality assessment results into final metrics."""
        
        # Extract scores from different sources
        rule_scores = rule_results.get("scores", {})
        ai_scores = ai_metrics.get("scores", {}) if ai_metrics else {}
        
        # Calculate individual metric scores (0-100)
        completeness_score = self._weighted_average([
            (rule_scores.get("completeness", 80), 0.6),
            (ai_scores.get("completeness", 80), 0.4)
        ])
        
        clarity_score = self._weighted_average([
            (ai_scores.get("clarity", 75), 0.7),
            (readability_score, 0.3)
        ])
        
        accuracy_score = ai_scores.get("accuracy", 80)
        
        consistency_score = self._weighted_average([
            (rule_scores.get("consistency", 80), 0.5),
            (ai_scores.get("consistency", 80), 0.5)
        ])
        
        grammar_score = ai_scores.get("grammar", 85)
        structure_score = rule_scores.get("structure", 80)
        
        # Calculate overall score with weights
        overall_score = self._weighted_average([
            (completeness_score, 0.25),
            (clarity_score, 0.20),
            (accuracy_score, 0.20),
            (grammar_score, 0.15),
            (structure_score, 0.10),
            (consistency_score, 0.10)
        ])
        
        # Determine quality level
        if overall_score >= 90:
            level = QualityLevel.EXCELLENT
        elif overall_score >= 80:
            level = QualityLevel.GOOD
        elif overall_score >= 70:
            level = QualityLevel.FAIR
        elif overall_score >= 60:
            level = QualityLevel.POOR
        else:
            level = QualityLevel.CRITICAL
        
        # Combine issues and suggestions
        issues = rule_results.get("issues", [])
        suggestions = rule_results.get("suggestions", [])
        
        if ai_metrics:
            issues.extend(ai_metrics.get("issues", []))
            suggestions.extend(ai_metrics.get("suggestions", []))
        
        return QualityMetrics(
            overall_score=round(overall_score, 1),
            completeness_score=round(completeness_score, 1),
            clarity_score=round(clarity_score, 1),
            accuracy_score=round(accuracy_score, 1),
            consistency_score=round(consistency_score, 1),
            grammar_score=round(grammar_score, 1),
            structure_score=round(structure_score, 1),
            level=level,
            issues=issues,
            suggestions=suggestions,
            word_count=word_count,
            readability_score=round(readability_score, 1)
        )
    
    def _weighted_average(self, values_and_weights: List[Tuple[float, float]]) -> float:
        """Calculate weighted average of values."""
        total_value = sum(value * weight for value, weight in values_and_weights)
        total_weight = sum(weight for _, weight in values_and_weights)
        return total_value / total_weight if total_weight > 0 else 0
    
    def get_quality_threshold(self, doc_type: str) -> float:
        """Get minimum quality threshold for document type."""
        thresholds = {
            "api": 85.0,  # API docs need high quality
            "guide": 80.0,  # User guides need good quality
            "reference": 90.0,  # Reference docs need excellent quality
            "tutorial": 85.0,  # Tutorials need high quality
            "general": 75.0  # General docs need fair quality
        }
        return thresholds.get(doc_type, 75.0)
    
    def should_approve_automatically(self, metrics: QualityMetrics, doc_type: str) -> bool:
        """Determine if documentation should be auto-approved based on quality."""
        threshold = self.get_quality_threshold(doc_type)
        
        # Auto-approve if:
        # 1. Overall score meets threshold
        # 2. No critical issues
        # 3. All individual scores are reasonable
        return (
            metrics.overall_score >= threshold and
            metrics.level in [QualityLevel.EXCELLENT, QualityLevel.GOOD] and
            all(score >= 70 for score in [
                metrics.completeness_score,
                metrics.clarity_score,
                metrics.accuracy_score,
                metrics.grammar_score
            ])
        )
    
    @cached("improvement_suggestions", ttl_seconds=3600, key_params=["content"])
    async def generate_improvement_suggestions(self, content: str, metrics: QualityMetrics) -> List[str]:
        """Generate specific improvement suggestions based on quality metrics."""
        if not self.openai_client:
            return ["AI-powered suggestions unavailable - OpenAI API key not configured"]
        
        try:
            # Focus on the lowest scoring areas
            problem_areas = []
            if metrics.completeness_score < 80:
                problem_areas.append("completeness")
            if metrics.clarity_score < 80:
                problem_areas.append("clarity")
            if metrics.grammar_score < 80:
                problem_areas.append("grammar")
            if metrics.structure_score < 80:
                problem_areas.append("structure")
            
            if not problem_areas:
                return ["Documentation quality is good - no major improvements needed"]
            
            prompt = f"""
            The following documentation has quality issues in these areas: {', '.join(problem_areas)}
            
            Current issues identified: {'; '.join(metrics.issues)}
            
            Documentation content:
            ```
            {content}
            ```
            
            Please provide 3-5 specific, actionable suggestions to improve the documentation quality.
            Focus on the problem areas: {', '.join(problem_areas)}
            
            Return suggestions as a simple list, one suggestion per line.
            """
            
            await self.rate_limiter.acquire(1)
            response = await self.circuit_breaker.call(
                self.openai_client.chat.completions.create,
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": "You are a technical writing expert. Provide specific, actionable suggestions for improving documentation."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            suggestions_text = response.choices[0].message.content.strip()
            suggestions = [line.strip() for line in suggestions_text.split('\n') if line.strip()]
            
            return suggestions[:5]  # Limit to 5 suggestions
            
        except Exception as e:
            logger.error(f"Failed to generate improvement suggestions: {e}")
            return ["Failed to generate AI-powered suggestions - manual review recommended"]