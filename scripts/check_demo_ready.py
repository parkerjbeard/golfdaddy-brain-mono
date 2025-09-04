#!/usr/bin/env python3
"""
Check if demo environment is ready
"""
import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Load environment variables from backend/.env
backend_env_path = Path(__file__).parent.parent / "backend" / ".env"
if backend_env_path.exists():
    load_dotenv(backend_env_path)

console = Console()

def check_demo_readiness():
    """Check if everything is ready for demo"""
    console.print("[bold]Checking Demo Readiness...[/bold]\n")
    
    checks = []
    
    # Check environment variables
    env_vars = {
        "OPENAI_API_KEY": "Required for AI analysis",
        "GITHUB_TOKEN": "Required for GitHub integration", 
        "SUPABASE_URL": "Required for database",
        "SUPABASE_SERVICE_KEY": "Required for database",
    }
    
    for var, description in env_vars.items():
        value = os.getenv(var)
        if value and len(value) > 10:  # Basic validation
            checks.append((var, "✅ Set", description))
        else:
            checks.append((var, "❌ Missing", description))
    
    # Check services
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            checks.append(("Backend API", "✅ Running", "API server at localhost:8000"))
        else:
            checks.append(("Backend API", "❌ Not healthy", "API server at localhost:8000"))
    except:
        checks.append(("Backend API", "❌ Not running", "API server at localhost:8000"))
    
    try:
        response = requests.get("http://localhost:8080", timeout=5)
        checks.append(("Frontend", "✅ Running", "React app at localhost:8080"))
    except:
        checks.append(("Frontend", "⚠️  Not running", "React app at localhost:8080"))
    
    # Check Python packages
    packages = ["rich", "gitpython", "requests", "faker"]
    missing_packages = []
    
    for package in packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        checks.append(("Python packages", f"❌ Missing: {', '.join(missing_packages)}", "Required for demo scripts"))
    else:
        checks.append(("Python packages", "✅ Installed", "All demo dependencies"))
    
    # Display results
    table = Table(title="Demo Environment Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Description", style="dim")
    
    all_good = True
    for component, status, desc in checks:
        table.add_row(component, status, desc)
        if "❌" in status:
            all_good = False
    
    console.print(table)
    
    # Summary
    console.print("\n[bold]Summary:[/bold]")
    if all_good:
        console.print("[green]✅ Your environment is ready for the demo![/green]")
        console.print("\nYou can now run:")
        console.print("  [bold]python scripts/demo_quick.py[/bold] - For a quick 15-20 minute demo")
        console.print("  [bold]python scripts/demo_golfdaddy.py[/bold] - For a full 45-60 minute demo")
    else:
        console.print("[red]❌ Some requirements are missing.[/red]")
        console.print("\n[yellow]To fix:[/yellow]")
        
        if any("OPENAI_API_KEY" in check[0] and "❌" in check[1] for check in checks):
            console.print("1. Get OpenAI API key from https://platform.openai.com/api-keys")
            console.print("   Add to .env: OPENAI_API_KEY=sk-...")
        
        if any("GITHUB_TOKEN" in check[0] and "❌" in check[1] for check in checks):
            console.print("2. Create GitHub token at https://github.com/settings/tokens")
            console.print("   Add to .env: GITHUB_TOKEN=ghp_...")
        
        if missing_packages:
            console.print(f"3. Install Python packages: pip install {' '.join(missing_packages)}")
        
        if any("Backend API" in check[0] and "❌" in check[1] for check in checks):
            console.print("4. Start dev stack: docker compose --profile dev up -d")

if __name__ == "__main__":
    check_demo_readiness()
