# Parallel Commit Analysis Benchmarking

## Overview

The parallel benchmarking tool (`benchmark_commit_analysis_parallel.py`) provides 3-5x faster execution compared to the serial version by using asyncio to run multiple API calls concurrently.

## Key Differences from Serial Version

| Feature | Serial | Parallel |
|---------|--------|----------|
| Execution | One at a time | Concurrent batches |
| 10 runs time | ~30-60 seconds | ~10-20 seconds |
| Rate limiting | Natural (sequential) | Configured delays |
| Resource usage | Low | Moderate |
| Results format | Same | Same + timing data |

## How It Works

1. **Asyncio Event Loop**: Uses Python's `asyncio` for concurrent execution
2. **Batch Processing**: Runs analyses in configurable batches (default: 3 concurrent)
3. **Rate Limit Protection**: Adds delays between batches to respect API limits
4. **Same Analysis**: Identical commit analysis logic, just executed in parallel

## Configuration

In the script, you can adjust:
```python
"max_concurrent_requests": 3,  # Number of parallel requests
"rate_limit_delay": 0.5,      # Seconds between batches
```

## Running the Tools

### Quick Start (Recommended)
```bash
# Run parallel version (faster)
./scripts/run_benchmark_parallel.sh

# Run serial version (for comparison)
./scripts/run_benchmark.sh
```

### Manual Execution
```bash
# Activate backend environment
cd backend && source venv/bin/activate
cd ..

# Run parallel benchmarking
python scripts/benchmark_commit_analysis_parallel.py

# Run serial benchmarking
python scripts/benchmark_commit_analysis.py
```

## Visual Experience

Both tools provide the same beautiful Rich terminal UI:
- Welcome screen with mode indicator
- Prerequisites check table
- Commit selection browser
- Live progress bar (shows batch progress for parallel)
- Statistical results tables
- Execution performance metrics (parallel only)

## Performance Comparison

Example for 10 runs of the same commit:

**Serial Mode:**
```
Running 10 analyses... ████████████ 100%
Total time: 52.3s
```

**Parallel Mode (3 concurrent):**
```
Running batch 1/4... ████████████ 100%
Total time: 14.7s
Estimated speedup: 3.6x
```

## When to Use Each Version

**Use Parallel (`run_benchmark_parallel.sh`) when:**
- You want faster results
- Testing multiple commits
- Your API limits allow concurrent requests
- Normal benchmarking workflow

**Use Serial (`run_benchmark.sh`) when:**
- Debugging API issues
- Very strict rate limits
- Need predictable request timing
- Comparing with baseline behavior

## Rate Limiting Considerations

The parallel version respects rate limits by:
1. Processing in batches (default: 3 concurrent)
2. Adding delays between batches (default: 0.5s)
3. Handling API errors gracefully

Adjust `max_concurrent_requests` based on your API tier:
- Free tier: 2-3 concurrent
- Paid tier: 5-10 concurrent
- Enterprise: 10+ concurrent

## Results Format

Both versions save identical JSON output:
```json
{
  "config": {
    "execution_mode": "parallel",  // or "serial"
    "max_concurrent": 3,           // parallel only
    ...
  },
  "runs": [...],  // Same format
  ...
}
```

## Troubleshooting

**"Rate limit exceeded" errors:**
- Reduce `max_concurrent_requests`
- Increase `rate_limit_delay`

**Inconsistent timing:**
- API response times vary
- Network latency affects results
- Run multiple benchmarks for average

**Memory usage high:**
- Reduce batch size
- Close other applications

## Tips

1. Start with default settings (3 concurrent)
2. Monitor for rate limit errors
3. Compare serial vs parallel consistency
4. Save results for long-term analysis
5. Run during off-peak hours for best performance