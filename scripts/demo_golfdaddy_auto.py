#!/usr/bin/env python3
"""
Automated (non-interactive) version of the GolfDaddy demo
Perfect for testing and CI/CD environments
"""

import sys
import os
import time
from pathlib import Path
from typing import Dict, Any
import asyncio
import requests

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# Load environment
from dotenv import load_dotenv
env_path = backend_path / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Import Rich for output
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich import box

# Import backend modules
try:
    from app.config.database import get_supabase_client
    from app.services.commit_analysis_service import CommitAnalysisService
    BACKEND_AVAILABLE = True
except ImportError:
    BACKEND_AVAILABLE = False
    print("Warning: Backend modules not available")

console = Console()


class AutomatedDemo:
    """Automated demo runner"""
    
    def __init__(self):
        self.console = console
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.api_base_url = os.getenv("VITE_API_URL", "http://localhost:8000")
        self.results = {}
    
    def run(self):
        """Run the automated demo"""
        self.console.print(Panel.fit(
            "[bold blue]🚀 GolfDaddy Brain Automated Demo[/bold blue]\n"
            "Running without user interaction",
            border_style="blue"
        ))
        
        # 1. Check prerequisites
        self.check_prerequisites()
        
        # 2. Test GitHub integration
        self.test_github_integration()
        
        # 3. Test commit analysis
        if BACKEND_AVAILABLE:
            self.test_commit_analysis()
        else:
            self.console.print("[yellow]⚠ Skipping commit analysis (backend not available)[/yellow]")
        
        # 4. Show results
        self.show_results()
    
    def check_prerequisites(self):
        """Check all prerequisites"""
        self.console.print("\n[bold]1. Checking Prerequisites[/bold]")
        
        checks = {
            "API Server": self._check_api(),
            "GitHub Token": bool(self.github_token),
            "OpenAI API Key": bool(os.getenv("OPENAI_API_KEY")),
            "Backend Modules": BACKEND_AVAILABLE,
            "Supabase": bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_KEY"))
        }
        
        table = Table(title="Prerequisites", box=box.ROUNDED)
        table.add_column("Component", style="cyan")
        table.add_column("Status")
        
        for component, status in checks.items():
            status_text = "[green]✓ Ready[/green]" if status else "[red]✗ Not Ready[/red]"
            table.add_row(component, status_text)
        
        self.console.print(table)
        self.results['prerequisites'] = all(checks.values())
    
    def _check_api(self) -> bool:
        """Check if API is accessible"""
        try:
            response = requests.get(f"{self.api_base_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def test_github_integration(self):
        """Test GitHub integration"""
        self.console.print("\n[bold]2. Testing GitHub Integration[/bold]")
        
        if not self.github_token:
            self.console.print("[red]✗ No GitHub token found[/red]")
            self.results['github'] = False
            return
        
        try:
            # Get user info
            headers = {"Authorization": f"token {self.github_token}"}
            response = requests.get("https://api.github.com/user", headers=headers)
            
            if response.status_code == 200:
                user_data = response.json()
                self.console.print(f"✓ Authenticated as: [green]{user_data['login']}[/green]")
                
                # Get latest commit from repo
                repo = "parkerjbeard/golfdaddy-brain-mono"
                response = requests.get(
                    f"https://api.github.com/repos/{repo}/commits",
                    headers=headers,
                    params={"per_page": 1}
                )
                
                if response.status_code == 200 and response.json():
                    commit = response.json()[0]
                    self.console.print(f"✓ Latest commit: [blue]{commit['sha'][:8]}[/blue] - {commit['commit']['message'][:60]}...")
                    self.results['github'] = True
                    self.results['latest_commit'] = commit
                else:
                    self.console.print("[red]✗ Could not fetch commits[/red]")
                    self.results['github'] = False
            else:
                self.console.print(f"[red]✗ GitHub authentication failed: {response.status_code}[/red]")
                self.results['github'] = False
                
        except Exception as e:
            self.console.print(f"[red]✗ GitHub error: {e}[/red]")
            self.results['github'] = False
    
    def test_commit_analysis(self):
        """Test commit analysis functionality"""
        self.console.print("\n[bold]3. Testing Commit Analysis[/bold]")
        
        if not self.results.get('latest_commit'):
            self.console.print("[yellow]⚠ No commit to analyze[/yellow]")
            return
        
        try:
            # Initialize services
            db = get_supabase_client()
            service = CommitAnalysisService(db)
            
            commit = self.results['latest_commit']
            commit_data = {
                "repository": "parkerjbeard/golfdaddy-brain-mono",
                "commit_hash": commit['sha'],
                "author": {
                    "name": commit['commit']['author']['name'],
                    "email": commit['commit']['author']['email'],
                    "login": commit.get('author', {}).get('login') if commit.get('author') else None
                },
                "message": commit['commit']['message'],
                "timestamp": commit['commit']['author']['date'],
                "url": commit['html_url']
            }
            
            self.console.print(f"Analyzing commit [blue]{commit['sha'][:8]}[/blue]...")
            
            # Run analysis
            with self.console.status("[yellow]Running AI analysis...[/yellow]"):
                analyzed = asyncio.run(
                    service.analyze_commit(
                        commit_hash=commit['sha'],
                        commit_data=commit_data,
                        fetch_diff=True
                    )
                )
            
            if analyzed:
                self.console.print("[green]✓ Analysis completed![/green]")
                
                # Display results
                table = Table(title="Analysis Results", box=box.ROUNDED)
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")
                
                table.add_row("Complexity Score", f"{analyzed.complexity_score}/10")
                table.add_row("AI Estimated Hours", f"{analyzed.ai_estimated_hours:.1f}")
                table.add_row("Points Earned", str(analyzed.points_earned))
                
                if analyzed.risk_level:
                    table.add_row("Risk Level", analyzed.risk_level.upper())
                
                if analyzed.files_changed:
                    table.add_row("Files Changed", str(analyzed.files_changed))
                
                self.console.print(table)
                
                if analyzed.commit_summary:
                    self.console.print(f"\n[bold]Summary:[/bold] {analyzed.commit_summary}")
                
                self.results['analysis'] = True
                self.results['analysis_data'] = analyzed
            else:
                self.console.print("[red]✗ Analysis failed[/red]")
                self.results['analysis'] = False
                
        except Exception as e:
            self.console.print(f"[red]✗ Analysis error: {e}[/red]")
            import traceback
            traceback.print_exc()
            self.results['analysis'] = False
    
    def show_results(self):
        """Show demo results summary"""
        self.console.print("\n" + "=" * 70)
        self.console.print("[bold]Demo Results Summary[/bold]")
        self.console.print("=" * 70)
        
        summary = {
            "Prerequisites": "✓ Pass" if self.results.get('prerequisites') else "✗ Fail",
            "GitHub Integration": "✓ Pass" if self.results.get('github') else "✗ Fail",
            "Commit Analysis": "✓ Pass" if self.results.get('analysis') else "✗ Fail or Skipped"
        }
        
        for test, result in summary.items():
            color = "green" if "✓" in result else "red" if "✗" in result else "yellow"
            self.console.print(f"{test}: [{color}]{result}[/{color}]")
        
        overall = all([
            self.results.get('prerequisites', False),
            self.results.get('github', False)
        ])
        
        self.console.print(f"\n[bold]Overall: [{'green' if overall else 'red'}]{'✓ SUCCESS' if overall else '✗ FAILED'}[/{'green' if overall else 'red'}][/bold]")
        
        if overall:
            self.console.print("\n[green]The GolfDaddy Brain system is working correctly![/green]")
            self.console.print("You can run the interactive demo with: python scripts/demo_golfdaddy.py")
        else:
            self.console.print("\n[yellow]Some components need attention. Check the results above.[/yellow]")


if __name__ == "__main__":
    demo = AutomatedDemo()
    demo.run()