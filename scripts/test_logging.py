#!/usr/bin/env python3
"""Test the enhanced logging in demo scripts"""

import sys
import time
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich import box

console = Console()

def test_visual_elements():
    """Test various visual elements"""
    
    # Test panel
    console.print(Panel.fit(
        "[bold cyan]Testing Visual Elements[/bold cyan]\n\n"
        "This tests the enhanced logging features:\n"
        "• Progress bars\n"
        "• Status indicators\n"
        "• Tables with formatting\n"
        "• Error messages",
        title="🧪 Visual Test",
        border_style="cyan"
    ))
    
    # Test progress bar
    console.print("\n[bold]Testing progress bar:[/bold]")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Processing...", total=30)
        for i in range(30):
            time.sleep(0.05)
            progress.update(task, advance=1)
    
    console.print("[green]✓ Progress complete[/green]")
    
    # Test status
    console.print("\n[bold]Testing status indicator:[/bold]")
    with console.status("[bold green]Loading data...[/bold green]") as status:
        time.sleep(1)
        status.update("[bold yellow]Processing...[/bold yellow]")
        time.sleep(1)
        status.update("[bold cyan]Finalizing...[/bold cyan]")
        time.sleep(1)
    
    console.print("[green]✓ Status test complete[/green]")
    
    # Test table
    console.print("\n[bold]Testing formatted table:[/bold]")
    table = Table(
        title="Sample Analysis Results",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
        title_style="bold blue"
    )
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green", justify="center")
    table.add_column("Visual", style="yellow")
    
    table.add_row("Complexity", "7/10", "███████░░░")
    table.add_row("Quality", "8/10", "████████░░")
    table.add_row("Risk", "LOW", "[green]●[/green]")
    
    console.print(table)
    
    # Test error messages
    console.print("\n[bold]Testing error displays:[/bold]")
    console.print("[red]✗ This is an error message[/red]")
    console.print("[yellow]⚠ This is a warning[/yellow]")
    console.print("[green]✓ This is a success message[/green]")
    console.print("[dim]This is additional context information[/dim]")
    
    console.print("\n[bold green]All visual tests completed![/bold green]")

if __name__ == "__main__":
    test_visual_elements()