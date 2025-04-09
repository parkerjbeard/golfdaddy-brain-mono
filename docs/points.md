# AI-Assisted Commit Point System

This document outlines our simplified, AI-assisted point system for quantifying developer productivity through commit analysis.

## Overview

We use a combination of AI analysis and minimal formula-based scaling to assess the complexity, time investment, and risk level of each commit. The system prioritizes the AI's direct assessment with minimal adjustments to ensure the results stay close to the AI's expert judgment.

## Data Collection

1. **Raw Commit Data**  
   - Author information
   - Commit timestamp
   - Lines added / deleted
   - Files changed
   - Commit message

2. **AI-Based Assessment**  
   - Complexity score (1-10)
   - Estimated hours
   - Risk level (low/medium/high)
   - Key changes identified
   - Technical debt concerns
   - Improvement suggestions

## Point Calculation Formula

Our simplified point formula focuses primarily on the AI's complexity assessment with a minimal risk adjustment:

```
commit_points = complexity_score × complexity_weight × risk_factor
```

Where:
- **complexity_score** is the AI's assessment (1-10)
- **complexity_weight** is 2.0 (base weight for complexity)
- **risk_factor** depends on the risk level:
  - low: 1.0 (no adjustment)
  - medium: 1.2 (20% increase)
  - high: 1.5 (50% increase)

## Understanding Risk Factor

The risk factor represents the potential for unexpected complications, side effects, or additional work that might arise from a commit's changes:

1. **Risk Assessment**
   - The AI evaluates the commit's risk level by considering:
     - Whether changes affect critical system components
     - The scope of impact (isolated vs. widespread changes)
     - Potential for regression or side effects
     - Security implications
     - Degree of architectural modification

2. **Risk Level Mapping**
   - **Low Risk** (factor = 1.0): Isolated changes with minimal chance of regression
     - Examples: Documentation updates, simple bug fixes, minor UI tweaks
     - No adjustment applied to complexity points or hours
   
   - **Medium Risk** (factor = 1.2): Changes affecting multiple components or introducing new patterns
     - Examples: New features, refactoring, database schema changes
     - 20% increase applied to complexity points and hours
   
   - **High Risk** (factor = 1.5): Core functionality changes or security-critical modifications
     - Examples: Authentication changes, payment processing, core architecture updates
     - 50% increase applied to complexity points and hours

3. **Application of Risk Factor**
   - For **points calculation**: Always applied as a multiplier
   - For **hour estimation**: Applied only to medium and high risk commits
     - Low risk: Uses AI's hour estimate directly
     - Medium/high risk: AI's estimate multiplied by the risk factor

This approach provides a balanced way to account for risk without overriding the AI's expert assessment.

## Time Estimation

We trust the AI's time estimates with minimal adjustments:

```
adjusted_hours = estimated_hours                  (for low risk)
adjusted_hours = estimated_hours × risk_factor    (for medium/high risk)
```

The final hours are rounded to the nearest 0.5 for readability.

## Example Calculation

For a commit with:
- Complexity score: 5
- Risk level: medium
- AI estimated hours: 3

The calculation would be:
- Points: 5 × 2.0 × 1.2 = 12 points
- Adjusted hours: 3 × 1.2 = 3.6, rounded to 3.5 hours

## Implementation Details

1. **CommitAnalysisService**
   - Uses AIIntegration to get the initial AI assessment
   - Applies the simple point formula
   - Records detailed calculation components for transparency
   - Preserves all AI insights (key changes, technical debt, suggestions)

2. **Benefits of Simplified Approach**
   - Results stay close to the AI's expert judgment
   - Minimal risk-based adjustments provide consistency
   - Transparent calculation makes estimates understandable
   - Removes unnecessary complexity in the formula

## Weekly Aggregation

Weekly points are calculated by simply summing the points from all commits within that period:

```
weekly_points = sum(commit_points for all commits in week)
```

This simple approach ensures that productivity metrics remain directly tied to the AI's assessment of the work performed.

## Calibration and Adjustment

The simplified formula uses minimal coefficients that can be adjusted if needed:
- Increase **complexity_weight** if points are consistently too low
- Adjust **risk_factors** if certain risk levels need more/less emphasis

However, the philosophy of this approach is to trust the AI's judgment and apply minimal adjustments, letting the sophisticated AI assessment drive the point calculation.