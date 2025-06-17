# Historical Commit Seeding Guide

This guide explains how to use the historical commit seeding functionality to backfill commit analysis data.

## Overview

The `seed_historical_commits.py` script:
- Fetches commits from GitHub repositories for a specified time period
- Groups commits by author and date
- Analyzes each commit using the AI model to estimate hours worked
- Stores results in the database (optional)
- Provides detailed summaries of work done

## Prerequisites

1. **Environment Variables** (in `backend/.env`):
   ```bash
   GITHUB_TOKEN=your_github_token_here  # Optional but recommended for rate limits
   OPENAI_API_KEY=your_openai_api_key_here  # Required
   ```

2. **Database Configuration** (if storing results):
   - Ensure your Supabase credentials are configured
   - Database migrations should be up to date

## Usage

### Basic Usage

```bash
cd backend/scripts

# Analyze last 30 days of the main branch
python seed_historical_commits.py --repo owner/repository

# Analyze last 7 days with specific model
python seed_historical_commits.py --repo owner/repository --days 7 --model gpt-4o-mini

# Dry run (analysis only, no database storage)
python seed_historical_commits.py --repo owner/repository --dry-run

# Analyze specific branches
python seed_historical_commits.py --repo owner/repository --branches main develop feature/xyz

# Quick test with single branch
python seed_historical_commits.py --repo microsoft/vscode --days 1 --single-branch --dry-run
```

### Command Line Options

- `--repo`: Repository to analyze (format: owner/repo)
- `--days`: Number of days to look back (default: 30)
- `--branches`: Specific branches to analyze (default: all branches)
- `--single-branch`: Only analyze the main branch (faster for testing)
- `--dry-run`: Run analysis without storing results in database
- `--model`: OpenAI model to use (e.g., gpt-4o-mini, o1-mini)
- `--output`: Save results to JSON file

### Examples

1. **Full Repository Analysis (Last Month)**
   ```bash
   python seed_historical_commits.py --repo myorg/myrepo
   ```

2. **Test Run on Public Repository**
   ```bash
   python seed_historical_commits.py --repo microsoft/vscode --days 3 --single-branch --dry-run --output vscode_analysis.json
   ```

3. **Analyze Specific Team's Work**
   ```bash
   python seed_historical_commits.py --repo myorg/myrepo --branches develop staging --days 14
   ```

## Output

The script provides:

1. **Real-time Progress**:
   - Branch scanning
   - Commit fetching
   - Analysis progress per author/day
   - Rate limit status

2. **Final Summary**:
   - Total commits analyzed
   - Unique authors
   - Total estimated hours
   - Top contributors by hours

3. **JSON Output** (if --output specified):
   ```json
   {
     "repository": "owner/repo",
     "date_range": {
       "since": "2024-12-18T00:00:00",
       "until": "2025-01-17T00:00:00"
     },
     "summary": {
       "total_commits": 150,
       "unique_authors": 25,
       "total_hours": 450.5,
       "daily_summaries": [...]
     }
   }
   ```

## How It Works

1. **Fetch Branches**: Gets all branches from the repository (or uses specified branches)
2. **Collect Commits**: For each branch, fetches commits within the date range
3. **Deduplicate**: Removes duplicate commits that appear in multiple branches
4. **Group by Author/Date**: Organizes commits by author email and date
5. **AI Analysis**: For each author's daily commits:
   - Fetches full diff for each commit
   - Sends to AI model for hour estimation
   - Aggregates results
6. **Store Results**: Optionally saves to database

## Performance Considerations

- **API Rate Limits**: 
  - Unauthenticated: 60 requests/hour
  - Authenticated: 5,000 requests/hour
  - Script handles rate limiting automatically

- **Processing Time**:
  - Each commit analysis takes 2-5 seconds
  - Large repositories may take hours to fully analyze
  - Use `--single-branch` and `--days` to limit scope for testing

- **Cost Estimation**:
  - Each commit uses ~1,000-5,000 tokens
  - Cost depends on model selected
  - Example: 1,000 commits ≈ $0.50-$2.00 with gpt-4o-mini

## Testing

Run the test script to verify functionality:

```bash
python test_historical_seeding.py
```

This will:
1. Test GitHub API connectivity
2. Fetch sample commits from VS Code repo
3. Run a small analysis
4. Save results to `test_seeding_results.json`

## Troubleshooting

1. **Rate Limit Errors**: 
   - Add GITHUB_TOKEN to increase limits
   - Script automatically waits when limits are hit

2. **Memory Issues**:
   - Use smaller date ranges
   - Process specific branches
   - Run in batches

3. **Analysis Failures**:
   - Check OpenAI API key is valid
   - Verify model name is correct
   - Some commits may be too large to analyze

## Integration with Daily Reports

The seeded data integrates with the existing system:
- Individual commit analyses are stored
- Can be cross-referenced with EOD reports
- Provides baseline data for productivity tracking
- Enables historical reporting and analytics