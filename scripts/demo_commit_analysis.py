#!/usr/bin/env python3
"""
Demo: Direct Commit Analysis using GitHub PAT
Analyzes your recent commits directly without going through webhooks.
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime

# Add backend directory to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# Now we can import from the backend
from app.config.database import get_db
from app.services.commit_analysis_service import CommitAnalysisService
from app.integrations.github_integration import GitHubIntegration
from dotenv import load_dotenv

# Load environment variables
env_path = backend_path / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Try to import rich for better output
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    console = Console()
    has_rich = True
except ImportError:
    has_rich = False
    print("Installing rich for better output...")
    os.system(f"{sys.executable} -m pip install rich")
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    console = Console()
    has_rich = True

async def analyze_recent_commits():
    """Main demo function to analyze recent commits."""
    
    console.print(Panel.fit("🚀 GolfDaddy Commit Analysis Demo", style="bold blue"))
    
    # Check for GitHub token
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        console.print("[red]❌ Error: GITHUB_TOKEN not found in environment[/red]")
        console.print("Please set GITHUB_TOKEN in backend/.env")
        sys.exit(1)
    
    # Initialize services
    console.print("\n[bold]Step 1: Initializing services...[/bold]")
    
    try:
        # Get database connection
        db = get_db()
        
        # Initialize services
        github_integration = GitHubIntegration()
        commit_service = CommitAnalysisService(db)
        
        console.print("✅ Services initialized successfully")
        
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize services: {e}[/red]")
        sys.exit(1)
    
    # Get repository info
    console.print("\n[bold]Step 2: Repository selection[/bold]")
    repo_owner = "parkerjbeard"
    repo_name = "golfdaddy-brain-mono"
    repository = f"{repo_owner}/{repo_name}"
    console.print(f"📦 Using repository: [cyan]{repository}[/cyan]")
    
    # Fetch recent commits
    console.print("\n[bold]Step 3: Fetching recent commits...[/bold]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Fetching commits from GitHub...", total=None)
        
        try:
            # Use GitHub API to get recent commits
            import requests
            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            url = f"https://api.github.com/repos/{repository}/commits"
            params = {"per_page": 5}  # Get last 5 commits
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            commits = response.json()
            progress.update(task, completed=True)
            
        except Exception as e:
            console.print(f"[red]❌ Failed to fetch commits: {e}[/red]")
            sys.exit(1)
    
    # Display commits
    console.print(f"\n✅ Found {len(commits)} recent commits:")
    
    table = Table(title="Recent Commits", show_header=True, header_style="bold magenta")
    table.add_column("SHA", style="dim", width=12)
    table.add_column("Author", style="cyan")
    table.add_column("Date", style="green")
    table.add_column("Message", style="white")
    
    for commit in commits[:5]:
        sha = commit['sha'][:8]
        author = commit['commit']['author']['name']
        date = datetime.fromisoformat(commit['commit']['author']['date'].replace('Z', '+00:00'))
        date_str = date.strftime("%Y-%m-%d %H:%M")
        message = commit['commit']['message'].split('\n')[0][:50] + "..."
        
        table.add_row(sha, author, date_str, message)
    
    console.print(table)
    
    # Let user select a commit
    console.print("\n[bold]Step 4: Select a commit to analyze[/bold]")
    console.print("Enter the number of the commit to analyze (1-5), or press Enter for the latest:")
    
    choice = input("> ").strip()
    if not choice:
        selected_index = 0
    else:
        try:
            selected_index = int(choice) - 1
            if selected_index < 0 or selected_index >= len(commits):
                console.print("[yellow]Invalid choice, using latest commit[/yellow]")
                selected_index = 0
        except ValueError:
            console.print("[yellow]Invalid input, using latest commit[/yellow]")
            selected_index = 0
    
    selected_commit = commits[selected_index]
    
    # Prepare commit data for analysis
    console.print(f"\n[bold]Step 5: Analyzing commit [cyan]{selected_commit['sha'][:8]}[/cyan]...[/bold]")
    
    commit_data = {
        "repository": repository,
        "commit_hash": selected_commit['sha'],
        "author": {
            "name": selected_commit['commit']['author']['name'],
            "email": selected_commit['commit']['author']['email'],
            "login": selected_commit['author']['login'] if selected_commit.get('author') else None
        },
        "message": selected_commit['commit']['message'],
        "timestamp": selected_commit['commit']['author']['date'],
        "url": selected_commit['html_url']
    }
    
    # Analyze the commit
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Analyzing commit with AI...", total=None)
        
        try:
            # Run the analysis
            analyzed_commit = await commit_service.analyze_commit(
                commit_hash=selected_commit['sha'],
                commit_data=commit_data,
                fetch_diff=True  # Will fetch diff from GitHub
            )
            
            progress.update(task, completed=True)
            
            if analyzed_commit:
                console.print("\n✅ [green]Commit analyzed successfully![/green]")
                
                # Display analysis results
                results_panel = Panel(
                    f"""[bold cyan]Analysis Results[/bold cyan]
                    
📊 [bold]Complexity Score:[/bold] {analyzed_commit.complexity_score}/10
💯 [bold]AI Estimated Hours:[/bold] {analyzed_commit.ai_estimated_hours:.1f} hours
🎯 [bold]Points Earned:[/bold] {analyzed_commit.points_earned}
📝 [bold]Summary:[/bold] {analyzed_commit.commit_summary}

[bold]AI Analysis:[/bold]
{analyzed_commit.ai_analysis}

[bold]Files Changed:[/bold] {analyzed_commit.files_changed}
[bold]Lines Added:[/bold] {analyzed_commit.additions}
[bold]Lines Deleted:[/bold] {analyzed_commit.deletions}
""",
                    title="Commit Analysis",
                    style="green"
                )
                console.print(results_panel)
                
                # Show how this would appear in daily reports
                console.print("\n[bold]Step 6: Impact on Daily Reports[/bold]")
                console.print("This commit analysis would contribute to:")
                console.print("• Daily commit summary and productivity metrics")
                console.print("• Team performance dashboards")
                console.print("• Weekly AI-generated insights")
                console.print("• Manager visibility into team productivity")
                
            else:
                console.print("[red]❌ Failed to analyze commit[/red]")
                
        except Exception as e:
            progress.update(task, completed=True)
            console.print(f"[red]❌ Error during analysis: {e}[/red]")
            import traceback
            traceback.print_exc()
    
    console.print("\n[bold green]✨ Demo completed![/bold green]")
    console.print("\nThis demonstrates how GolfDaddy analyzes commits to:")
    console.print("• Calculate complexity and effort scores")
    console.print("• Generate AI-powered summaries")
    console.print("• Track developer productivity")
    console.print("• Provide insights for managers")

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(analyze_recent_commits())