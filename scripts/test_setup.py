#!/usr/bin/env python3
"""Test if the demo environment is properly set up"""

import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Load environment variables from backend/.env first
backend_env_path = Path(__file__).parent.parent / "backend" / ".env"
if backend_env_path.exists():
    load_dotenv(backend_env_path)

console = Console()

def test_setup():
    """Test basic setup requirements"""
    console.print("[bold]Testing GolfDaddy Brain Demo Setup[/bold]\n")
    
    tests = []
    
    # Test API connection
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            tests.append(("Backend API", "✅ Working", "Connected to localhost:8000"))
        else:
            tests.append(("Backend API", f"❌ Status {response.status_code}", "Check backend logs"))
    except Exception as e:
        tests.append(("Backend API", "❌ Not reachable", str(e)[:50]))
    
    # Test frontend
    try:
        response = requests.get("http://localhost:8080", timeout=5)
        tests.append(("Frontend", "✅ Working", "Connected to localhost:8080"))
    except:
        tests.append(("Frontend", "⚠️  Not running", "Run: docker-compose up -d"))
    
    # Check environment variables from backend/.env
    env_path = os.path.join(os.path.dirname(__file__), "..", "backend", ".env")
    if os.path.exists(env_path):
        # Load environment variables
        with open(env_path, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    try:
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
                    except:
                        pass
        
        # Check critical vars
        if os.environ.get("OPENAI_API_KEY", "").startswith("sk-"):
            tests.append(("OpenAI API Key", "✅ Set", "Key configured"))
        else:
            tests.append(("OpenAI API Key", "❌ Missing", "Add to backend/.env"))
        
        if os.environ.get("GITHUB_TOKEN", "").startswith(("ghp_", "github_pat_")):
            tests.append(("GitHub Token", "✅ Set", "Token configured"))
        else:
            tests.append(("GitHub Token", "❌ Missing", "Add to backend/.env"))
    else:
        tests.append(("Environment File", "❌ Not found", f"Missing {env_path}"))
    
    # Display results
    table = Table(title="Setup Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status")
    table.add_column("Notes", style="dim")
    
    for component, status, notes in tests:
        table.add_row(component, status, notes)
    
    console.print(table)
    
    # Summary
    all_good = all("✅" in test[1] for test in tests if "⚠️" not in test[1])
    
    if all_good:
        console.print("\n[green]✅ Your environment is ready![/green]")
        console.print("\nNext steps:")
        console.print("1. Run the quick demo: [bold]python scripts/demo_quick.py[/bold]")
        console.print("2. Or comprehensive demo: [bold]python scripts/demo_golfdaddy.py[/bold]")
        console.print("\nNote: The demo scripts are interactive - run them in a terminal!")
    else:
        console.print("\n[yellow]⚠️  Some components need attention[/yellow]")
        console.print("\nThe demo can still run with partial functionality.")

if __name__ == "__main__":
    test_setup()