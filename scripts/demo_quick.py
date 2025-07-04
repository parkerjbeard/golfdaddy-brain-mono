#!/usr/bin/env python3
"""
GolfDaddy Brain Quick Demo Script
=================================
A simplified demo script that showcases existing features without creating test data.
Perfect for quick demonstrations using existing repositories and data.
"""

import os
import time
import json
import requests
import webbrowser
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich import box

console = Console()

class QuickDemo:
    def __init__(self):
        self.api_url = os.getenv("VITE_API_URL", "http://localhost:8000")
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:8080")
        self.console = console
        
    def run(self):
        """Run the quick demo"""
        self.show_welcome()
        
        demos = [
            ("Dashboard Overview", self.demo_dashboard),
            ("GitHub Commit Analysis", self.demo_commit_analysis),
            ("Auto Documentation", self.demo_documentation),
            ("Semantic Search", self.demo_search),
            ("Team Analytics", self.demo_analytics),
        ]
        
        for title, demo_func in demos:
            self.console.print(f"\n[bold blue]=== {title} ===[/bold blue]\n")
            if Confirm.ask(f"Demo {title}?", default=True):
                demo_func()
            else:
                self.console.print("[yellow]Skipped[/yellow]")
        
        self.show_closing()
    
    def show_welcome(self):
        """Show welcome message"""
        welcome = """
# GolfDaddy Brain Quick Demo

This quick demo will showcase the key features using your existing data.

**Prerequisites:**
- Application running at http://localhost:8000
- Frontend running at http://localhost:5173
- Some existing data in the system
        """
        self.console.print(Panel(Markdown(welcome), title="Quick Demo", border_style="blue"))
        
        if not Confirm.ask("Ready to start?", default=True):
            exit(0)
    
    def demo_dashboard(self):
        """Open and explain the dashboard"""
        with self.console.status("[bold green]Loading dashboard information...[/bold green]"):
            time.sleep(1)
        
        self.console.print(Panel.fit(
            "[bold cyan]Dashboard Features:[/bold cyan]\n\n"
            "• Recent commits and their AI analysis\n"
            "• Daily productivity metrics\n"
            "• Documentation coverage status\n"
            "• Team performance KPIs",
            title="📊 Dashboard Overview",
            border_style="cyan"
        ))
        
        if Confirm.ask("\n[bold yellow]Open dashboard in browser?[/bold yellow]", default=True):
            self.console.print(f"\n[dim]Opening {self.frontend_url}/dashboard...[/dim]")
            try:
                webbrowser.open(f"{self.frontend_url}/dashboard")
                self.console.print("[green]✓ Dashboard opened successfully[/green]")
                time.sleep(2)
            except Exception as e:
                self.console.print(f"[red]✗ Failed to open browser: {e}[/red]")
        
        self.explain_feature(
            "The dashboard automatically updates as new commits are pushed to your "
            "repositories. Each commit is analyzed for complexity and effort."
        )
    
    def demo_commit_analysis(self):
        """Show commit analysis features"""
        self.console.print(Panel.fit(
            "[bold cyan]Commit Analysis Demo[/bold cyan]\n\n"
            "This feature automatically analyzes every git commit to estimate:\n"
            "• Development effort (hours)\n"
            "• Code complexity (1-10 scale)\n"
            "• Code quality/seniority level\n"
            "• Risk assessment",
            title="🔍 GitHub Commit Analysis",
            border_style="cyan"
        ))
        
        # Make API call to get recent commits
        with self.console.status("[bold green]Fetching recent commits from API...[/bold green]") as status:
            try:
                response = requests.get(f"{self.api_url}/api/v1/commits/recent?limit=5", timeout=10)
                
                if response.status_code == 200:
                    commits = response.json()
                    status.update("[bold green]Processing commit data...[/bold green]")
                    time.sleep(0.5)
                    
                    if commits:
                        self.console.print("\n[green]✓ Found recent commits[/green]\n")
                        
                        table = Table(
                            title="Recent Commit Analysis Results",
                            box=box.ROUNDED,
                            show_header=True,
                            header_style="bold magenta",
                            title_style="bold blue"
                        )
                        table.add_column("Commit Message", style="cyan", max_width=40)
                        table.add_column("AI Hours", style="green", justify="center")
                        table.add_column("Complexity", style="yellow", justify="center")
                        table.add_column("Quality", style="blue", justify="center")
                        
                        for commit in commits[:5]:
                            message = commit.get('message', 'No message')
                            if len(message) > 40:
                                message = message[:37] + "..."
                            
                            table.add_row(
                                message,
                                f"{commit.get('ai_hours', 0):.1f}h",
                                f"{commit.get('complexity', 0)}/10",
                                f"{commit.get('seniority_score', 0)}/10"
                            )
                        
                        self.console.print(table)
                    else:
                        self.console.print(Panel(
                            "[yellow]No recent commits found in the system.[/yellow]\n\n"
                            "This could mean:\n"
                            "• No commits have been analyzed yet\n"
                            "• GitHub webhook is not configured\n"
                            "• The system was recently reset",
                            title="⚠️ No Data",
                            border_style="yellow"
                        ))
                else:
                    self.console.print(f"\n[red]✗ API returned status code: {response.status_code}[/red]")
                    self.console.print(f"[dim]Response: {response.text[:200]}...[/dim]")
                    
            except requests.exceptions.Timeout:
                self.console.print("\n[red]✗ API request timed out[/red]")
                self.console.print("[yellow]The backend might be slow or unresponsive[/yellow]")
            except requests.exceptions.ConnectionError:
                self.console.print("\n[red]✗ Could not connect to API[/red]")
                self.console.print(f"[yellow]Is the backend running at {self.api_url}?[/yellow]")
            except Exception as e:
                self.console.print(f"\n[red]✗ Unexpected error: {type(e).__name__}[/red]")
                self.console.print(f"[dim]{str(e)}[/dim]")
        
        self.explain_feature(
            "Every commit is automatically analyzed using AI to estimate effort hours, "
            "complexity, and code quality. This helps track true productivity beyond simple LOC metrics."
        )
    
    def demo_documentation(self):
        """Show documentation features"""
        self.console.print("Auto Documentation features:")
        self.console.print("• AI analyzes code changes and suggests documentation updates")
        self.console.print("• Human approval required before changes are applied")
        self.console.print("• Creates pull requests to your docs repository")
        self.console.print("• Maintains documentation quality standards")
        
        if Confirm.ask("Open documentation management page?", default=True):
            webbrowser.open(f"{self.frontend_url}/documentation")
            time.sleep(2)
        
        # Show sample documentation update
        sample_update = """
        File: docs/api/payment.md
        
        Suggested Addition:
        ## PaymentProcessor Class
        
        The PaymentProcessor handles Stripe integration for payment processing.
        
        ### Methods:
        - `process_payment(amount, currency)`: Process a payment
        - `refund_payment(intent_id, amount)`: Issue full or partial refund
        """
        
        self.console.print("\n[bold]Sample Documentation Update:[/bold]")
        self.console.print(Panel(sample_update, border_style="dim"))
        
        self.explain_feature(
            "The AI understands your code structure and generates contextually appropriate "
            "documentation. It can update existing docs or create new ones based on code changes."
        )
    
    def demo_search(self):
        """Demo semantic search"""
        self.console.print("Semantic search understands meaning, not just keywords.")
        self.console.print("\nExample searches:")
        
        example_searches = [
            ("How do we handle authentication?", "Finds auth-related docs even without 'authentication' keyword"),
            ("Payment processing flow", "Discovers payment, billing, and transaction documentation"),
            ("Error handling best practices", "Locates error handling patterns across the codebase")
        ]
        
        for query, explanation in example_searches:
            self.console.print(f"\n[bold]Query:[/bold] {query}")
            self.console.print(f"[dim]{explanation}[/dim]")
        
        if Confirm.ask("\nTry semantic search?", default=True):
            query = Prompt.ask("Enter a search query", default="How do we handle errors?")
            
            # Simulate search
            self.console.print(f"\n[yellow]Searching for: {query}[/yellow]")
            time.sleep(1)
            
            # Mock results
            results = [
                {"title": "Error Handling Guidelines", "score": 0.92, "path": "docs/guidelines/errors.md"},
                {"title": "API Error Responses", "score": 0.87, "path": "docs/api/errors.md"},
                {"title": "Exception Handling in Services", "score": 0.84, "path": "src/services/README.md"}
            ]
            
            for i, result in enumerate(results, 1):
                self.console.print(f"\n{i}. {result['title']}")
                self.console.print(f"   Relevance: {result['score']:.0%}")
                self.console.print(f"   Path: {result['path']}")
    
    def demo_analytics(self):
        """Show analytics capabilities"""
        # Create sample analytics display
        self.console.print("[bold]Team Productivity This Week:[/bold]\n")
        
        # Weekly summary table
        table = Table()
        table.add_column("Developer", style="cyan")
        table.add_column("Commits", style="green")
        table.add_column("Est. Hours", style="yellow")
        table.add_column("Avg Quality", style="blue")
        
        # Sample data
        developers = [
            ("Alice Johnson", 12, 28.5, 8.2),
            ("Bob Smith", 8, 19.3, 7.8),
            ("Carol White", 15, 31.2, 8.5),
            ("Team Average", 11.7, 26.3, 8.2)
        ]
        
        for name, commits, hours, quality in developers:
            table.add_row(name, str(commits), f"{hours:.1f}", f"{quality:.1f}/10")
        
        self.console.print(table)
        
        # Show trends
        self.console.print("\n[bold]Trends:[/bold]")
        self.console.print("📈 Productivity: +12% from last week")
        self.console.print("📊 Code Quality: Stable (8.2 avg)")
        self.console.print("📚 Documentation Coverage: 78% (+3%)")
        
        if Confirm.ask("\nView full analytics?", default=True):
            webbrowser.open(f"{self.frontend_url}/analytics")
        
        self.explain_feature(
            "Analytics combine data from GitHub, documentation, and daily reports to provide "
            "comprehensive insights into team productivity and code quality trends."
        )
    
    def explain_feature(self, explanation: str):
        """Show feature explanation"""
        self.console.print(f"\n[dim]{explanation}[/dim]")
        Prompt.ask("\nPress Enter to continue", default="")
    
    def show_closing(self):
        """Show closing message"""
        closing = """
# Demo Complete!

## Key Takeaways:

1. **Automatic Tracking** - No manual time entry needed
2. **AI-Powered Insights** - Understands code complexity and effort
3. **Documentation Automation** - Keeps docs in sync with code
4. **Semantic Understanding** - Search by meaning, not keywords
5. **Actionable Analytics** - Data that drives decisions

## Next Steps:

1. Set up GitHub webhooks for your repositories
2. Configure your documentation repository
3. Customize AI prompts for your team
4. Train your team on the approval workflow

## Questions?

Contact: support@golfdaddy.com
Docs: https://docs.golfdaddy.com
        """
        self.console.print(Panel(Markdown(closing), title="Thank You!", border_style="green"))


def main():
    """Run the quick demo"""
    demo = QuickDemo()
    demo.run()


if __name__ == "__main__":
    main()