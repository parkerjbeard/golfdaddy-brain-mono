#!/usr/bin/env python3
"""
GolfDaddy Brain Commit Analysis Benchmarking Tool
================================================
This script benchmarks the consistency of AI commit analysis by running
the same commit through the model multiple times and analyzing variance.

Features:
- Runs each commit analysis 10 times
- Calculates statistical metrics (mean, std dev, variance)
- Saves detailed results to JSON file
- Interactive commit selection
- Beautiful Rich terminal UI
"""

import os
import sys
import time
import json
import subprocess
import requests
from datetime import datetime, timedelta
import statistics
from pathlib import Path
from typing import Dict, Any, List, Tuple
import webbrowser
from decimal import Decimal
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.markdown import Markdown
from rich import box
from rich.live import Live
from rich.layout import Layout
import git
from dotenv import load_dotenv

# Custom JSON encoder to handle Decimal types
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

# Initialize Rich console for beautiful output
console = Console()

# Load environment variables from backend/.env
backend_env_path = Path(__file__).parent.parent / "backend" / ".env"
if backend_env_path.exists():
    load_dotenv(backend_env_path)

# Add backend to Python path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# Try to import backend modules
BACKEND_IMPORTS_AVAILABLE = False
try:
    from app.config.database import get_supabase_client
    from app.services.commit_analysis_service import CommitAnalysisService
    import asyncio
    BACKEND_IMPORTS_AVAILABLE = True
except ImportError as e:
    console.print(f"[yellow]Warning: Could not import backend modules: {e}[/yellow]")
    console.print("[dim]Benchmarking requires backend modules to be available[/dim]")

# Configuration
BENCHMARK_CONFIG = {
    "runs_per_commit": 10,
    "output_dir": Path(__file__).parent.parent / "benchmark_results",
    "github_token": os.getenv("GITHUB_TOKEN"),
    "github_username": None,  # Will be fetched
    "test_repo": "golfdaddy-brain-mono",  # Default repo
}

class CommitAnalysisBenchmark:
    """Main benchmarking orchestrator class"""
    
    def __init__(self):
        self.console = console
        self.config = BENCHMARK_CONFIG
        self.results = []
        self.current_benchmark_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create output directory
        self.config["output_dir"].mkdir(exist_ok=True)
        
    def run(self):
        """Main benchmark execution flow"""
        try:
            self.show_welcome()
            
            if not self.check_prerequisites():
                return
            
            self.get_github_username()
            
            # Main benchmarking loop
            while True:
                commit_data = self.select_commit()
                if not commit_data:
                    break
                    
                benchmark_results = self.benchmark_commit(commit_data)
                self.analyze_results(benchmark_results)
                self.save_results(benchmark_results)
                
                if not Confirm.ask("\n[bold yellow]Would you like to benchmark another commit?[/bold yellow]", default=True):
                    break
            
            self.show_final_summary()
            
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Benchmark interrupted by user[/yellow]")
        except Exception as e:
            self.console.print(f"\n[red]Benchmark error: {str(e)}[/red]")
    
    def show_welcome(self):
        """Display welcome message and benchmark overview"""
        welcome_text = f"""
# Commit Analysis Benchmarking Tool

This tool tests the consistency of AI commit analysis by running the same commit
through the model multiple times.

**Configuration:**
- Runs per commit: {self.config['runs_per_commit']}
- Output directory: benchmark_results/
- Scoring methods: Traditional Hours + Impact Points v2.0

**What we'll measure:**
- Score consistency across runs
- Statistical variance and standard deviation
- Min/max ranges for each metric
- Reasoning consistency

**Impact Points v2.0 Formula:**
Impact = (Business Value × 2) + (Technical Complexity × 1.5) + Quality Points - Risk Penalty

Results will be saved to: `benchmark_results/benchmark_{self.current_benchmark_id}.json`
        """
        self.console.print(Panel(Markdown(welcome_text), title="Welcome", border_style="blue"))
        
        if not Confirm.ask("Ready to begin benchmarking?", default=True):
            sys.exit(0)
    
    def check_prerequisites(self) -> bool:
        """Check if all requirements are met"""
        self.console.print("\n[bold]Checking prerequisites...[/bold]")
        
        checks = {
            "Backend Modules": BACKEND_IMPORTS_AVAILABLE,
            "GitHub Token": bool(self.config["github_token"]),
            "OpenAI API Key": bool(os.getenv("OPENAI_API_KEY")),
        }
        
        # Display results
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
            self.console.print("\n[red]Some prerequisites are not met. Please check your setup.[/red]")
            if not BACKEND_IMPORTS_AVAILABLE:
                self.console.print("[yellow]Run from backend venv: cd backend && source venv/bin/activate[/yellow]")
            return False
        
        return True
    
    def get_github_username(self):
        """Fetch GitHub username using token"""
        headers = {"Authorization": f"token {self.config['github_token']}"}
        response = requests.get("https://api.github.com/user", headers=headers)
        if response.status_code == 200:
            self.config["github_username"] = response.json()["login"]
        else:
            raise Exception("Failed to fetch GitHub username")
    
    def select_commit(self) -> Dict[str, Any]:
        """Select a commit for benchmarking"""
        self.console.print("\n[bold]Selecting commit for benchmarking...[/bold]")
        
        # Ask for repository
        repo_name = Prompt.ask(
            "Enter repository name",
            default=f"{self.config['github_username']}/{self.config['test_repo']}"
        )
        
        # Fetch commits
        headers = {"Authorization": f"token {self.config['github_token']}"}
        response = requests.get(
            f"https://api.github.com/repos/{repo_name}/commits",
            headers=headers,
            params={"per_page": 10}
        )
        
        if response.status_code != 200:
            self.console.print(f"[red]Failed to fetch commits from {repo_name}[/red]")
            return None
        
        commits = response.json()
        if not commits:
            self.console.print("[red]No commits found in repository[/red]")
            return None
        
        # Display commits table
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
        
        # Select commit
        choice = Prompt.ask(
            "\nSelect commit number to benchmark",
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
    
    def benchmark_commit(self, commit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run multiple analyses on the same commit"""
        self.console.print(f"\n[bold]Benchmarking commit {commit_data['sha'][:7]}...[/bold]")
        self.console.print(f"Message: {commit_data['message'].split(chr(10))[0]}")
        self.console.print(f"This will run {self.config['runs_per_commit']} analyses...\n")
        
        results = {
            "commit_data": commit_data,
            "runs": [],
            "timestamp": datetime.now().isoformat(),
            "config": {
                "runs": self.config["runs_per_commit"],
                "model": os.getenv("COMMIT_ANALYSIS_MODEL", "gpt-4"),
            }
        }
        
        # Initialize services
        db = get_supabase_client()
        commit_service = CommitAnalysisService(db)
        
        # Progress tracking
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console
        ) as progress:
            
            task = progress.add_task(
                f"Running {self.config['runs_per_commit']} analyses...", 
                total=self.config['runs_per_commit']
            )
            
            for run_idx in range(self.config['runs_per_commit']):
                progress.update(task, description=f"Analysis run {run_idx + 1}/{self.config['runs_per_commit']}...")
                
                try:
                    # Run the analysis
                    start_time = time.time()
                    
                    # Prepare commit data for analysis
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
                    
                    # Run async analysis
                    analyzed_commit = asyncio.run(
                        commit_service.analyze_commit(
                            commit_hash=commit_data["sha"],
                            commit_data=analysis_data,
                            fetch_diff=True
                        )
                    )
                    
                    analysis_time = time.time() - start_time
                    
                    if analyzed_commit:
                        # Extract scores
                        run_result = {
                            "run_index": run_idx + 1,
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
                        
                        # Parse comprehensive analysis data from ai_analysis_notes
                        if analyzed_commit.ai_analysis_notes:
                            try:
                                analysis_data = json.loads(analyzed_commit.ai_analysis_notes)
                                
                                # Update traditional hours with new anchor fields if available
                                if analysis_data.get('total_lines') is not None:
                                    run_result["traditional_hours"].update({
                                        "total_lines": analysis_data.get('total_lines'),
                                        "total_files": analysis_data.get('total_files'),
                                        "initial_anchor": analysis_data.get('initial_anchor'),
                                        "final_anchor": analysis_data.get('final_anchor'),
                                        "base_hours": analysis_data.get('base_hours'),
                                        "major_change_checks": analysis_data.get('major_change_checks', []),
                                        "major_change_count": analysis_data.get('major_change_count', 0),
                                        "file_count_override": analysis_data.get('file_count_override', False),
                                        "simplicity_reduction_checks": analysis_data.get('simplicity_reduction_checks', []),
                                        "complexity_cap_applied": analysis_data.get('complexity_cap_applied', 'none'),
                                        "multipliers_applied": analysis_data.get('multipliers_applied', [])
                                    })
                                
                                # Extract impact scoring - check for v2.0 structure
                                if 'impact_classification' in analysis_data:
                                    # New v2.0 structure
                                    run_result["impact_points"] = {
                                        "business_value": analysis_data.get('impact_business_value', 0),
                                        "technical_complexity": analysis_data.get('impact_technical_complexity', 0),
                                        "code_quality_points": analysis_data.get('impact_code_quality_points', 0),
                                        "risk_penalty": analysis_data.get('impact_risk_penalty', 0),
                                        "total_score": analysis_data.get('impact_score', 0),
                                        "classification": analysis_data.get('impact_classification', {}),
                                        "calculation_breakdown": analysis_data.get('impact_calculation_breakdown', ''),
                                        "reasoning": {
                                            "business_value": analysis_data.get('impact_business_value_reasoning', ''),
                                            "technical_complexity": analysis_data.get('impact_technical_complexity_reasoning', ''),
                                            "code_quality": analysis_data.get('impact_code_quality_checklist', {}),
                                            "risk": analysis_data.get('impact_risk_reasoning', ''),
                                        }
                                    }
                                else:
                                    # Old structure (backward compatibility)
                                    run_result["impact_points"] = {
                                        "business_value": analysis_data.get('impact_business_value', 0),
                                        "technical_complexity": analysis_data.get('impact_technical_complexity', 0),
                                        "code_quality": analysis_data.get('impact_code_quality', 1.0),
                                        "risk_factor": analysis_data.get('impact_risk_factor', 1.0),
                                        "total_score": analysis_data.get('impact_score', 0),
                                        "reasoning": {
                                            "business_value": analysis_data.get('impact_business_value_reasoning', ''),
                                            "technical_complexity": analysis_data.get('impact_technical_complexity_reasoning', ''),
                                            "code_quality": analysis_data.get('impact_code_quality_reasoning', ''),
                                            "risk_factor": analysis_data.get('impact_risk_factor_reasoning', ''),
                                        }
                                    }
                            except Exception as e:
                                self.console.print(f"[yellow]Warning: Could not parse analysis data: {e}[/yellow]")
                                # Fallback to basic impact data if available
                                run_result["impact_points"] = {
                                    "business_value": None,
                                    "technical_complexity": None,
                                    "code_quality": 1.0,
                                    "risk_factor": 1.0,
                                    "total_score": None,
                                    "reasoning": {
                                        "business_value": None,
                                        "technical_complexity": None,
                                        "code_quality": None,
                                        "risk_factor": None,
                                    }
                                }
                        
                        results["runs"].append(run_result)
                    else:
                        results["runs"].append({
                            "run_index": run_idx + 1,
                            "error": "Analysis failed"
                        })
                    
                except Exception as e:
                    results["runs"].append({
                        "run_index": run_idx + 1,
                        "error": str(e)
                    })
                
                progress.update(task, advance=1)
                
                # Small delay between runs to avoid rate limiting
                if run_idx < self.config['runs_per_commit'] - 1:
                    time.sleep(2)
        
        return results
    
    def analyze_results(self, benchmark_results: Dict[str, Any]):
        """Analyze and display benchmark results"""
        self.console.print("\n[bold]Analyzing benchmark results...[/bold]\n")
        
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
        business_values = [r["impact_points"]["business_value"] for r in successful_runs if r.get("impact_points", {}).get("business_value")]
        technical_values = [r["impact_points"]["technical_complexity"] for r in successful_runs if r.get("impact_points", {}).get("technical_complexity")]
        
        # Handle both old (code_quality) and new (code_quality_points) field names
        quality_values = []
        risk_values = []
        for r in successful_runs:
            impact = r.get("impact_points", {})
            # Code quality - check both field names
            if "code_quality_points" in impact:
                quality_values.append(impact["code_quality_points"])
            elif "code_quality" in impact:
                quality_values.append(impact["code_quality"])
            
            # Risk - check both field names (risk_penalty vs risk_factor)
            if "risk_penalty" in impact:
                risk_values.append(impact["risk_penalty"])
            elif "risk_factor" in impact:
                risk_values.append(impact["risk_factor"])
        
        impact_scores = [r["impact_points"]["total_score"] for r in successful_runs if r.get("impact_points", {}).get("total_score")]
        
        # Traditional Hours Statistics Table
        trad_table = Table(title="Traditional Hours Method - Statistical Analysis", box=box.ROUNDED)
        trad_table.add_column("Metric", style="cyan")
        trad_table.add_column("Mean", style="green")
        trad_table.add_column("Std Dev", style="yellow")
        trad_table.add_column("Min", style="blue")
        trad_table.add_column("Max", style="blue")
        trad_table.add_column("Range", style="red")
        trad_table.add_column("CV%", style="magenta")
        
        # Add rows for traditional metrics
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
        
        if seniority_values:
            mean_senior = statistics.mean(seniority_values)
            std_senior = statistics.stdev(seniority_values) if len(seniority_values) > 1 else 0
            cv_senior = (std_senior / mean_senior * 100) if mean_senior > 0 else 0
            trad_table.add_row(
                "Seniority Score",
                f"{mean_senior:.2f}",
                f"{std_senior:.2f}",
                f"{min(seniority_values):.2f}",
                f"{max(seniority_values):.2f}",
                f"{max(seniority_values) - min(seniority_values):.2f}",
                f"{cv_senior:.1f}%"
            )
        
        self.console.print(trad_table)
        self.console.print("")
        
        # Impact Points Statistics Table
        impact_table = Table(title="Impact Points Method - Statistical Analysis", box=box.ROUNDED)
        impact_table.add_column("Metric", style="cyan")
        impact_table.add_column("Mean", style="green")
        impact_table.add_column("Std Dev", style="yellow")
        impact_table.add_column("Min", style="blue")
        impact_table.add_column("Max", style="blue")
        impact_table.add_column("Range", style="red")
        impact_table.add_column("CV%", style="magenta")
        
        # Add rows for impact metrics
        if business_values:
            mean_biz = statistics.mean(business_values)
            std_biz = statistics.stdev(business_values) if len(business_values) > 1 else 0
            cv_biz = (std_biz / mean_biz * 100) if mean_biz > 0 else 0
            impact_table.add_row(
                "Business Value",
                f"{mean_biz:.2f}",
                f"{std_biz:.2f}",
                f"{min(business_values):.2f}",
                f"{max(business_values):.2f}",
                f"{max(business_values) - min(business_values):.2f}",
                f"{cv_biz:.1f}%"
            )
        
        if technical_values:
            mean_tech = statistics.mean(technical_values)
            std_tech = statistics.stdev(technical_values) if len(technical_values) > 1 else 0
            cv_tech = (std_tech / mean_tech * 100) if mean_tech > 0 else 0
            impact_table.add_row(
                "Technical Complexity",
                f"{mean_tech:.2f}",
                f"{std_tech:.2f}",
                f"{min(technical_values):.2f}",
                f"{max(technical_values):.2f}",
                f"{max(technical_values) - min(technical_values):.2f}",
                f"{cv_tech:.1f}%"
            )
        
        if quality_values:
            mean_quality = statistics.mean(quality_values)
            std_quality = statistics.stdev(quality_values) if len(quality_values) > 1 else 0
            cv_quality = (std_quality / mean_quality * 100) if mean_quality > 0 else 0
            impact_table.add_row(
                "Code Quality Points",
                f"{mean_quality:.2f}",
                f"{std_quality:.2f}",
                f"{min(quality_values):.2f}",
                f"{max(quality_values):.2f}",
                f"{max(quality_values) - min(quality_values):.2f}",
                f"{cv_quality:.1f}%"
            )
        
        if risk_values:
            mean_risk = statistics.mean(risk_values)
            std_risk = statistics.stdev(risk_values) if len(risk_values) > 1 else 0
            cv_risk = (std_risk / mean_risk * 100) if mean_risk > 0 else 0
            impact_table.add_row(
                "Risk Penalty",
                f"{mean_risk:.2f}",
                f"{std_risk:.2f}",
                f"{min(risk_values):.2f}",
                f"{max(risk_values):.2f}",
                f"{max(risk_values) - min(risk_values):.2f}",
                f"{cv_risk:.1f}%"
            )
        
        if impact_scores:
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
        
        # Risk Level Distribution
        risk_levels = [r["traditional_hours"]["risk_level"] for r in successful_runs if r["traditional_hours"].get("risk_level")]
        if risk_levels:
            risk_counts = {}
            for risk in risk_levels:
                risk_counts[risk] = risk_counts.get(risk, 0) + 1
            
            self.console.print("\n[bold]Risk Level Distribution:[/bold]")
            risk_table = Table(box=box.SIMPLE)
            risk_table.add_column("Risk Level", style="cyan")
            risk_table.add_column("Count", style="green")
            risk_table.add_column("Percentage", style="yellow")
            
            for risk, count in sorted(risk_counts.items()):
                percentage = (count / len(risk_levels)) * 100
                risk_color = {"low": "green", "medium": "yellow", "high": "red"}.get(risk.lower(), "white")
                risk_table.add_row(
                    f"[{risk_color}]{risk.upper()}[/{risk_color}]",
                    str(count),
                    f"{percentage:.1f}%"
                )
            
            self.console.print(risk_table)
        
        # Analysis Summary
        self.console.print("\n[bold]Consistency Analysis:[/bold]")
        summary = Table(box=box.SIMPLE)
        summary.add_column("Method", style="cyan")
        summary.add_column("Consistency Rating", style="green")
        summary.add_column("Notes", style="dim")
        
        # Rate traditional hours consistency
        if hours_values and len(hours_values) > 1:
            hours_cv = (statistics.stdev(hours_values) / statistics.mean(hours_values) * 100)
            if hours_cv < 10:
                rating = "Excellent"
                color = "green"
            elif hours_cv < 20:
                rating = "Good"
                color = "yellow"
            else:
                rating = "Fair"
                color = "red"
            
            summary.add_row(
                "Traditional Hours",
                f"[{color}]{rating}[/{color}]",
                f"CV: {hours_cv:.1f}%"
            )
        
        # Rate impact points consistency
        if impact_scores and len(impact_scores) > 1:
            impact_cv = (statistics.stdev(impact_scores) / statistics.mean(impact_scores) * 100)
            if impact_cv < 10:
                rating = "Excellent"
                color = "green"
            elif impact_cv < 20:
                rating = "Good"
                color = "yellow"
            else:
                rating = "Fair"
                color = "red"
            
            summary.add_row(
                "Impact Points",
                f"[{color}]{rating}[/{color}]",
                f"CV: {impact_cv:.1f}%"
            )
        
        self.console.print(summary)
        
        # Show individual run details
        if Confirm.ask("\n[bold]Show detailed run-by-run results?[/bold]", default=False):
            self.show_detailed_runs(benchmark_results)
    
    def show_detailed_runs(self, benchmark_results: Dict[str, Any]):
        """Show detailed results for each run"""
        for run in benchmark_results["runs"]:
            if "error" in run:
                self.console.print(f"\n[red]Run {run['run_index']}: ERROR - {run['error']}[/red]")
                continue
            
            self.console.print(f"\n[bold]Run {run['run_index']}:[/bold]")
            
            # Create a small table for this run
            run_table = Table(box=box.SIMPLE)
            run_table.add_column("Metric", style="cyan")
            run_table.add_column("Traditional Hours", style="green")
            run_table.add_column("Impact Points", style="yellow")
            
            trad = run["traditional_hours"]
            impact = run.get("impact_points", {})
            
            run_table.add_row(
                "Primary Score",
                f"{trad['ai_estimated_hours']:.1f} hours",
                f"{impact.get('total_score', 0):.1f} points"
            )
            
            # Add business value row
            run_table.add_row(
                "Business Value",
                "-",
                f"{impact.get('business_value', 0)}/10"
            )
            
            run_table.add_row(
                "Complexity",
                f"{trad['complexity_score']}/10",
                f"{impact.get('technical_complexity', 0)}/10"
            )
            
            # Handle both old and new field names for quality and risk
            quality_val = impact.get('code_quality_points', impact.get('code_quality', 0))
            risk_val = impact.get('risk_penalty', impact.get('risk_factor', 0))
            
            run_table.add_row(
                "Quality Assessment",
                f"Seniority: {trad.get('seniority_score', 0)}/10",
                f"Quality Points: {quality_val}" + (" pts" if "code_quality_points" in impact else "x")
            )
            
            if trad.get('risk_level') or risk_val:
                run_table.add_row(
                    "Risk Assessment",
                    trad.get('risk_level', 'N/A').upper(),
                    f"Penalty: -{risk_val}" if "risk_penalty" in impact else f"{risk_val:.2f}x"
                )
            
            # Add calculation breakdown for impact points if available
            if impact.get('total_score') and "code_quality_points" in impact:
                bv = impact.get('business_value', 0)
                tc = impact.get('technical_complexity', 0)
                cq = impact.get('code_quality_points', 0)
                rp = impact.get('risk_penalty', 0)
                calc = f"({bv}×2) + ({tc}×1.5) + {cq} - {rp} = {impact['total_score']:.1f}"
                run_table.add_row(
                    "Impact Calculation",
                    "-",
                    calc
                )
            
            self.console.print(run_table)
    
    def save_results(self, benchmark_results: Dict[str, Any]):
        """Save results to JSON file"""
        filename = self.config["output_dir"] / f"benchmark_{self.current_benchmark_id}_commit_{benchmark_results['commit_data']['sha'][:7]}.json"
        
        with open(filename, 'w') as f:
            json.dump(benchmark_results, f, indent=2, cls=DecimalEncoder)
        
        self.console.print(f"\n[green]✓ Results saved to: {filename.relative_to(Path.cwd())}[/green]")
        
        # Update overall results tracking
        self.results.append({
            "commit": benchmark_results["commit_data"]["sha"][:7],
            "filename": str(filename),
            "runs": len(benchmark_results["runs"]),
            "successful_runs": len([r for r in benchmark_results["runs"] if "error" not in r])
        })
    
    def show_final_summary(self):
        """Display final summary of all benchmarks"""
        if not self.results:
            return
        
        summary_text = f"""
# Benchmarking Session Complete

**Session ID:** {self.current_benchmark_id}
**Commits Analyzed:** {len(self.results)}
**Total Runs:** {sum(r['runs'] for r in self.results)}
**Successful Runs:** {sum(r['successful_runs'] for r in self.results)}

## Results Files:
"""
        
        for result in self.results:
            summary_text += f"- {result['filename']}\n"
        
        summary_text += f"""
## Next Steps:
1. Review the JSON files for detailed analysis
2. Compare consistency across different types of commits
3. Use insights to tune AI prompts if needed
4. Share results with the team for discussion

All results saved in: `{self.config['output_dir'].relative_to(Path.cwd())}/`
        """
        
        self.console.print(Panel(Markdown(summary_text), title="Session Summary", border_style="green"))


def main():
    """Main entry point"""
    # Check if running from correct directory
    if not Path("backend").exists() or not Path("frontend").exists():
        console.print("[red]Error: Please run this script from the project root directory[/red]")
        sys.exit(1)
    
    # Check backend virtual environment
    if not BACKEND_IMPORTS_AVAILABLE:
        console.print("[red]Error: Backend modules not available[/red]")
        console.print("[yellow]Please activate the backend virtual environment:[/yellow]")
        console.print("[dim]  cd backend && source venv/bin/activate[/dim]")
        console.print("[dim]  cd .. && python scripts/benchmark_commit_analysis.py[/dim]")
        sys.exit(1)
    
    # Install required packages if needed
    try:
        import rich
        import git
    except ImportError:
        console.print("[yellow]Installing required packages...[/yellow]")
        subprocess.run([sys.executable, "-m", "pip", "install", "rich", "gitpython", "requests", "python-dotenv"])
        console.print("[green]✓ Packages installed[/green]")
        console.print("Please run the script again")
        sys.exit(0)
    
    # Run benchmark
    benchmark = CommitAnalysisBenchmark()
    benchmark.run()


if __name__ == "__main__":
    main()