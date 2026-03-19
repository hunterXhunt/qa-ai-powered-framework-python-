#!/usr/bin/env python3
"""
scripts/analyze_failures.py

CLI tool — AI-powered analysis of pytest failures.

Usage:
    python scripts/analyze_failures.py
    python scripts/analyze_failures.py --results reports/results.json
    python scripts/analyze_failures.py --output reports/analysis.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from src.analyzers import FailureAnalyzer, report_to_markdown

app     = typer.Typer(help="🔍 QA AI Failure Analyzer — categorise test failures with AI")
console = Console()


@app.command()
def analyze(
    results: Path = typer.Option(
        Path("reports/results.json"),
        "--results", "-r",
        help="Path to pytest-json-report results file",
    ),
    output: Path = typer.Option(
        Path("reports/failure-analysis.md"),
        "--output", "-o",
        help="Output path for the Markdown analysis report",
    ),
) -> None:
    """Analyse pytest failures and categorise them with AI."""

    analyzer = FailureAnalyzer()
    report   = analyzer.analyze(str(results))

    if report.total_failures == 0:
        console.print("[bold green]✅ No failures found — all tests passed![/bold green]")
        return

    # Save markdown report
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report_to_markdown(report), encoding="utf-8")
    console.print(f"\n[bold green]📄 Analysis saved:[/bold green] {output}")

    # Exit with error code if there are real bugs (useful for CI)
    real_bugs = report.by_category.get("real-bug", 0)
    if real_bugs > 0:
        console.print(f"\n[bold red]❌ {real_bugs} real bug(s) detected — review required[/bold red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
