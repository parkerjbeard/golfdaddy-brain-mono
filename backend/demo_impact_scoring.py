"""
Demo script to show the difference between hours estimation and impact scoring.
This demonstrates how the new system works for your boss.
"""

def calculate_impact_score(business_value, technical_complexity, code_quality, risk_factor):
    """Calculate the impact score using the formula"""
    return round((business_value * technical_complexity * code_quality) / risk_factor, 1)


def demo_scenarios():
    """Show various scenarios comparing hours vs impact scoring"""
    
    scenarios = [
        {
            "name": "LLM-Assisted CRUD Feature",
            "description": "Developer uses LLM to quickly generate a standard CRUD API",
            "traditional": {
                "estimated_hours": 0.5,  # Very quick with LLM
                "complexity": 2,
                "seniority": 5
            },
            "impact": {
                "business_value": 4,  # Nice-to-have feature
                "technical_complexity": 2,  # Simple API endpoint
                "code_quality": 1.0,  # Adequate tests
                "risk_factor": 1.0,  # Appropriate solution
                "score": calculate_impact_score(4, 2, 1.0, 1.0)
            }
        },
        {
            "name": "Game Physics Engine Optimization",
            "description": "Hand-crafted optimization of collision detection algorithm",
            "traditional": {
                "estimated_hours": 6.0,  # Complex manual work
                "complexity": 8,
                "seniority": 9
            },
            "impact": {
                "business_value": 6,  # Improves game performance
                "technical_complexity": 9,  # Complex algorithm + game dev bonus
                "code_quality": 1.2,  # Good documentation
                "risk_factor": 1.0,  # Appropriate solution
                "score": calculate_impact_score(6, 9, 1.2, 1.0)
            }
        },
        {
            "name": "Payment Integration (LLM-Assisted)",
            "description": "LLM helps implement Stripe integration with proper error handling",
            "traditional": {
                "estimated_hours": 2.0,  # Faster with LLM
                "complexity": 6,
                "seniority": 7
            },
            "impact": {
                "business_value": 8,  # Direct revenue impact
                "technical_complexity": 6,  # Multi-service integration
                "code_quality": 1.5,  # Comprehensive tests
                "risk_factor": 1.5,  # High financial risk
                "score": calculate_impact_score(8, 6, 1.5, 1.5)
            }
        },
        {
            "name": "Emergency Production Fix",
            "description": "Quick fix for critical bug (manual debugging required)",
            "traditional": {
                "estimated_hours": 0.25,  # Very quick fix
                "complexity": 3,
                "seniority": 8
            },
            "impact": {
                "business_value": 10,  # Critical to business
                "technical_complexity": 3,  # Simple fix
                "code_quality": 0.8,  # Minimal tests due to urgency
                "risk_factor": 2.0,  # Emergency fix
                "score": calculate_impact_score(10, 3, 0.8, 2.0)
            }
        }
    ]
    
    print("🎯 IMPACT SCORING VS HOURS ESTIMATION COMPARISON\n")
    print("=" * 80)
    
    for scenario in scenarios:
        print(f"\n📋 {scenario['name']}")
        print(f"   {scenario['description']}")
        print(f"\n   Traditional Hours: {scenario['traditional']['estimated_hours']}h")
        print(f"   Impact Score: {scenario['impact']['score']} points")
        print(f"\n   Breakdown:")
        print(f"   • Business Value: {scenario['impact']['business_value']}/10")
        print(f"   • Technical Complexity: {scenario['impact']['technical_complexity']}/10")
        print(f"   • Code Quality: {scenario['impact']['code_quality']}x")
        print(f"   • Risk Factor: {scenario['impact']['risk_factor']}x")
        print(f"\n   Formula: ({scenario['impact']['business_value']} × {scenario['impact']['technical_complexity']} × {scenario['impact']['code_quality']}) ÷ {scenario['impact']['risk_factor']} = {scenario['impact']['score']}")
        print("-" * 80)
    
    print("\n🔍 KEY INSIGHTS:\n")
    print("1. LLM-Assisted CRUD (0.5h) → 8.0 impact points")
    print("   - Low hours due to LLM assistance, but also low business impact")
    print("\n2. Game Physics (6.0h) → 64.8 impact points")
    print("   - High hours for manual work, high impact due to complexity and performance gains")
    print("\n3. Payment Integration (2.0h) → 48.0 impact points")
    print("   - Medium hours with LLM help, but high impact due to revenue importance")
    print("\n4. Emergency Fix (0.25h) → 12.0 impact points")
    print("   - Very low hours, but decent impact due to critical business need")
    
    print("\n✨ CONCLUSION:")
    print("Impact scoring better reflects actual value delivered, regardless of whether")
    print("LLM assistance was used. It rewards business value and technical achievement")
    print("rather than time spent coding.")


if __name__ == "__main__":
    demo_scenarios()