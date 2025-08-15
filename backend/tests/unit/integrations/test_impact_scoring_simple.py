"""
Simple test to verify impact scoring logic without full app dependencies.
This test focuses on the prompt structure and response parsing.
"""

import json


def test_impact_score_calculation():
    """Test the impact score calculation formula"""
    # Test data
    business_value = 8
    technical_complexity = 6
    code_quality = 1.2
    risk_factor = 1.5

    # Calculate impact score
    impact_score = (business_value * technical_complexity * code_quality) / risk_factor
    impact_score = round(impact_score, 1)

    # Expected: (8 * 6 * 1.2) / 1.5 = 38.4
    assert impact_score == 38.4


def test_calibration_examples():
    """Test that calibration examples are properly structured"""
    CALIBRATION_EXAMPLES = {
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

    # Verify structure
    assert "business_value" in CALIBRATION_EXAMPLES
    assert "technical_complexity" in CALIBRATION_EXAMPLES
    assert "code_quality" in CALIBRATION_EXAMPLES

    # Verify business value scores
    assert "10" in CALIBRATION_EXAMPLES["business_value"]
    assert "1" in CALIBRATION_EXAMPLES["business_value"]

    # Verify code quality multipliers
    assert "1.5" in CALIBRATION_EXAMPLES["code_quality"]
    assert "0.5" in CALIBRATION_EXAMPLES["code_quality"]


def test_impact_prompt_structure():
    """Test that the impact scoring prompt contains required elements"""
    # Sample prompt structure
    prompt_template = """Analyze this commit using the Impact Points System. You must score exactly according to these definitions.

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
Impact Score = (Business Value × Technical Complexity × Code Quality) / Risk Factor"""

    # Verify key elements are present
    assert "Impact Points System" in prompt_template
    assert "Business Value Score (1-10)" in prompt_template
    assert "Technical Complexity Score (1-10)" in prompt_template
    assert "Code Quality Multiplier (0.5-1.5)" in prompt_template
    assert "Risk Factor (0.8-2.0)" in prompt_template
    assert "Impact Score = (Business Value × Technical Complexity × Code Quality) / Risk Factor" in prompt_template


def test_combined_result_structure():
    """Test the structure of combined hours and impact results"""
    # Sample combined result
    combined_result = {
        # Traditional hours-based analysis
        "complexity_score": 6,
        "estimated_hours": 3.5,
        "risk_level": "high",
        "seniority_score": 7,
        "seniority_rationale": "Well-structured implementation",
        "key_changes": ["Feature A", "Test B"],
        # Impact scoring analysis (prefixed with impact_)
        "impact_business_value": 8,
        "impact_business_value_reasoning": "Direct revenue impact",
        "impact_technical_complexity": 6,
        "impact_technical_complexity_reasoning": "Multi-service integration",
        "impact_code_quality": 1.2,
        "impact_code_quality_reasoning": "Good test coverage",
        "impact_risk_factor": 1.5,
        "impact_risk_factor_reasoning": "Financial risk",
        "impact_score": 38.4,
        "impact_dominant_category": "feature",
        # Metadata
        "analyzed_at": "2024-01-01T12:00:00",
        "commit_hash": "abc123",
        "repository": "test-repo",
        "model_used": "gpt-4",
        "scoring_methods": ["hours_estimation", "impact_points"],
    }

    # Verify all fields are present
    # Hours fields
    assert "complexity_score" in combined_result
    assert "estimated_hours" in combined_result
    assert "risk_level" in combined_result
    assert "seniority_score" in combined_result

    # Impact fields (all prefixed)
    assert "impact_business_value" in combined_result
    assert "impact_technical_complexity" in combined_result
    assert "impact_code_quality" in combined_result
    assert "impact_risk_factor" in combined_result
    assert "impact_score" in combined_result

    # Metadata
    assert combined_result["scoring_methods"] == ["hours_estimation", "impact_points"]


if __name__ == "__main__":
    test_impact_score_calculation()
    test_calibration_examples()
    test_impact_prompt_structure()
    test_combined_result_structure()
    print("✅ All simple tests passed!")
