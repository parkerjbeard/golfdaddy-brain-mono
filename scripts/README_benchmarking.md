# Commit Analysis Benchmarking Tool

## Overview

The benchmarking tool (`benchmark_commit_analysis.py`) tests the consistency of AI-powered commit analysis by running the same commit through the model multiple times and analyzing the variance in results.

## Purpose

When using AI for commit analysis, it's important to understand:
- How consistent are the scores across multiple runs?
- Which metrics have the highest variance?
- Is the Impact Points system more or less consistent than Traditional Hours?
- How does model temperature affect consistency?

## Prerequisites

1. Backend virtual environment activated
2. Environment variables configured:
   - `GITHUB_TOKEN` - GitHub Personal Access Token
   - `OPENAI_API_KEY` - OpenAI API key
   - Backend database credentials

## Usage

```bash
# Activate backend environment
cd backend
source venv/bin/activate

# Run benchmarking tool
cd ..
python scripts/benchmark_commit_analysis.py
```

## Workflow

1. **Prerequisites Check**: Verifies all required modules and tokens
2. **Repository Selection**: Choose or enter a GitHub repository
3. **Commit Selection**: Browse recent commits and select one
4. **Benchmarking**: Runs analysis 10 times with progress tracking
5. **Analysis**: Shows statistical breakdown of results
6. **Save Results**: Stores detailed JSON in `benchmark_results/`
7. **Repeat**: Option to benchmark additional commits

## Metrics Analyzed

### Traditional Hours Method
- **AI Estimated Hours**: Time estimation consistency
- **Complexity Score**: Technical difficulty assessment
- **Seniority Score**: Code quality evaluation
- **Risk Level**: Security/stability risk categorization

### Impact Points Method
- **Business Value**: Importance to users/revenue
- **Technical Complexity**: Problem difficulty
- **Code Quality Multiplier**: Testing/documentation bonus
- **Risk Factor**: Critical system impact
- **Total Impact Score**: Combined metric

## Statistical Measures

For each metric, the tool calculates:
- **Mean**: Average across all runs
- **Standard Deviation**: Measure of variance
- **Min/Max**: Range of values
- **Range**: Difference between min and max
- **CV% (Coefficient of Variation)**: Std Dev / Mean × 100

## Consistency Ratings

Based on CV% (lower is better):
- **Excellent**: < 10% - Very consistent results
- **Good**: 10-20% - Acceptable variance
- **Fair**: > 20% - Higher variance, may need prompt tuning

## Output Format

Results are saved as JSON files with structure:
```json
{
  "commit_data": {
    "repository": "owner/repo",
    "sha": "commit_hash",
    "message": "commit message",
    "author": "author name",
    "date": "ISO date"
  },
  "runs": [
    {
      "run_index": 1,
      "analysis_time": 5.23,
      "traditional_hours": {
        "ai_estimated_hours": 4.5,
        "complexity_score": 7,
        "seniority_score": 8,
        "risk_level": "medium"
      },
      "impact_points": {
        "business_value": 8,
        "technical_complexity": 7,
        "code_quality": 1.2,
        "risk_factor": 0.9,
        "total_score": 74.67
      }
    }
    // ... more runs
  ],
  "timestamp": "2024-03-15T14:30:22",
  "config": {
    "runs": 10,
    "model": "gpt-4"
  }
}
```

## Interpreting Results

### Good Signs
- Low CV% across metrics
- Consistent risk level assessments
- Similar reasoning patterns
- Stable impact scores

### Areas of Concern
- High variance in hours estimation
- Inconsistent complexity ratings
- Changing risk assessments
- Wide range in business value scores

## Use Cases

1. **Model Tuning**: Test different temperatures or prompts
2. **Quality Assurance**: Verify consistency before production
3. **Comparison**: Benchmark different AI models
4. **Documentation**: Provide evidence of system reliability
5. **Debugging**: Identify problematic commit patterns

## Tips

- Run benchmarks on various commit types (bug fixes, features, refactors)
- Test with commits of different sizes
- Compare morning vs evening runs (API load variance)
- Save results for long-term consistency tracking
- Use results to refine AI prompts

## Example Session

```
Welcome to Commit Analysis Benchmarking Tool

Checking prerequisites...
✓ Backend Modules
✓ GitHub Token  
✓ OpenAI API Key

Enter repository name [parkerbeard/golfdaddy-brain-mono]: ↵

Recent Commits:
# | SHA     | Message                          | Author | Date
1 | 3421a08 | test: add comprehensive unit...  | Parker | 2024-03-15
2 | 9c30b14 | feat: enhance demo script...     | Parker | 2024-03-14

Select commit number [1]: 1

Running 10 analyses... ████████████ 100%

Statistical Analysis:
Traditional Hours Method
- AI Estimated Hours: Mean 4.3, CV 8.2% (Excellent)
- Complexity Score: Mean 7.1, CV 5.6% (Excellent)

Impact Points Method  
- Total Impact Score: Mean 72.4, CV 11.3% (Good)

✓ Results saved to: benchmark_results/benchmark_20240315_143022_commit_3421a08.json

Would you like to benchmark another commit? [Y/n]: 
```