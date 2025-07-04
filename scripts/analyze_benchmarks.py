#!/usr/bin/env python3
"""
Analyze and visualize benchmark results from commit analysis benchmarking.
This script reads the JSON files created by benchmark_commit_analysis.py
and provides summary statistics and comparisons.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
import statistics
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.prompt import Prompt

console = Console()

def load_benchmark_files(directory: Path) -> List[Dict[str, Any]]:
    """Load all benchmark JSON files from the directory"""
    benchmark_files = list(directory.glob("benchmark_*.json"))
    
    if not benchmark_files:
        console.print(f"[red]No benchmark files found in {directory}[/red]")
        return []
    
    results = []
    for file in sorted(benchmark_files, key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with open(file, 'r') as f:
                data = json.load(f)
                data['filename'] = file.name
                results.append(data)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load {file.name}: {e}[/yellow]")
    
    return results

def analyze_single_benchmark(data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze a single benchmark file and return summary statistics"""
    runs = data.get('runs', [])
    successful_runs = [r for r in runs if 'error' not in r]
    
    if not successful_runs:
        return {'error': 'No successful runs'}
    
    # Extract all metrics
    analysis = {
        'filename': data.get('filename', 'Unknown'),
        'commit': data['commit_data']['sha'][:7],
        'message': data['commit_data']['message'].split('\n')[0][:50],
        'total_runs': len(runs),
        'successful_runs': len(successful_runs),
        'timestamp': data.get('timestamp', 'Unknown'),
    }
    
    # Traditional Hours metrics
    hours = [r['traditional_hours']['ai_estimated_hours'] for r in successful_runs 
             if r['traditional_hours'].get('ai_estimated_hours')]
    if hours and len(hours) > 1:
        analysis['hours_mean'] = statistics.mean(hours)
        analysis['hours_cv'] = (statistics.stdev(hours) / statistics.mean(hours) * 100)
    
    # Impact Points metrics
    impact_scores = [r['impact_points']['total_score'] for r in successful_runs 
                     if r.get('impact_points', {}).get('total_score')]
    if impact_scores and len(impact_scores) > 1:
        analysis['impact_mean'] = statistics.mean(impact_scores)
        analysis['impact_cv'] = (statistics.stdev(impact_scores) / statistics.mean(impact_scores) * 100)
    
    # Risk level consistency
    risk_levels = [r['traditional_hours']['risk_level'] for r in successful_runs 
                   if r['traditional_hours'].get('risk_level')]
    if risk_levels:
        unique_risks = set(risk_levels)
        analysis['risk_consistency'] = len(unique_risks) == 1
        analysis['risk_levels'] = list(unique_risks)
    
    return analysis

def display_benchmark_summary(benchmarks: List[Dict[str, Any]]):
    """Display summary of all benchmarks"""
    console.print("\n[bold]Benchmark Results Summary[/bold]\n")
    
    # Create summary table
    table = Table(title="All Benchmarks", box=box.ROUNDED)
    table.add_column("#", style="cyan", width=3)
    table.add_column("Commit", style="yellow", width=8)
    table.add_column("Message", style="white", width=30)
    table.add_column("Runs", style="green", width=10)
    table.add_column("Hours CV%", style="blue", width=10)
    table.add_column("Impact CV%", style="magenta", width=10)
    table.add_column("Date", style="dim", width=20)
    
    for i, benchmark in enumerate(benchmarks):
        analysis = analyze_single_benchmark(benchmark)
        
        if 'error' in analysis:
            continue
        
        # Format CV% with color coding
        hours_cv = analysis.get('hours_cv', 0)
        impact_cv = analysis.get('impact_cv', 0)
        
        hours_cv_str = format_cv(hours_cv) if hours_cv else "N/A"
        impact_cv_str = format_cv(impact_cv) if impact_cv else "N/A"
        
        table.add_row(
            str(i + 1),
            analysis['commit'],
            analysis['message'] + "...",
            f"{analysis['successful_runs']}/{analysis['total_runs']}",
            hours_cv_str,
            impact_cv_str,
            analysis['timestamp'][:19] if analysis['timestamp'] != 'Unknown' else 'Unknown'
        )
    
    console.print(table)
    
    # Overall statistics
    if benchmarks:
        all_hours_cvs = []
        all_impact_cvs = []
        
        for benchmark in benchmarks:
            analysis = analyze_single_benchmark(benchmark)
            if 'hours_cv' in analysis:
                all_hours_cvs.append(analysis['hours_cv'])
            if 'impact_cv' in analysis:
                all_impact_cvs.append(analysis['impact_cv'])
        
        console.print("\n[bold]Overall Statistics:[/bold]")
        stats_table = Table(box=box.SIMPLE)
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="green")
        
        stats_table.add_row("Total Benchmarks", str(len(benchmarks)))
        stats_table.add_row("Total Commits Analyzed", str(len(set(b['commit_data']['sha'] for b in benchmarks))))
        
        if all_hours_cvs:
            stats_table.add_row("Avg Hours CV%", f"{statistics.mean(all_hours_cvs):.1f}%")
            stats_table.add_row("Best Hours CV%", f"{min(all_hours_cvs):.1f}%")
            stats_table.add_row("Worst Hours CV%", f"{max(all_hours_cvs):.1f}%")
        
        if all_impact_cvs:
            stats_table.add_row("Avg Impact CV%", f"{statistics.mean(all_impact_cvs):.1f}%")
            stats_table.add_row("Best Impact CV%", f"{min(all_impact_cvs):.1f}%")
            stats_table.add_row("Worst Impact CV%", f"{max(all_impact_cvs):.1f}%")
        
        console.print(stats_table)

def format_cv(cv: float) -> str:
    """Format CV% with color coding"""
    if cv < 10:
        return f"[green]{cv:.1f}%[/green]"
    elif cv < 20:
        return f"[yellow]{cv:.1f}%[/yellow]"
    else:
        return f"[red]{cv:.1f}%[/red]"

def show_detailed_analysis(benchmark: Dict[str, Any]):
    """Show detailed analysis of a single benchmark"""
    console.print(f"\n[bold]Detailed Analysis: {benchmark['commit_data']['sha'][:7]}[/bold]")
    console.print(f"Message: {benchmark['commit_data']['message']}")
    console.print(f"Repository: {benchmark['commit_data']['repository']}")
    console.print(f"Author: {benchmark['commit_data']['author']}")
    
    runs = benchmark.get('runs', [])
    successful_runs = [r for r in runs if 'error' not in r]
    
    if not successful_runs:
        console.print("[red]No successful runs to analyze[/red]")
        return
    
    # Show run-by-run comparison
    console.print("\n[bold]Run-by-Run Results:[/bold]")
    
    run_table = Table(box=box.ROUNDED)
    run_table.add_column("Run", style="cyan", width=5)
    run_table.add_column("Hours", style="green", width=8)
    run_table.add_column("Complex", style="yellow", width=8)
    run_table.add_column("Senior", style="blue", width=8)
    run_table.add_column("Risk", style="magenta", width=8)
    run_table.add_column("Biz Val", style="green", width=8)
    run_table.add_column("Tech", style="yellow", width=8)
    run_table.add_column("Impact", style="bold white", width=10)
    
    for run in successful_runs:
        trad = run['traditional_hours']
        impact = run.get('impact_points', {})
        
        risk_color = {"low": "green", "medium": "yellow", "high": "red"}.get(
            trad.get('risk_level', '').lower(), "white"
        )
        
        run_table.add_row(
            str(run['run_index']),
            f"{trad.get('ai_estimated_hours', 0):.1f}",
            f"{trad.get('complexity_score', 0):.0f}",
            f"{trad.get('seniority_score', 0):.0f}",
            f"[{risk_color}]{trad.get('risk_level', 'N/A').upper()[0]}[/{risk_color}]",
            f"{impact.get('business_value', 0):.0f}",
            f"{impact.get('technical_complexity', 0):.0f}",
            f"{impact.get('total_score', 0):.1f}"
        )
    
    console.print(run_table)
    
    # Show reasoning variations
    console.print("\n[bold]Reasoning Consistency:[/bold]")
    
    # Check for unique reasoning patterns
    rationales = [r['reasoning']['seniority_rationale'] for r in successful_runs 
                  if r.get('reasoning', {}).get('seniority_rationale')]
    
    if rationales:
        # Simple check - count unique first sentences
        first_sentences = [r.split('.')[0] for r in rationales if r]
        unique_patterns = len(set(first_sentences))
        
        if unique_patterns == 1:
            console.print("[green]✓ Highly consistent reasoning patterns[/green]")
        elif unique_patterns < len(rationales) / 2:
            console.print("[yellow]⚠ Moderately consistent reasoning patterns[/yellow]")
        else:
            console.print("[red]✗ Inconsistent reasoning patterns[/red]")
        
        # Show a sample reasoning
        if rationales[0]:
            console.print("\n[dim]Sample reasoning from Run 1:[/dim]")
            console.print(Panel(rationales[0][:300] + "...", border_style="dim"))

def main():
    """Main entry point"""
    # Check for benchmark results directory
    results_dir = Path(__file__).parent.parent / "benchmark_results"
    
    if not results_dir.exists():
        console.print("[red]No benchmark_results directory found[/red]")
        console.print("[yellow]Run benchmark_commit_analysis.py first to generate results[/yellow]")
        sys.exit(1)
    
    # Load all benchmark files
    benchmarks = load_benchmark_files(results_dir)
    
    if not benchmarks:
        console.print("[red]No benchmark files found[/red]")
        sys.exit(1)
    
    # Main loop
    while True:
        console.print("\n" + "="*80 + "\n")
        display_benchmark_summary(benchmarks)
        
        console.print("\n[bold]Options:[/bold]")
        console.print("1. View detailed analysis of a benchmark")
        console.print("2. Compare two benchmarks")
        console.print("3. Export summary to CSV")
        console.print("4. Exit")
        
        choice = Prompt.ask("\nSelect option", choices=["1", "2", "3", "4"], default="4")
        
        if choice == "1":
            # View detailed analysis
            idx = Prompt.ask("Enter benchmark number", default="1")
            try:
                benchmark_idx = int(idx) - 1
                if 0 <= benchmark_idx < len(benchmarks):
                    show_detailed_analysis(benchmarks[benchmark_idx])
                else:
                    console.print("[red]Invalid benchmark number[/red]")
            except ValueError:
                console.print("[red]Invalid input[/red]")
        
        elif choice == "2":
            # Compare two benchmarks
            console.print("[yellow]Comparison feature coming soon[/yellow]")
        
        elif choice == "3":
            # Export to CSV
            export_path = results_dir / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            with open(export_path, 'w') as f:
                f.write("Commit,Message,Total Runs,Successful,Hours Mean,Hours CV%,Impact Mean,Impact CV%,Date\n")
                for benchmark in benchmarks:
                    analysis = analyze_single_benchmark(benchmark)
                    if 'error' not in analysis:
                        f.write(f"{analysis['commit']},")
                        f.write(f'"{analysis["message"]}",')
                        f.write(f"{analysis['total_runs']},")
                        f.write(f"{analysis['successful_runs']},")
                        f.write(f"{analysis.get('hours_mean', 'N/A')},")
                        f.write(f"{analysis.get('hours_cv', 'N/A')},")
                        f.write(f"{analysis.get('impact_mean', 'N/A')},")
                        f.write(f"{analysis.get('impact_cv', 'N/A')},")
                        f.write(f"{analysis['timestamp']}\n")
            console.print(f"[green]✓ Summary exported to: {export_path.name}[/green]")
        
        elif choice == "4":
            break
    
    console.print("\n[bold green]Thanks for using the benchmark analyzer![/bold green]")

if __name__ == "__main__":
    main()