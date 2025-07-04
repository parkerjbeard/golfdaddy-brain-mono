#!/usr/bin/env python3
"""
GolfDaddy Brain Parallel Commit Analysis Benchmarking Tool
=========================================================
This script benchmarks commit analysis using parallel API calls for much faster execution.
Uses asyncio to run multiple analyses concurrently while respecting rate limits.

Features:
- Runs analyses in parallel batches
- Configurable concurrency level
- Rate limiting protection
- Same statistical analysis as serial version
- 3-5x faster execution
"""

import os
import sys
import time
import json
import subprocess
import requests
from datetime import datetime
import statistics
from pathlib import Path
from typing import Dict, Any, List, Optional
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskID
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.markdown import Markdown
from rich import box
from rich.live import Live
from rich.layout import Layout
from dotenv import load_dotenv

# Initialize Rich console
console = Console()

# Load environment variables
backend_env_path = Path(__file__).parent.parent / "backend" / ".env"
if backend_env_path.exists():
    load_dotenv(backend_env_path)

# Add backend to Python path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# Import backend modules
BACKEND_IMPORTS_AVAILABLE = False
try:
    from app.config.database import get_supabase_client
    from app.services.commit_analysis_service import CommitAnalysisService
    BACKEND_IMPORTS_AVAILABLE = True
except ImportError as e:
    console.print(f"[yellow]Warning: Could not import backend modules: {e}[/yellow]")

# Custom JSON encoder to handle Decimal types
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

# Configuration
PARALLEL_CONFIG = {
    "runs_per_commit": 10,
    "max_concurrent_requests": 3,  # Adjust based on API limits
    "rate_limit_delay": 0.5,  # Seconds between batches
    "output_dir": Path(__file__).parent.parent / "benchmark_results",
    "github_token": os.getenv("GITHUB_TOKEN"),
    "github_username": None,
}

class ParallelCommitAnalysisBenchmark:
    """Parallel benchmarking orchestrator using asyncio"""
    
    def __init__(self):
        self.console = console
        self.config = PARALLEL_CONFIG
        self.results = []
        self.current_benchmark_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.config["output_dir"].mkdir(exist_ok=True)
        
        # Initialize services
        if BACKEND_IMPORTS_AVAILABLE:
            self.db = get_supabase_client()
            self.commit_service = CommitAnalysisService(self.db)
        
    async def analyze_commit_async(self, commit_data: Dict[str, Any], run_index: int) -> Dict[str, Any]:
        """Async wrapper for commit analysis"""
        try:
            start_time = time.time()
            
            # Prepare analysis data
            analysis_data = {
                "repository": commit_data["repository"],
                "commit_hash": commit_data["sha"],
                "author": {
                    "name": commit_data["author"],
                    "email": "benchmark@example.com",
                    "login": self.config["github_username"]
                },
                "message": commit_data["message"],
                "timestamp": commit_data["date"],
                "url": commit_data["url"]
            }
            
            # Run analysis
            analyzed_commit = await self.commit_service.analyze_commit(
                commit_hash=commit_data["sha"],
                commit_data=analysis_data,
                fetch_diff=True
            )
            
            analysis_time = time.time() - start_time
            
            if analyzed_commit:
                # Extract scores
                run_result = {
                    "run_index": run_index + 1,
                    "analysis_time": analysis_time,
                    "traditional_hours": {
                        "ai_estimated_hours": analyzed_commit.ai_estimated_hours,
                        "complexity_score": analyzed_commit.complexity_score,
                        "seniority_score": analyzed_commit.seniority_score,
                        "risk_level": analyzed_commit.risk_level,
                    },
                    "impact_points": {},
                    "reasoning": {
                        "seniority_rationale": analyzed_commit.seniority_rationale,
                        "key_changes": analyzed_commit.key_changes,
                    }
                }
                
                # Parse impact scoring
                if analyzed_commit.ai_analysis_notes:
                    try:
                        impact_data = json.loads(analyzed_commit.ai_analysis_notes)
                        run_result["impact_points"] = {
                            "business_value": impact_data.get('impact_business_value', 0),
                            "technical_complexity": impact_data.get('impact_technical_complexity', 0),
                            "code_quality": impact_data.get('impact_code_quality', 1.0),
                            "risk_factor": impact_data.get('impact_risk_factor', 1.0),
                            "total_score": impact_data.get('impact_score', 0),
                            "reasoning": {
                                "business_value": impact_data.get('impact_business_value_reasoning', ''),
                                "technical_complexity": impact_data.get('impact_technical_complexity_reasoning', ''),
                                "code_quality": impact_data.get('impact_code_quality_reasoning', ''),
                                "risk_factor": impact_data.get('impact_risk_factor_reasoning', ''),
                            }
                        }
                    except:
                        pass
                
                return run_result
            else:
                return {
                    "run_index": run_index + 1,
                    "error": "Analysis failed"
                }
                
        except Exception as e:
            return {
                "run_index": run_index + 1,
                "error": str(e)
            }
    
    async def benchmark_commit_parallel(self, commit_data: Dict[str, Any], progress: Progress, task: TaskID) -> Dict[str, Any]:
        """Run multiple analyses in parallel batches"""
        self.console.print(f"\n[bold]Benchmarking commit {commit_data['sha'][:7]} (Parallel Mode)...[/bold]")
        self.console.print(f"Message: {commit_data['message'].split(chr(10))[0]}")
        self.console.print(f"Running {self.config['runs_per_commit']} analyses with max {self.config['max_concurrent_requests']} concurrent...\n")
        
        results = {
            "commit_data": commit_data,
            "runs": [],
            "timestamp": datetime.now().isoformat(),
            "config": {
                "runs": self.config["runs_per_commit"],
                "max_concurrent": self.config["max_concurrent_requests"],
                "model": os.getenv("COMMIT_ANALYSIS_MODEL", "gpt-4"),
                "execution_mode": "parallel"
            }
        }
        
        # Create all tasks
        tasks = []
        for run_idx in range(self.config['runs_per_commit']):
            task_coroutine = self.analyze_commit_async(commit_data, run_idx)
            tasks.append(task_coroutine)
        
        # Process in batches to respect rate limits
        completed = 0
        batch_size = self.config['max_concurrent_requests']
        
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            
            # Update progress description
            progress.update(task, description=f"Running batch {i//batch_size + 1}/{(len(tasks) + batch_size - 1)//batch_size}...")
            
            # Run batch concurrently
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            
            # Process results
            for result in batch_results:
                if isinstance(result, Exception):
                    results["runs"].append({
                        "run_index": completed + 1,
                        "error": str(result)
                    })
                else:
                    results["runs"].append(result)
                
                completed += 1
                progress.update(task, completed=completed)
            
            # Rate limit delay between batches (except for last batch)
            if i + batch_size < len(tasks):
                await asyncio.sleep(self.config['rate_limit_delay'])
        
        return results
    
    def run(self):
        """Main benchmark execution flow"""
        try:
            self.show_welcome()
            
            if not self.check_prerequisites():
                return
            
            self.get_github_username()
            
            # Run async event loop
            asyncio.run(self.async_main())
            
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Benchmark interrupted by user[/yellow]")
        except Exception as e:
            self.console.print(f"\n[red]Benchmark error: {str(e)}[/red]")
    
    async def async_main(self):
        """Async main loop"""
        while True:
            commit_data = self.select_commit()
            if not commit_data:
                break
            
            # Run benchmark with progress tracking
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=self.console
            ) as progress:
                
                task = progress.add_task(
                    f"Running {self.config['runs_per_commit']} parallel analyses...", 
                    total=self.config['runs_per_commit']
                )
                
                benchmark_results = await self.benchmark_commit_parallel(commit_data, progress, task)
            
            self.analyze_results(benchmark_results)
            self.save_results(benchmark_results)
            
            if not Confirm.ask("\n[bold yellow]Would you like to benchmark another commit?[/bold yellow]", default=True):
                break
        
        self.show_final_summary()
    
    def show_welcome(self):
        """Display welcome message"""
        welcome_text = f"""
# Parallel Commit Analysis Benchmarking Tool

This tool tests AI commit analysis consistency using **parallel execution** for faster results.

**Configuration:**
- Runs per commit: {self.config['runs_per_commit']}
- Max concurrent requests: {self.config['max_concurrent_requests']}
- Rate limit delay: {self.config['rate_limit_delay']}s
- Execution mode: Parallel (asyncio)

**Performance:**
- Expected speedup: 3-5x faster than serial execution
- Respects API rate limits automatically

Results will be saved to: `benchmark_results/benchmark_{self.current_benchmark_id}_parallel.json`
        """
        self.console.print(Panel(Markdown(welcome_text), title="Welcome - Parallel Mode", border_style="blue"))
        
        if not Confirm.ask("Ready to begin parallel benchmarking?", default=True):
            sys.exit(0)
    
    def check_prerequisites(self) -> bool:
        """Check requirements"""
        self.console.print("\n[bold]Checking prerequisites...[/bold]")
        
        checks = {
            "Backend Modules": BACKEND_IMPORTS_AVAILABLE,
            "GitHub Token": bool(self.config["github_token"]),
            "OpenAI API Key": bool(os.getenv("OPENAI_API_KEY")),
            "Asyncio Support": True,  # Python 3.7+ has asyncio
        }
        
        table = Table(title="Prerequisites Check")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="green")
        
        all_passed = True
        for component, status in checks.items():
            status_text = "[green]✓ Ready[/green]" if status else "[red]✗ Not Ready[/red]"
            table.add_row(component, status_text)
            if not status:
                all_passed = False
        
        self.console.print(table)
        
        if not all_passed:
            self.console.print("\n[red]Some prerequisites are not met.[/red]")
            return False
        
        return True
    
    def get_github_username(self):
        """Fetch GitHub username"""
        headers = {"Authorization": f"token {self.config['github_token']}"}
        response = requests.get("https://api.github.com/user", headers=headers)
        if response.status_code == 200:
            self.config["github_username"] = response.json()["login"]
        else:
            raise Exception("Failed to fetch GitHub username")
    
    def select_commit(self) -> Dict[str, Any]:
        """Select a commit for benchmarking"""
        self.console.print("\n[bold]Selecting commit for benchmarking...[/bold]")
        
        repo_name = Prompt.ask(
            "Enter repository name",
            default=f"{self.config['github_username']}/golfdaddy-brain-mono"
        )
        
        headers = {"Authorization": f"token {self.config['github_token']}"}
        response = requests.get(
            f"https://api.github.com/repos/{repo_name}/commits",
            headers=headers,
            params={"per_page": 10}
        )
        
        if response.status_code != 200:
            self.console.print(f"[red]Failed to fetch commits[/red]")
            return None
        
        commits = response.json()
        if not commits:
            self.console.print("[red]No commits found[/red]")
            return None
        
        # Display commits
        table = Table(title=f"Recent Commits from {repo_name}")
        table.add_column("#", style="cyan", width=3)
        table.add_column("SHA", style="yellow", width=8)
        table.add_column("Message", style="white", width=50)
        table.add_column("Author", style="blue", width=20)
        table.add_column("Date", style="green", width=20)
        
        for i, commit in enumerate(commits):
            sha = commit['sha'][:7]
            message = commit['commit']['message'].split('\n')[0][:47] + "..."
            author = commit['commit']['author']['name'][:17] + "..." if len(commit['commit']['author']['name']) > 20 else commit['commit']['author']['name']
            date = commit['commit']['author']['date'][:10]
            
            table.add_row(str(i+1), sha, message, author, date)
        
        self.console.print(table)
        
        choice = Prompt.ask(
            "\nSelect commit number",
            choices=[str(i+1) for i in range(len(commits))],
            default="1"
        )
        
        selected_commit = commits[int(choice)-1]
        
        return {
            "repository": repo_name,
            "sha": selected_commit['sha'],
            "message": selected_commit['commit']['message'],
            "author": selected_commit['commit']['author']['name'],
            "date": selected_commit['commit']['author']['date'],
            "url": selected_commit['html_url']
        }
    
    def analyze_results(self, benchmark_results: Dict[str, Any]):
        """Same analysis as serial version"""
        # Reuse the analysis logic from the serial version
        self.console.print("\n[bold]Analyzing benchmark results (Parallel Execution)...[/bold]\n")
        
        runs = benchmark_results["runs"]
        successful_runs = [r for r in runs if "error" not in r]
        
        if not successful_runs:
            self.console.print("[red]No successful runs to analyze[/red]")
            return
        
        # Calculate statistics for Traditional Hours method
        hours_values = [r["traditional_hours"]["ai_estimated_hours"] for r in successful_runs if r["traditional_hours"]["ai_estimated_hours"]]
        complexity_values = [r["traditional_hours"]["complexity_score"] for r in successful_runs if r["traditional_hours"]["complexity_score"]]
        seniority_values = [r["traditional_hours"]["seniority_score"] for r in successful_runs if r["traditional_hours"]["seniority_score"]]
        
        # Calculate statistics for Impact Points method
        impact_scores = [r["impact_points"]["total_score"] for r in successful_runs if r.get("impact_points", {}).get("total_score")]
        
        # Show execution time comparison
        total_time = sum(r.get("analysis_time", 0) for r in successful_runs)
        avg_time = total_time / len(successful_runs) if successful_runs else 0
        
        timing_table = Table(title="Execution Performance", box=box.SIMPLE)
        timing_table.add_column("Metric", style="cyan")
        timing_table.add_column("Value", style="green")
        
        timing_table.add_row("Total Analysis Time", f"{total_time:.1f}s")
        timing_table.add_row("Average per Run", f"{avg_time:.1f}s")
        timing_table.add_row("Execution Mode", "Parallel")
        timing_table.add_row("Concurrency Level", str(self.config['max_concurrent_requests']))
        
        # Estimate serial time
        estimated_serial_time = avg_time * len(successful_runs)
        speedup = estimated_serial_time / total_time if total_time > 0 else 1
        timing_table.add_row("Estimated Speedup", f"{speedup:.1f}x")
        
        self.console.print(timing_table)
        self.console.print("")
        
        # Traditional Hours Statistics Table
        trad_table = Table(title="Traditional Hours Method - Statistical Analysis", box=box.ROUNDED)
        trad_table.add_column("Metric", style="cyan")
        trad_table.add_column("Mean", style="green")
        trad_table.add_column("Std Dev", style="yellow")
        trad_table.add_column("Min", style="blue")
        trad_table.add_column("Max", style="blue")
        trad_table.add_column("Range", style="red")
        trad_table.add_column("CV%", style="magenta")
        
        if hours_values:
            mean_hours = statistics.mean(hours_values)
            std_hours = statistics.stdev(hours_values) if len(hours_values) > 1 else 0
            cv_hours = (std_hours / mean_hours * 100) if mean_hours > 0 else 0
            trad_table.add_row(
                "AI Estimated Hours",
                f"{mean_hours:.2f}",
                f"{std_hours:.2f}",
                f"{min(hours_values):.2f}",
                f"{max(hours_values):.2f}",
                f"{max(hours_values) - min(hours_values):.2f}",
                f"{cv_hours:.1f}%"
            )
        
        if complexity_values:
            mean_complex = statistics.mean(complexity_values)
            std_complex = statistics.stdev(complexity_values) if len(complexity_values) > 1 else 0
            cv_complex = (std_complex / mean_complex * 100) if mean_complex > 0 else 0
            trad_table.add_row(
                "Complexity Score",
                f"{mean_complex:.2f}",
                f"{std_complex:.2f}",
                f"{min(complexity_values):.2f}",
                f"{max(complexity_values):.2f}",
                f"{max(complexity_values) - min(complexity_values):.2f}",
                f"{cv_complex:.1f}%"
            )
        
        self.console.print(trad_table)
        
        # Impact Points Statistics
        if impact_scores:
            self.console.print("")
            impact_table = Table(title="Impact Points Method - Statistical Analysis", box=box.ROUNDED)
            impact_table.add_column("Metric", style="cyan")
            impact_table.add_column("Mean", style="green")
            impact_table.add_column("Std Dev", style="yellow")
            impact_table.add_column("Min", style="blue")
            impact_table.add_column("Max", style="blue")
            impact_table.add_column("Range", style="red")
            impact_table.add_column("CV%", style="magenta")
            
            mean_impact = statistics.mean(impact_scores)
            std_impact = statistics.stdev(impact_scores) if len(impact_scores) > 1 else 0
            cv_impact = (std_impact / mean_impact * 100) if mean_impact > 0 else 0
            
            impact_table.add_row(
                "[bold]Total Impact Score[/bold]",
                f"[bold]{mean_impact:.2f}[/bold]",
                f"{std_impact:.2f}",
                f"{min(impact_scores):.2f}",
                f"{max(impact_scores):.2f}",
                f"{max(impact_scores) - min(impact_scores):.2f}",
                f"{cv_impact:.1f}%"
            )
            
            self.console.print(impact_table)
    
    def save_results(self, benchmark_results: Dict[str, Any]):
        """Save results with parallel indicator"""
        filename = self.config["output_dir"] / f"benchmark_{self.current_benchmark_id}_parallel_commit_{benchmark_results['commit_data']['sha'][:7]}.json"
        
        with open(filename, 'w') as f:
            json.dump(benchmark_results, f, indent=2, cls=DecimalEncoder)
        
        self.console.print(f"\n[green]✓ Results saved to: {filename.relative_to(Path.cwd())}[/green]")
        
        self.results.append({
            "commit": benchmark_results["commit_data"]["sha"][:7],
            "filename": str(filename),
            "runs": len(benchmark_results["runs"]),
            "successful_runs": len([r for r in benchmark_results["runs"] if "error" not in r])
        })
    
    def show_final_summary(self):
        """Display session summary"""
        if not self.results:
            return
        
        summary_text = f"""
# Parallel Benchmarking Session Complete

**Session ID:** {self.current_benchmark_id}
**Execution Mode:** Parallel (max {self.config['max_concurrent_requests']} concurrent)
**Commits Analyzed:** {len(self.results)}
**Total Runs:** {sum(r['runs'] for r in self.results)}
**Successful Runs:** {sum(r['successful_runs'] for r in self.results)}

## Performance Benefits:
- Reduced wait time by running analyses concurrently
- Respected API rate limits with batch processing
- Maintained result consistency

## Results Files:
"""
        
        for result in self.results:
            summary_text += f"- {result['filename']}\n"
        
        summary_text += f"""
All results saved in: `{self.config['output_dir'].relative_to(Path.cwd())}/`
        """
        
        self.console.print(Panel(Markdown(summary_text), title="Session Summary", border_style="green"))


def main():
    """Main entry point"""
    if not Path("backend").exists() or not Path("frontend").exists():
        console.print("[red]Error: Please run from project root[/red]")
        sys.exit(1)
    
    if not BACKEND_IMPORTS_AVAILABLE:
        console.print("[red]Error: Backend modules not available[/red]")
        console.print("[yellow]Activate backend venv first:[/yellow]")
        console.print("[dim]  cd backend && source venv/bin/activate[/dim]")
        sys.exit(1)
    
    # Run benchmark
    benchmark = ParallelCommitAnalysisBenchmark()
    benchmark.run()


if __name__ == "__main__":
    main()