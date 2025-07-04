#!/usr/bin/env python3
"""
GolfDaddy Brain Comprehensive Demo Script
=========================================
This script demonstrates all features of the GolfDaddy Brain system including:
- GitHub commit analysis and productivity tracking
- Auto documentation generation and approval
- Semantic search and documentation management
- Dashboard analytics and reporting

Requirements:
- Python 3.8+
- All environment variables properly configured
- Docker services running
- GitHub personal access token with repo permissions
"""

import os
import sys
import time
import json
import subprocess
import requests
from datetime import datetime, timedelta
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
import webbrowser
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.markdown import Markdown
from rich import box
import git
from dotenv import load_dotenv

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
    console.print("[dim]Some features may be limited[/dim]")

# Configuration
DEMO_CONFIG = {
    "api_base_url": os.getenv("VITE_API_URL", "http://localhost:8000"),
    "frontend_url": os.getenv("FRONTEND_URL", "http://localhost:8080"),
    "github_token": os.getenv("GITHUB_TOKEN"),
    "github_username": None,  # Will be fetched
    "demo_repo_name": "golfdaddy-brain-mono",  # Use existing repo
    "demo_docs_repo_name": "golfdaddy-brain-mono",  # Use same repo for docs demo
    "test_user_email": os.getenv("DEMO_USER_EMAIL", "testadmin1@example.com"),
    "test_user_password": os.getenv("DEMO_USER_PASSWORD", "password123"),
}

class GolfDaddyDemo:
    """Main demo orchestrator class"""
    
    def __init__(self):
        self.console = console
        self.config = DEMO_CONFIG
        self.session = requests.Session()
        self.auth_token = None
        self.demo_repos = {}
        self.created_resources = []
        
    def run(self):
        """Main demo execution flow"""
        try:
            self.show_welcome()
            
            if not self.check_prerequisites():
                return
            
            self.setup_demo_environment()
            
            # Main demo sections
            self.demo_github_analysis()
            self.demo_auto_documentation()
            self.demo_semantic_search()
            self.demo_analytics_dashboard()
            
            self.show_summary()
            
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Demo interrupted by user[/yellow]")
        except Exception as e:
            self.console.print(f"\n[red]Demo error: {str(e)}[/red]")
        finally:
            if Confirm.ask("Clean up demo resources?", default=True):
                self.cleanup()
    
    def show_welcome(self):
        """Display welcome message and demo overview"""
        welcome_text = """
# GolfDaddy Brain Demo

Welcome to the comprehensive demonstration of GolfDaddy Brain!

This demo will showcase:
1. **GitHub Analysis** - Automatic commit tracking and effort estimation
2. **Auto Documentation** - AI-powered documentation generation
3. **Semantic Search** - Find and analyze documentation
4. **Analytics Dashboard** - Team productivity insights

The demo will create temporary repositories and data for demonstration purposes.
        """
        self.console.print(Panel(Markdown(welcome_text), title="Welcome", border_style="blue"))
        
        if not Confirm.ask("Ready to begin?", default=True):
            sys.exit(0)
    
    def check_prerequisites(self) -> bool:
        """Check if all requirements are met"""
        self.console.print("\n[bold]Checking prerequisites...[/bold]")
        
        checks = {
            "API Server": self.check_api_health(),
            "Frontend": self.check_frontend(),
            "GitHub Token": bool(self.config["github_token"]),
            "OpenAI API Key": bool(os.getenv("OPENAI_API_KEY")),
            "Docker Services": self.check_docker_services(),
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
            return False
        
        return True
    
    def check_api_health(self) -> bool:
        """Check if API server is running"""
        try:
            response = requests.get(f"{self.config['api_base_url']}/health")
            return response.status_code == 200
        except:
            return False
    
    def check_frontend(self) -> bool:
        """Check if frontend is accessible"""
        try:
            response = requests.get(self.config['frontend_url'])
            return response.status_code == 200
        except:
            return False
    
    def check_docker_services(self) -> bool:
        """Check if Docker services are running"""
        try:
            result = subprocess.run(
                ["docker-compose", "ps"], 
                capture_output=True, 
                text=True,
                cwd=Path(__file__).parent.parent
            )
            return result.returncode == 0
        except:
            return False
    
    def setup_demo_environment(self):
        """Set up demo user and repositories"""
        self.console.print("\n[bold]Setting up demo environment...[/bold]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            # Create demo user
            task = progress.add_task("Creating demo user...", total=1)
            self.create_demo_user()
            progress.update(task, completed=1)
            
            # Authenticate
            task = progress.add_task("Authenticating...", total=1)
            self.authenticate()
            progress.update(task, completed=1)
            
            # Get GitHub username
            task = progress.add_task("Fetching GitHub info...", total=1)
            self.get_github_username()
            progress.update(task, completed=1)
            
            # Create demo repositories
            task = progress.add_task("Creating demo repositories...", total=1)
            self.create_demo_repositories()
            progress.update(task, completed=1)
    
    def create_demo_user(self):
        """Create or verify demo user exists"""
        # Check if user exists
        try:
            response = self.session.post(
                f"{self.config['api_base_url']}/api/v1/auth/login",
                json={
                    "email": self.config["test_user_email"],
                    "password": self.config["test_user_password"]
                }
            )
            if response.status_code == 200:
                return  # User already exists
        except:
            pass
        
        # Create new user
        # Note: You'll need to implement a registration endpoint or use Supabase directly
        self.console.print("[yellow]Demo user creation skipped - using existing user[/yellow]")
    
    def authenticate(self):
        """Authenticate and get token"""
        # Try the correct auth endpoint
        response = self.session.post(
            f"{self.config['api_base_url']}/auth/login",
            json={
                "email": self.config["test_user_email"],
                "password": self.config["test_user_password"]
            }
        )
        if response.status_code == 200:
            data = response.json()
            self.auth_token = data.get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
        else:
            # If login fails, continue without auth - many demo features will still work
            self.console.print("[yellow]⚠ Authentication skipped - continuing without login[/yellow]")
            self.console.print("[dim]  Some features may be limited[/dim]")
            # Use API key instead
            self.session.headers.update({"X-API-Key": "dev-api-key"})
    
    def get_github_username(self):
        """Fetch GitHub username using token"""
        headers = {"Authorization": f"token {self.config['github_token']}"}
        response = requests.get("https://api.github.com/user", headers=headers)
        if response.status_code == 200:
            self.config["github_username"] = response.json()["login"]
        else:
            raise Exception("Failed to fetch GitHub username")
    
    def create_demo_repositories(self):
        """Create demo repositories on GitHub"""
        headers = {"Authorization": f"token {self.config['github_token']}"}
        
        # Create main demo repo
        repo_data = {
            "name": self.config["demo_repo_name"],
            "description": "Demo repository for GolfDaddy Brain",
            "private": False,
            "auto_init": True
        }
        
        response = requests.post(
            "https://api.github.com/user/repos",
            headers=headers,
            json=repo_data
        )
        
        if response.status_code == 201:
            self.demo_repos["main"] = response.json()
            self.created_resources.append(("github_repo", self.config["demo_repo_name"]))
        elif response.status_code == 422:
            # Repo already exists
            response = requests.get(
                f"https://api.github.com/repos/{self.config['github_username']}/{self.config['demo_repo_name']}",
                headers=headers
            )
            self.demo_repos["main"] = response.json()
        
        # Create docs repo
        repo_data["name"] = self.config["demo_docs_repo_name"]
        repo_data["description"] = "Demo documentation repository"
        
        response = requests.post(
            "https://api.github.com/user/repos",
            headers=headers,
            json=repo_data
        )
        
        if response.status_code == 201:
            self.demo_repos["docs"] = response.json()
            self.created_resources.append(("github_repo", self.config["demo_docs_repo_name"]))
        elif response.status_code == 422:
            # Repo already exists
            response = requests.get(
                f"https://api.github.com/repos/{self.config['github_username']}/{self.config['demo_docs_repo_name']}",
                headers=headers
            )
            self.demo_repos["docs"] = response.json()
    
    def demo_github_analysis(self):
        """Demonstrate GitHub commit analysis features"""
        self.console.print("\n[bold blue]=== GitHub Analysis Demo ===[/bold blue]\n")
        
        demo_text = """
This section demonstrates automatic commit analysis and developer productivity tracking.

We'll:
1. Fetch the latest commit from your repository
2. Analyze it using AI with TWO scoring methods:
   - Traditional Hours Estimation (time-based)
   - Impact Points System (value-based)
3. Compare both methods side-by-side
4. View the AI-generated insights
5. Check the productivity dashboard

Note: This uses your GitHub PAT to fetch commit data directly - no webhooks needed!

The Impact Points System is designed to be fair in the age of LLM-assisted programming,
focusing on business value delivered rather than time spent coding.
        """
        self.console.print(Panel(Markdown(demo_text), border_style="blue"))
        
        if not Confirm.ask("Continue with GitHub analysis demo?", default=True):
            return
        
        # Check if we can create repositories
        self.console.print("\n[bold]Step 1: Checking GitHub permissions...[/bold]")
        try:
            headers = {"Authorization": f"token {self.config['github_token']}"}
            response = requests.get("https://api.github.com/user", headers=headers)
            
            if response.status_code == 200:
                user_data = response.json()
                self.config['github_username'] = user_data.get('login')  # Store username
                self.console.print(f"[green]✓ Authenticated as: {user_data.get('login', 'Unknown')}[/green]")
            else:
                self.console.print(f"[red]✗ GitHub authentication failed: {response.status_code}[/red]")
                self.console.print("[yellow]Please check your GitHub token permissions[/yellow]")
                return
        except Exception as e:
            self.console.print(f"[red]✗ Error checking GitHub: {e}[/red]")
            return
        
        # Use existing repository
        self.console.print("\n[bold]Step 2: Using existing repository...[/bold]")
        try:
            headers = {"Authorization": f"token {self.config['github_token']}"}
            repo_name = f"{self.config['github_username']}/{self.config['demo_repo_name']}"
            response = requests.get(f"https://api.github.com/repos/{repo_name}", headers=headers)
            
            if response.status_code == 200:
                self.demo_repos["main"] = response.json()
                self.console.print(f"[green]✓ Found repository: {repo_name}[/green]")
            else:
                self.console.print(f"[red]✗ Repository not found: {repo_name}[/red]")
                self.console.print(f"[yellow]Status code: {response.status_code}[/yellow]")
                self.console.print("[yellow]Please check your GitHub token has 'repo' scope[/yellow]")
                return
        except Exception as e:
            self.console.print(f"[red]✗ Error fetching repository: {e}[/red]")
            return
        
        # Get commits from the repository
        self.console.print("\n[bold]Step 3: Fetching commits from repository...[/bold]")
        try:
            headers = {"Authorization": f"token {self.config['github_token']}"}
            repo_name = f"{self.config['github_username']}/{self.config['demo_repo_name']}"
            
            # Get multiple commits for analysis
            response = requests.get(
                f"https://api.github.com/repos/{repo_name}/commits",
                headers=headers,
                params={"per_page": 20}  # Get more commits for multiple analyses
            )
            
            if response.status_code == 200:
                all_commits = response.json()
                if all_commits:
                    self.console.print(f"[green]✓ Found {len(all_commits)} commits in repository[/green]")
                    
                    # Analyze commits one by one
                    commit_index = 0
                    while commit_index < len(all_commits):
                        commit = all_commits[commit_index]
                        commit_sha = commit['sha']
                        commit_message = commit['commit']['message']
                        author = commit['commit']['author']['name']
                        date = commit['commit']['author']['date']
                        
                        self.console.print(f"\n[bold]Analyzing commit {commit_index + 1} of {len(all_commits)}:[/bold]")
                        self.console.print(f"  SHA: {commit_sha[:7]}")
                        self.console.print(f"  Message: {commit_message.split('\\n')[0][:60]}...")
                        self.console.print(f"  Author: {author}")
                        self.console.print(f"  Date: {date}")
                        
                        # Analyze this commit
                        if not self._analyze_single_commit(commit_sha, commit_message, author, date):
                            return  # Exit if analysis fails
                        
                        # Ask if user wants to analyze another commit
                        commit_index += 1
                        if commit_index < len(all_commits):
                            self.console.print("\n" + "="*80 + "\n")
                            if Confirm.ask(f"[bold yellow]Would you like to analyze another commit? ({len(all_commits) - commit_index} more available)[/bold yellow]", default=True):
                                continue
                            else:
                                break
                        else:
                            self.console.print("\n[yellow]No more commits available to analyze.[/yellow]")
                            break
                    
                else:
                    self.console.print("[red]✗ No commits found in repository[/red]")
                    return
            else:
                self.console.print(f"[red]✗ Failed to fetch commits: {response.status_code}[/red]")
                return
        except Exception as e:
            self.console.print(f"[red]✗ Error fetching commits: {e}[/red]")
            return
        
        # Step 5: Show productivity dashboard
        self.console.print("\n[bold]Step 5: Viewing productivity dashboard...[/bold]")
        dashboard_url = f"{self.config['frontend_url']}/manager"
        self.console.print(f"\n[cyan]Open your browser to view the manager dashboard:[/cyan]")
        self.console.print(f"[bold]{dashboard_url}[/bold]")
        
        if Confirm.ask("Open dashboard in browser?", default=True):
            webbrowser.open(dashboard_url)
            self.console.print("[green]✓ Dashboard opened in browser[/green]")
            time.sleep(3)
        
        self.console.print("\n[green]✅ GitHub analysis demo complete![/green]")
    
    def _analyze_single_commit(self, commit_sha: str, commit_message: str, author: str, date: str) -> bool:
        """Analyze a single commit and display results. Returns True if successful."""
        self.console.print("\n[bold]Step 4: Analyzing commit with AI...[/bold]")
        
        # Check if backend imports are available
        if not BACKEND_IMPORTS_AVAILABLE:
            self.console.print("[red]✗ Backend modules not available[/red]")
            self.console.print("[yellow]Please ensure you're running from the backend virtual environment[/yellow]")
            self.console.print("[dim]  cd backend && source venv/bin/activate[/dim]")
            return False
        
        try:
            # Initialize services
            db = get_supabase_client()
            commit_service = CommitAnalysisService(db)
            
            # Prepare commit data for analysis
            commit_data = {
                "repository": f"{self.config['github_username']}/{self.config['demo_repo_name']}",
                "commit_hash": commit_sha,
                "author": {
                    "name": author,
                    "email": "demo@example.com",
                    "login": self.config['github_username']
                },
                "message": commit_message,
                "timestamp": date,
                "url": f"https://github.com/{self.config['github_username']}/{self.config['demo_repo_name']}/commit/{commit_sha}"
            }
            
            with self.console.status("[bold yellow]AI is analyzing the commit (this may take 10-30 seconds)...[/bold yellow]") as status:
                # Run the async analysis
                analyzed_commit = asyncio.run(
                    commit_service.analyze_commit(
                        commit_hash=commit_sha,
                        commit_data=commit_data,
                        fetch_diff=True  # Fetch diff from GitHub using PAT
                    )
                )
                
            if analyzed_commit:
                self.console.print("[green]✓ Commit analysis completed successfully[/green]")
                
                # Show the analysis results
                self.console.print("\n[bold]AI Analysis Results:[/bold]")
                
                # Display analysis in a nice table with BOTH scoring methods
                table = Table(title="Commit Analysis - Traditional Hours Method", box=box.ROUNDED)
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")
                
                table.add_row("Commit SHA", commit_sha[:8])
                table.add_row("Complexity Score", f"{analyzed_commit.complexity_score}/10" if analyzed_commit.complexity_score else "N/A")
                table.add_row("AI Estimated Hours", f"{analyzed_commit.ai_estimated_hours:.1f} hours" if analyzed_commit.ai_estimated_hours else "N/A")
                table.add_row("Seniority Score", f"{analyzed_commit.seniority_score}/10" if analyzed_commit.seniority_score else "N/A")
                
                if analyzed_commit.risk_level:
                    risk_color = {"low": "green", "medium": "yellow", "high": "red"}.get(
                        analyzed_commit.risk_level.lower(), "white"
                    )
                    table.add_row("Risk Level", f"[{risk_color}]{analyzed_commit.risk_level.upper()}[/{risk_color}]")
                
                if analyzed_commit.changed_files:
                    table.add_row("Files Changed", str(len(analyzed_commit.changed_files)))
                
                additions = analyzed_commit.lines_added or 0
                deletions = analyzed_commit.lines_deleted or 0
                table.add_row("Lines Changed", f"[green]+{additions}[/green] [red]-{deletions}[/red]")
                
                self.console.print(table)
                
                # Parse and display impact scoring from ai_analysis_notes
                if analyzed_commit.ai_analysis_notes:
                    try:
                        import json
                        impact_data = json.loads(analyzed_commit.ai_analysis_notes)
                        
                        # Display impact scoring table
                        impact_table = Table(title="Commit Analysis - Impact Points Method", box=box.ROUNDED)
                        impact_table.add_column("Metric", style="cyan")
                        impact_table.add_column("Value", style="green")
                        impact_table.add_column("Reasoning", style="dim")
                        
                        impact_table.add_row(
                            "Business Value", 
                            f"{impact_data.get('impact_business_value', 0)}/10",
                            impact_data.get('impact_business_value_reasoning', '')[:50] + "..."
                        )
                        impact_table.add_row(
                            "Technical Complexity", 
                            f"{impact_data.get('impact_technical_complexity', 0)}/10",
                            impact_data.get('impact_technical_complexity_reasoning', '')[:50] + "..."
                        )
                        impact_table.add_row(
                            "Code Quality", 
                            f"{impact_data.get('impact_code_quality', 1.0)}x",
                            impact_data.get('impact_code_quality_reasoning', '')[:50] + "..."
                        )
                        impact_table.add_row(
                            "Risk Factor", 
                            f"{impact_data.get('impact_risk_factor', 1.0)}x",
                            impact_data.get('impact_risk_factor_reasoning', '')[:50] + "..."
                        )
                        
                        # Calculate and show impact score
                        impact_score = impact_data.get('impact_score', 0)
                        impact_table.add_row(
                            "[bold]Impact Score[/bold]", 
                            f"[bold]{impact_score} points[/bold]",
                            f"({impact_data.get('impact_business_value', 0)} × {impact_data.get('impact_technical_complexity', 0)} × {impact_data.get('impact_code_quality', 1.0)}) ÷ {impact_data.get('impact_risk_factor', 1.0)}"
                        )
                        
                        self.console.print("\n")
                        self.console.print(impact_table)
                        
                        # Show comparison
                        self.console.print("\n[bold]Scoring Method Comparison:[/bold]")
                        comparison_table = Table(box=box.SIMPLE)
                        comparison_table.add_column("Method", style="cyan")
                        comparison_table.add_column("Result", style="green")
                        comparison_table.add_column("Focus", style="dim")
                        
                        comparison_table.add_row(
                            "Traditional Hours",
                            f"{analyzed_commit.ai_estimated_hours:.1f} hours",
                            "Time to implement"
                        )
                        comparison_table.add_row(
                            "Impact Points",
                            f"{impact_score} points",
                            "Business value delivered"
                        )
                        
                        self.console.print(comparison_table)
                        
                    except Exception as e:
                        self.console.print(f"[yellow]Could not parse impact scoring data: {e}[/yellow]")
                
                # Show commit message
                if analyzed_commit.commit_message:
                    self.console.print("\n[bold]Commit Message:[/bold]")
                    self.console.print(Panel(
                        analyzed_commit.commit_message,
                        border_style="blue"
                    ))
                
                # Show seniority rationale as AI insights
                if analyzed_commit.seniority_rationale:
                    self.console.print("\n[bold]AI Insights:[/bold]")
                    self.console.print(Panel(
                        analyzed_commit.seniority_rationale,
                        border_style="green"
                    ))
                
                # Show key changes if available
                if analyzed_commit.key_changes:
                    self.console.print("\n[bold]Key Changes Identified:[/bold]")
                    for change in analyzed_commit.key_changes:
                        self.console.print(f"  [dim]•[/dim] {change}")
                
                # Add explanation of the two scoring methods
                self.console.print("\n[bold yellow]📊 Analysis Explanation:[/bold yellow]")
                self.console.print("[dim]The Traditional Hours method estimates time spent coding, which can be[/dim]")
                self.console.print("[dim]unfairly low for LLM-assisted development or unfairly high for manual work.[/dim]")
                self.console.print("")
                self.console.print("[dim]The Impact Points method focuses on business value delivered, considering:[/dim]")
                self.console.print("[dim]  • Business Value: How critical is this to users/revenue?[/dim]")
                self.console.print("[dim]  • Technical Complexity: How difficult was the problem?[/dim]")
                self.console.print("[dim]  • Code Quality: Are there tests and documentation?[/dim]")
                self.console.print("[dim]  • Risk Factor: Is this touching critical systems?[/dim]")
                self.console.print("")
                self.console.print("[dim]This makes it fair for both LLM-assisted and manual development![/dim]")
                
                return True  # Success
                        
            else:
                self.console.print("[red]✗ Failed to analyze commit[/red]")
                self.console.print("[yellow]Check that your GITHUB_TOKEN has repo access[/yellow]")
                return False
                
        except ImportError as e:
            self.console.print(f"[red]✗ Error importing analysis modules: {e}[/red]")
            self.console.print("[yellow]Make sure you're running from the backend virtual environment[/yellow]")
            return False
        except Exception as e:
            self.console.print(f"[red]✗ Error analyzing commit: {e}[/red]")
            return False
    
    def show_commit_analysis(self, commit_sha: str):
        """Display commit analysis results"""
        with self.console.status(f"[bold green]Fetching analysis for commit {commit_sha[:8]}...[/bold green]") as status:
            try:
                response = self.session.get(
                    f"{self.config['api_base_url']}/api/v1/commits/{commit_sha}",
                    timeout=10
                )
                
                if response.status_code == 200:
                    analysis = response.json()
                    self.console.print("[green]✓ Analysis retrieved successfully[/green]\n")
                    
                    # Create analysis table
                    table = Table(
                        title="🤖 AI Commit Analysis Results",
                        show_header=False,
                        box=box.ROUNDED,
                        title_style="bold magenta"
                    )
                    table.add_column("Metric", style="cyan", width=20)
                    table.add_column("Value", style="green")
                    
                    # Add rows with better formatting
                    complexity = analysis.get('complexity', 'N/A')
                    if complexity != 'N/A':
                        complexity_bar = "█" * int(float(complexity)) + "░" * (10 - int(float(complexity)))
                        table.add_row("Complexity Score", f"{complexity}/10 [{complexity_bar}]")
                    else:
                        table.add_row("Complexity Score", "N/A")
                    
                    hours = analysis.get('ai_hours', 'N/A')
                    if hours != 'N/A':
                        table.add_row("Estimated Hours", f"{float(hours):.1f} hours")
                    else:
                        table.add_row("Estimated Hours", "N/A")
                    
                    seniority = analysis.get('seniority_score', 'N/A')
                    if seniority != 'N/A':
                        seniority_bar = "█" * int(float(seniority)) + "░" * (10 - int(float(seniority)))
                        table.add_row("Code Quality", f"{seniority}/10 [{seniority_bar}]")
                    else:
                        table.add_row("Code Quality", "N/A")
                    
                    additions = analysis.get('additions', 0)
                    deletions = analysis.get('deletions', 0)
                    table.add_row("Lines Changed", f"[green]+{additions}[/green] [red]-{deletions}[/red]")
                    
                    risk = analysis.get('risk_level', 'N/A')
                    risk_color = {"low": "green", "medium": "yellow", "high": "red"}.get(risk.lower(), "white")
                    table.add_row("Risk Level", f"[{risk_color}]{risk.upper()}[/{risk_color}]")
                    
                    self.console.print(table)
                    
                    if analysis.get('key_changes'):
                        self.console.print("\n[bold cyan]Key Changes Identified:[/bold cyan]")
                        for change in analysis['key_changes']:
                            self.console.print(f"  [dim]•[/dim] {change}")
                            
                elif response.status_code == 404:
                    self.console.print("[yellow]⚠ Analysis not found - webhook might not be configured[/yellow]")
                    self.console.print("[dim]  The commit needs to be processed through the webhook first[/dim]")
                else:
                    self.console.print(f"[red]✗ API returned status: {response.status_code}[/red]")
                    self.console.print(f"[dim]Response: {response.text[:200]}...[/dim]")
                    
            except requests.exceptions.Timeout:
                self.console.print("[red]✗ Request timed out[/red]")
            except requests.exceptions.ConnectionError:
                self.console.print("[red]✗ Could not connect to API[/red]")
            except Exception as e:
                self.console.print(f"[red]✗ Error fetching analysis: {e}[/red]")
    
    def demo_auto_documentation(self):
        """Demonstrate auto documentation features"""
        self.console.print("\n[bold blue]=== Auto Documentation Demo ===[/bold blue]\n")
        
        demo_text = """
This section demonstrates AI-powered documentation generation.

We'll:
1. Push code that needs documentation
2. View AI-generated documentation suggestions
3. Review and approve the changes
4. See the pull request created
        """
        self.console.print(Panel(Markdown(demo_text), border_style="blue"))
        
        if not Confirm.ask("Continue with auto documentation demo?", default=True):
            return
        
        # Configure docs repository in settings
        self.console.print("Configuring documentation repository...")
        response = self.session.post(
            f"{self.config['api_base_url']}/api/v1/settings/docs-repository",
            json={"repository": f"{self.config['github_username']}/{self.config['demo_docs_repo_name']}"}
        )
        
        # Trigger documentation generation
        self.console.print("Triggering documentation analysis...")
        response = self.session.post(
            f"{self.config['api_base_url']}/api/v1/documentation/analyze",
            json={
                "repository": f"{self.config['github_username']}/{self.config['demo_repo_name']}",
                "branch": "main"
            }
        )
        
        if response.status_code == 200:
            doc_request_id = response.json().get("request_id")
            self.console.print(f"[green]✓ Documentation analysis started: {doc_request_id}[/green]")
            
            # Wait for processing
            time.sleep(5)
            
            # Show pending approvals
            self.show_documentation_approvals()
            
            # Open documentation page
            if Confirm.ask("Open documentation management page?", default=True):
                webbrowser.open(f"{self.config['frontend_url']}/documentation")
        
        self.pause_for_explanation(
            "The auto documentation system has analyzed the code changes and generated "
            "contextual documentation updates. The approval queue allows human review "
            "before changes are committed to your documentation repository."
        )
    
    def show_documentation_approvals(self):
        """Display pending documentation approvals"""
        response = self.session.get(
            f"{self.config['api_base_url']}/api/v1/documentation/approvals/pending"
        )
        
        if response.status_code == 200 and response.json():
            approvals = response.json()
            
            self.console.print("\n[bold]Pending Documentation Updates:[/bold]")
            for approval in approvals[:3]:  # Show first 3
                self.console.print(f"\nFile: {approval.get('file_path', 'N/A')}")
                self.console.print(f"Type: {approval.get('change_type', 'N/A')}")
                if approval.get('suggested_content'):
                    self.console.print("Suggested content preview:")
                    preview = approval['suggested_content'][:200] + "..."
                    self.console.print(Panel(preview, border_style="dim"))
    
    def demo_semantic_search(self):
        """Demonstrate semantic search capabilities"""
        self.console.print("\n[bold blue]=== Semantic Search Demo ===[/bold blue]\n")
        
        demo_text = """
This section demonstrates AI-powered semantic search for documentation.

We'll:
1. Search for concepts (not just keywords)
2. Find related documentation
3. Identify documentation gaps
4. View documentation quality metrics
        """
        self.console.print(Panel(Markdown(demo_text), border_style="blue"))
        
        if not Confirm.ask("Continue with semantic search demo?", default=True):
            return
        
        # Perform searches
        search_queries = [
            "How do we handle payment processing?",
            "Authentication and security",
            "Error handling patterns"
        ]
        
        for query in search_queries:
            self.console.print(f"\n[bold]Searching for: '{query}'[/bold]")
            
            response = self.session.post(
                f"{self.config['api_base_url']}/api/v1/documentation/search",
                json={"query": query, "limit": 3}
            )
            
            if response.status_code == 200:
                results = response.json()
                if results:
                    for i, result in enumerate(results, 1):
                        self.console.print(f"\n{i}. {result.get('title', 'Untitled')}")
                        self.console.print(f"   Relevance: {result.get('relevance_score', 0):.2%}")
                        self.console.print(f"   Path: {result.get('file_path', 'N/A')}")
                else:
                    self.console.print("[yellow]No results found[/yellow]")
            
            time.sleep(1)
        
        # Show documentation coverage
        self.show_documentation_coverage()
        
        self.pause_for_explanation(
            "Semantic search understands the meaning behind queries, not just keywords. "
            "It can identify related concepts and help discover documentation gaps in your codebase."
        )
    
    def show_documentation_coverage(self):
        """Display documentation coverage statistics"""
        self.console.print("\n[bold]Documentation Coverage Analysis:[/bold]")
        
        response = self.session.get(
            f"{self.config['api_base_url']}/api/v1/documentation/coverage"
        )
        
        if response.status_code == 200:
            coverage = response.json()
            
            table = Table(title="Coverage Statistics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Total Files", str(coverage.get('total_files', 0)))
            table.add_row("Documented Files", str(coverage.get('documented_files', 0)))
            table.add_row("Coverage Percentage", f"{coverage.get('coverage_percentage', 0):.1f}%")
            table.add_row("Average Quality Score", f"{coverage.get('avg_quality_score', 0):.1f}/10")
            
            self.console.print(table)
            
            if coverage.get('gaps'):
                self.console.print("\n[bold]Top Documentation Gaps:[/bold]")
                for gap in coverage['gaps'][:5]:
                    self.console.print(f"  • {gap['file']}: {gap['reason']}")
    
    def demo_analytics_dashboard(self):
        """Demonstrate analytics and reporting features"""
        self.console.print("\n[bold blue]=== Analytics Dashboard Demo ===[/bold blue]\n")
        
        demo_text = """
This section demonstrates team analytics and productivity insights.

Features:
- Daily/weekly productivity summaries
- Individual and team metrics
- Code quality trends
- Repository activity analysis
        """
        self.console.print(Panel(Markdown(demo_text), border_style="blue"))
        
        if not Confirm.ask("Continue with analytics demo?", default=True):
            return
        
        # Fetch and display analytics
        self.show_weekly_summary()
        self.show_team_metrics()
        
        # Open analytics dashboard
        if Confirm.ask("Open full analytics dashboard?", default=True):
            webbrowser.open(f"{self.config['frontend_url']}/dashboard")
        
        self.pause_for_explanation(
            "The analytics dashboard provides comprehensive insights into team productivity, "
            "code quality trends, and individual contributor metrics. All data is gathered "
            "automatically from GitHub and other integrated tools."
        )
    
    def show_weekly_summary(self):
        """Display weekly productivity summary"""
        response = self.session.get(
            f"{self.config['api_base_url']}/api/v1/analytics/weekly-summary"
        )
        
        if response.status_code == 200:
            summary = response.json()
            
            self.console.print("\n[bold]Weekly Productivity Summary:[/bold]")
            
            table = Table()
            table.add_column("Day", style="cyan")
            table.add_column("Commits", style="green")
            table.add_column("Hours", style="yellow")
            table.add_column("Lines Changed", style="blue")
            
            for day_data in summary.get('daily_breakdown', []):
                table.add_row(
                    day_data['day'],
                    str(day_data['commits']),
                    f"{day_data['hours']:.1f}",
                    f"+{day_data['additions']} -{day_data['deletions']}"
                )
            
            self.console.print(table)
    
    def show_team_metrics(self):
        """Display team performance metrics"""
        response = self.session.get(
            f"{self.config['api_base_url']}/api/v1/analytics/team-metrics"
        )
        
        if response.status_code == 200:
            metrics = response.json()
            
            self.console.print("\n[bold]Team Performance Metrics:[/bold]")
            
            # Key metrics
            self.console.print(f"Total Commits (This Week): {metrics.get('total_commits', 0)}")
            self.console.print(f"Average Complexity Score: {metrics.get('avg_complexity', 0):.1f}/10")
            self.console.print(f"Code Quality Trend: {metrics.get('quality_trend', 'stable')}")
            self.console.print(f"Documentation Coverage: {metrics.get('doc_coverage', 0):.1f}%")
    
    def pause_for_explanation(self, message: str):
        """Pause demo with explanation"""
        self.console.print(f"\n[dim]{message}[/dim]")
        Prompt.ask("\nPress Enter to continue", default="")
    
    def show_summary(self):
        """Display demo summary and next steps"""
        summary_text = """
# Demo Summary

You've seen how GolfDaddy Brain can:

1. **Automatically track engineering work** - Every commit is analyzed for effort and complexity
2. **Generate contextual documentation** - AI understands your code and suggests updates
3. **Enable semantic search** - Find information by meaning, not just keywords
4. **Provide actionable insights** - Dashboard shows productivity trends and metrics

## Next Steps

1. **Configure webhooks** for your repositories
2. **Customize AI prompts** for your team's style
3. **Set up Slack integration** for notifications
4. **Train the team** on approval workflows

## Resources

- API Documentation: `/docs`
- Admin Panel: `/admin`
- Support: support@golfdaddy.com
        """
        self.console.print(Panel(Markdown(summary_text), title="Demo Complete", border_style="green"))
    
    def cleanup(self):
        """Clean up demo resources"""
        self.console.print("\n[bold]Cleaning up demo resources...[/bold]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            
            # Delete GitHub repositories
            if self.config["github_username"]:
                for repo_type, repo_name in self.created_resources:
                    if repo_type == "github_repo":
                        task = progress.add_task(f"Deleting {repo_name}...", total=1)
                        try:
                            headers = {"Authorization": f"token {self.config['github_token']}"}
                            requests.delete(
                                f"https://api.github.com/repos/{self.config['github_username']}/{repo_name}",
                                headers=headers
                            )
                        except:
                            pass
                        progress.update(task, completed=1)
            
            # Clean up local data
            task = progress.add_task("Cleaning local data...", total=1)
            # Add any local cleanup here
            progress.update(task, completed=1)
        
        self.console.print("[green]✓ Cleanup complete[/green]")


def main():
    """Main entry point"""
    # Check if running from correct directory
    if not Path("backend").exists() or not Path("frontend").exists():
        console.print("[red]Error: Please run this script from the project root directory[/red]")
        sys.exit(1)
    
    # Install required packages if needed
    try:
        import rich
        import git
    except ImportError:
        console.print("[yellow]Installing required packages...[/yellow]")
        subprocess.run([sys.executable, "-m", "pip", "install", "rich", "gitpython", "requests"])
        console.print("[green]✓ Packages installed[/green]")
        console.print("Please run the script again")
        sys.exit(0)
    
    # Run demo
    demo = GolfDaddyDemo()
    demo.run()


if __name__ == "__main__":
    main()