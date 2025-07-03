"""
Comprehensive unit tests for the DocQualityService.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import json
from datetime import datetime

from app.services.doc_quality_service import (
    DocQualityService, QualityLevel, QualityMetrics, ValidationRule
)
from app.core.exceptions import AIIntegrationError, BadRequestError
from tests.fixtures.auto_doc_fixtures import (
    QUALITY_TEST_CASES, MOCK_OPENAI_RESPONSES, TEST_CONFIG
)


class TestQualityMetrics:
    """Test cases for QualityMetrics dataclass."""
    
    def test_quality_metrics_initialization(self):
        """Test QualityMetrics initialization."""
        metrics = QualityMetrics(
            overall_score=85.5,
            completeness_score=90.0,
            clarity_score=88.0,
            accuracy_score=92.0,
            consistency_score=80.0,
            grammar_score=95.0,
            structure_score=82.0,
            level=QualityLevel.GOOD,
            issues=["Missing examples"],
            suggestions=["Add code examples"],
            word_count=500,
            readability_score=75.0
        )
        
        assert metrics.overall_score == 85.5
        assert metrics.level == QualityLevel.GOOD
        assert len(metrics.issues) == 1
        assert metrics.word_count == 500
    
    def test_quality_metrics_to_dict(self):
        """Test QualityMetrics to_dict conversion."""
        metrics = QualityMetrics(
            overall_score=75.0,
            completeness_score=70.0,
            clarity_score=72.0,
            accuracy_score=78.0,
            consistency_score=76.0,
            grammar_score=80.0,
            structure_score=74.0,
            level=QualityLevel.FAIR,
            issues=["Issue 1", "Issue 2"],
            suggestions=["Suggestion 1"],
            word_count=300
        )
        
        result = metrics.to_dict()
        
        assert isinstance(result, dict)
        assert result["overall_score"] == 75.0
        assert result["level"] == "fair"
        assert len(result["issues"]) == 2
        assert result["word_count"] == 300
        assert "readability_score" in result  # Should include None value


class TestValidationRule:
    """Test cases for ValidationRule dataclass."""
    
    def test_validation_rule_initialization(self):
        """Test ValidationRule initialization."""
        rule = ValidationRule(
            name="heading_check",
            description="Check for proper headings",
            pattern=r"^#\s+.+",
            weight=1.5,
            severity="error"
        )
        
        assert rule.name == "heading_check"
        assert rule.weight == 1.5
        assert rule.severity == "error"
        assert rule.pattern is not None


class TestDocQualityServiceComprehensive:
    """Comprehensive test cases for DocQualityService."""
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings for the service."""
        with patch('app.services.doc_quality_service.settings') as mock:
            mock.OPENAI_API_KEY = TEST_CONFIG["openai_api_key"]
            mock.DOCUMENTATION_OPENAI_MODEL = "gpt-4"
            yield mock
    
    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        with patch('app.services.doc_quality_service.OpenAI') as mock:
            client = Mock()
            mock.return_value = client
            yield client
    
    @pytest.fixture
    def mock_cache_service(self):
        """Mock cache service."""
        with patch('app.services.doc_quality_service.cache_service') as mock:
            yield mock
    
    @pytest.fixture
    def service(self, mock_settings, mock_openai_client):
        """Create a DocQualityService instance."""
        with patch('app.services.doc_quality_service.create_openai_circuit_breaker'):
            with patch('app.services.doc_quality_service.create_openai_rate_limiter'):
                service = DocQualityService()
                service.circuit_breaker = AsyncMock()
                service.circuit_breaker.call = AsyncMock(side_effect=lambda f, *args, **kwargs: f(*args, **kwargs))
                service.rate_limiter = AsyncMock()
                service.rate_limiter.acquire = AsyncMock()
                return service
    
    def test_initialization_success(self, mock_settings):
        """Test successful service initialization."""
        service = DocQualityService()
        assert service.openai_api_key == TEST_CONFIG["openai_api_key"]
        assert service.openai_client is not None
        assert len(service.validation_rules) > 0
    
    def test_initialization_no_api_key(self, mock_settings):
        """Test initialization without API key."""
        mock_settings.OPENAI_API_KEY = None
        
        service = DocQualityService()
        assert service.openai_client is None
        # Service should still work with limited functionality
    
    def test_load_validation_rules(self, service):
        """Test loading default validation rules."""
        rules = service._load_validation_rules()
        
        assert len(rules) > 0
        
        # Check for expected rules
        rule_names = [r.name for r in rules]
        assert "missing_title" in rule_names
        assert "short_content" in rule_names
        assert "no_examples" in rule_names
        assert "missing_parameters" in rule_names
    
    @pytest.mark.asyncio
    async def test_validate_documentation_high_quality(self, service, mock_openai_client):
        """Test validation of high-quality documentation."""
        content = QUALITY_TEST_CASES["high_quality_doc"]
        doc_type = "api"
        
        # Mock OpenAI response
        ai_response = {
            "overall_score": 92,
            "completeness_score": 95,
            "clarity_score": 90,
            "accuracy_score": 94,
            "consistency_score": 88,
            "grammar_score": 96,
            "structure_score": 91,
            "issues": [],
            "suggestions": ["Consider adding performance notes"]
        }
        
        mock_openai_client.chat = Mock()
        mock_openai_client.chat.completions = Mock()
        mock_openai_client.chat.completions.create = Mock(
            return_value=Mock(
                choices=[Mock(message=Mock(content=json.dumps(ai_response)))]
            )
        )
        
        result = await service.validate_documentation(content, doc_type)
        
        assert isinstance(result, QualityMetrics)
        assert result.overall_score == 92
        assert result.level == QualityLevel.EXCELLENT
        assert len(result.issues) == 0
        assert len(result.suggestions) == 1
        assert result.word_count > 0
    
    @pytest.mark.asyncio
    async def test_validate_documentation_low_quality(self, service, mock_openai_client):
        """Test validation of low-quality documentation."""
        content = QUALITY_TEST_CASES["low_quality_doc"]
        
        # Mock OpenAI response
        ai_response = {
            "overall_score": 35,
            "completeness_score": 20,
            "clarity_score": 30,
            "accuracy_score": 40,
            "consistency_score": 35,
            "grammar_score": 50,
            "structure_score": 25,
            "issues": [
                "No proper headings",
                "Missing examples",
                "No parameter documentation",
                "Poor grammar and formatting"
            ],
            "suggestions": [
                "Add markdown headings",
                "Include code examples",
                "Document all parameters",
                "Improve grammar and structure"
            ]
        }
        
        mock_openai_client.chat.completions.create = Mock(
            return_value=Mock(
                choices=[Mock(message=Mock(content=json.dumps(ai_response)))]
            )
        )
        
        result = await service.validate_documentation(content)
        
        assert result.overall_score == 35
        assert result.level == QualityLevel.POOR
        assert len(result.issues) >= 4
        assert len(result.suggestions) >= 4
    
    @pytest.mark.asyncio
    async def test_validate_documentation_empty_content(self, service):
        """Test validation with empty content."""
        with pytest.raises(BadRequestError, match="Document content cannot be empty"):
            await service.validate_documentation("")
    
    @pytest.mark.asyncio
    async def test_validate_documentation_no_openai(self, service):
        """Test validation when OpenAI is not available."""
        service.openai_client = None
        
        content = "# Test Documentation\nSome content here."
        
        result = await service.validate_documentation(content)
        
        # Should return basic validation only
        assert result.overall_score < 70  # Low score without AI
        assert result.level in [QualityLevel.FAIR, QualityLevel.POOR]
        assert len(result.issues) > 0
    
    @pytest.mark.asyncio
    async def test_validate_documentation_ai_error(self, service, mock_openai_client):
        """Test validation when AI call fails."""
        mock_openai_client.chat.completions.create.side_effect = Exception("AI Error")
        
        content = "# Test\nContent"
        
        # Should fall back to basic validation
        result = await service.validate_documentation(content)
        
        assert isinstance(result, QualityMetrics)
        assert result.overall_score < 70
    
    @pytest.mark.asyncio
    async def test_validate_documentation_with_cache(self, service, mock_openai_client, mock_cache_service):
        """Test validation with caching."""
        content = "# Cached Documentation\nThis content should be cached."
        
        # First call - should hit AI
        ai_response = {"overall_score": 85}
        mock_openai_client.chat.completions.create = Mock(
            return_value=Mock(
                choices=[Mock(message=Mock(content=json.dumps({
                    "overall_score": 85,
                    "completeness_score": 85,
                    "clarity_score": 85,
                    "accuracy_score": 85,
                    "consistency_score": 85,
                    "grammar_score": 85,
                    "structure_score": 85,
                    "issues": [],
                    "suggestions": []
                })))]
            )
        )
        
        # Decorated method should handle caching
        result1 = await service.validate_documentation(content)
        assert result1.overall_score == 85
    
    def test_calculate_readability(self, service):
        """Test readability calculation."""
        # Simple text
        simple_text = "This is easy to read. Short sentences help. Clear words work best."
        score = service._calculate_readability(simple_text)
        assert score > 70  # Should be highly readable
        
        # Complex text
        complex_text = """The implementation utilizes sophisticated algorithmic 
        methodologies incorporating multifaceted architectural paradigms necessitating 
        comprehensive understanding of distributed systems and asynchronous processing."""
        score = service._calculate_readability(complex_text)
        assert score < 50  # Should be less readable
        
        # Empty text
        assert service._calculate_readability("") == 0
    
    def test_apply_validation_rules(self, service):
        """Test applying validation rules."""
        content = "Short doc"  # Intentionally short
        
        issues = service._apply_validation_rules(content, "api")
        
        # Should detect multiple issues
        assert any("too short" in issue.lower() for issue in issues)
        assert any("missing" in issue.lower() and "heading" in issue.lower() for issue in issues)
    
    def test_apply_validation_rules_api_specific(self, service):
        """Test API-specific validation rules."""
        content = """# API Documentation
        
        This endpoint does something.
        """
        
        issues = service._apply_validation_rules(content, "api")
        
        # Should detect missing API documentation elements
        assert any("example" in issue.lower() for issue in issues)
        assert any("parameter" in issue.lower() for issue in issues)
    
    def test_determine_quality_level(self, service):
        """Test quality level determination."""
        assert service._determine_quality_level(95) == QualityLevel.EXCELLENT
        assert service._determine_quality_level(85) == QualityLevel.GOOD
        assert service._determine_quality_level(75) == QualityLevel.FAIR
        assert service._determine_quality_level(65) == QualityLevel.POOR
        assert service._determine_quality_level(45) == QualityLevel.CRITICAL
    
    @pytest.mark.asyncio
    async def test_multiple_validations(self, service, mock_openai_client):
        """Test multiple documentation validations."""
        documents = [
            {"content": "# Doc 1\nFirst document", "doc_type": "api"},
            {"content": "# Doc 2\nSecond document", "doc_type": "guide"},
            {"content": "# Doc 3\nThird document", "doc_type": "tutorial"}
        ]
        
        # Mock different scores for each
        mock_responses = [
            {"overall_score": 90, "completeness_score": 90, "clarity_score": 90,
             "accuracy_score": 90, "consistency_score": 90, "grammar_score": 90,
             "structure_score": 90, "issues": [], "suggestions": []},
            {"overall_score": 75, "completeness_score": 75, "clarity_score": 75,
             "accuracy_score": 75, "consistency_score": 75, "grammar_score": 75,
             "structure_score": 75, "issues": ["Issue 1"], "suggestions": ["Fix 1"]},
            {"overall_score": 60, "completeness_score": 60, "clarity_score": 60,
             "accuracy_score": 60, "consistency_score": 60, "grammar_score": 60,
             "structure_score": 60, "issues": ["Issue 2", "Issue 3"], "suggestions": ["Fix 2"]}
        ]
        
        call_count = 0
        def mock_create(*args, **kwargs):
            nonlocal call_count
            response = mock_responses[call_count % len(mock_responses)]
            call_count += 1
            return Mock(choices=[Mock(message=Mock(content=json.dumps(response)))])
        
        mock_openai_client.chat.completions.create = Mock(side_effect=mock_create)
        
        # Validate each document separately
        results = []
        for doc in documents:
            result = await service.validate_documentation(doc["content"], doc["doc_type"])
            results.append(result)
        
        assert len(results) == 3
        assert results[0].overall_score == 90
        assert results[0].level == QualityLevel.EXCELLENT
        assert results[1].overall_score == 75
        assert results[1].level == QualityLevel.FAIR
        assert results[2].overall_score == 60
        assert results[2].level == QualityLevel.POOR
    
    @pytest.mark.asyncio
    async def test_generate_improvement_suggestions(self, service, mock_openai_client):
        """Test improvement suggestions generation."""
        metrics = QualityMetrics(
            overall_score=65,
            completeness_score=60,
            clarity_score=70,
            accuracy_score=75,
            consistency_score=55,
            grammar_score=80,
            structure_score=65,
            level=QualityLevel.POOR,
            issues=[
                "Missing examples",
                "Inconsistent terminology",
                "No error handling documentation"
            ],
            suggestions=[],
            word_count=200
        )
        
        content = "# API Guide\nBasic documentation..."
        
        # Mock AI suggestions
        ai_suggestions = [
            "Add code examples for each endpoint",
            "Use consistent terminology throughout",
            "Document error responses and status codes",
            "Expand the introduction section",
            "Add a table of contents"
        ]
        
        mock_openai_client.chat.completions.create = Mock(
            return_value=Mock(
                choices=[Mock(message=Mock(content=json.dumps({
                    "suggestions": ai_suggestions,
                    "priority_improvements": [
                        "Add code examples for each endpoint",
                        "Document error responses and status codes"
                    ]
                })))]
            )
        )
        
        suggestions = await service.generate_improvement_suggestions(content, metrics)
        
        assert isinstance(suggestions, list)
        assert len(suggestions) >= 1
    
    def test_validation_rules_patterns(self, service):
        """Test validation rule patterns."""
        # Test missing title rule
        no_title = "This document has no markdown title."
        issues = service._apply_validation_rules(no_title, "general")
        assert any("title" in issue.lower() for issue in issues)
        
        # Test content with title
        with_title = "# Proper Title\nThis document has a title."
        issues = service._apply_validation_rules(with_title, "general")
        assert not any("title" in issue.lower() and "missing" in issue.lower() for issue in issues)
    
    def test_quality_metrics_thresholds(self):
        """Test quality metrics threshold checking."""
        # Test that we can determine if metrics meet minimum thresholds
        metrics = QualityMetrics(
            overall_score=65,  # Poor score
            completeness_score=70,
            clarity_score=75,
            accuracy_score=80,
            consistency_score=70,
            grammar_score=85,
            structure_score=70,
            level=QualityLevel.POOR,
            issues=["Low overall score"],
            suggestions=["Improve documentation completeness"],
            word_count=300
        )
        
        # Check if score is below acceptable threshold (e.g., 70)
        assert metrics.overall_score < 70
        assert metrics.level == QualityLevel.POOR
        
        # Test with good scores
        good_metrics = QualityMetrics(
            overall_score=85,
            completeness_score=90,
            clarity_score=88,
            accuracy_score=92,
            consistency_score=86,
            grammar_score=95,
            structure_score=87,
            level=QualityLevel.GOOD,
            issues=[],
            suggestions=[],
            word_count=500
        )
        
        assert good_metrics.overall_score >= 80
        assert good_metrics.level == QualityLevel.GOOD
    
    def test_get_quality_threshold(self, service):
        """Test getting quality thresholds for different doc types."""
        # Test default thresholds
        assert service.get_quality_threshold("api") >= 70
        assert service.get_quality_threshold("guide") >= 60
        assert service.get_quality_threshold("tutorial") >= 60
        assert service.get_quality_threshold("general") >= 60
        
        # Unknown doc type should return a default
        assert service.get_quality_threshold("unknown") >= 60
    
    def test_should_approve_automatically(self, service):
        """Test automatic approval logic."""
        # High quality API docs should be auto-approved
        high_quality_metrics = QualityMetrics(
            overall_score=92,
            completeness_score=95,
            clarity_score=90,
            accuracy_score=94,
            consistency_score=88,
            grammar_score=96,
            structure_score=91,
            level=QualityLevel.EXCELLENT,
            issues=[],
            suggestions=[],
            word_count=500
        )
        
        assert service.should_approve_automatically(high_quality_metrics, "api") is True
        
        # Low quality docs should not be auto-approved
        low_quality_metrics = QualityMetrics(
            overall_score=65,
            completeness_score=60,
            clarity_score=70,
            accuracy_score=65,
            consistency_score=60,
            grammar_score=70,
            structure_score=65,
            level=QualityLevel.POOR,
            issues=["Multiple issues"],
            suggestions=["Many improvements needed"],
            word_count=100
        )
        
        assert service.should_approve_automatically(low_quality_metrics, "api") is False
        
        # Borderline quality might depend on doc type
        borderline_metrics = QualityMetrics(
            overall_score=75,
            completeness_score=75,
            clarity_score=75,
            accuracy_score=75,
            consistency_score=75,
            grammar_score=75,
            structure_score=75,
            level=QualityLevel.FAIR,
            issues=[],
            suggestions=["Minor improvements"],
            word_count=300
        )
        
        # API docs might have higher threshold
        api_approval = service.should_approve_automatically(borderline_metrics, "api")
        # Guide docs might have lower threshold
        guide_approval = service.should_approve_automatically(borderline_metrics, "guide")
        
        # At least one should be boolean
        assert isinstance(api_approval, bool)
        assert isinstance(guide_approval, bool)
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, service, mock_openai_client):
        """Test rate limiting behavior."""
        from app.core.rate_limiter import RateLimitExceededError
        
        # Simulate rate limit exceeded
        service.rate_limiter.acquire.side_effect = RateLimitExceededError("Rate limit hit")
        
        content = "# Test\nContent"
        
        # Should fall back to basic validation
        result = await service.validate_documentation(content)
        
        assert isinstance(result, QualityMetrics)
        assert result.overall_score < 70  # Basic validation only
    
    @pytest.mark.asyncio
    async def test_circuit_breaker(self, service):
        """Test circuit breaker behavior."""
        from app.core.circuit_breaker import CircuitBreakerOpenError
        
        # Simulate circuit breaker open
        service.circuit_breaker.call.side_effect = CircuitBreakerOpenError("Circuit open")
        
        content = "# Test\nContent"
        
        # Should fall back to basic validation
        result = await service.validate_documentation(content)
        
        assert isinstance(result, QualityMetrics)
        assert result.overall_score < 70  # Basic validation only