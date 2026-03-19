"""
src/analyzers/failure_analyzer.py

AI-powered failure analysis — reads pytest-json-report results,
categorises each failure as: real-bug | flaky | env-issue | test-issue
and suggests a concrete fix for each one.

Usage:
    analyzer = FailureAnalyzer()
    report = analyzer.analyze("reports/results.json")
    report.save_markdown("reports/analysis.md")
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from rich.console import Console
from rich.table import Table

from src.generators.models import (
    AnalysisReport,
    AnalyzedFailure,
    FailureCategory,
    Priority,
)

console = Console()

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert QA engineer analysing pytest + Playwright test failures.
Categorise each failure and suggest a concrete fix.

Categories:
- real-bug    : The application has a genuine defect. The test is correct, the app is wrong.
- flaky       : Non-deterministic — timing, race condition, or shared state issue.
- env-issue   : CI/CD environment problem (network, credentials, missing service, wrong URL).
- test-issue  : The test itself is incorrectly written (wrong selector, wrong assertion, missing wait).
- unknown     : Cannot determine from the available information.

Priority:
- P1: Auth, payment, data loss, security, regression on previously passing feature
- P2: Core feature broken, blocks main user flow
- P3: Minor UI issue, cosmetic, edge case

Respond ONLY with a valid JSON object:
{
  "category": "real-bug|flaky|env-issue|test-issue|unknown",
  "confidence": "high|medium|low",
  "root_cause": "One sentence describing the root cause",
  "suggested_fix": "Concrete fix — Python code snippet if applicable",
  "priority": "P1|P2|P3"
}"""


# ── RawFailure (internal) ─────────────────────────────────────────────────────

class _RawFailure:
    def __init__(
        self,
        test_name: str,
        file: str,
        error: str,
        longrepr: str = "",
    ) -> None:
        self.test_name = test_name
        self.file      = file
        self.error     = error
        self.longrepr  = longrepr


# ── FailureAnalyzer ───────────────────────────────────────────────────────────

class FailureAnalyzer:
    """Categorises pytest failures using Claude API."""

    def __init__(self) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model  = os.getenv("AI_MODEL", "claude-opus-4-6")

    # ── Public API ────────────────────────────────────────────────────────────

    def analyze(self, results_path: str = "reports/results.json") -> AnalysisReport:
        """Read pytest-json-report file and analyse every failure."""
        path = Path(results_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Results file not found: {path}\n"
                "Run tests first: pytest --json-report --json-report-file=reports/results.json"
            )

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        raw_failures = self._extract_failures(data)
        console.print(f"\n[bold blue]🔍 Analysing {len(raw_failures)} failure(s) with AI...[/bold blue]\n")

        analyzed: list[AnalyzedFailure] = []
        for raw in raw_failures:
            result = self._analyze_one(raw)
            analyzed.append(result)
            self._print_failure(result)

        return self._build_report(analyzed)

    def analyze_one(self, test_name: str, error: str, file: str = "") -> AnalyzedFailure:
        """Analyse a single failure directly (useful for integration)."""
        raw = _RawFailure(test_name=test_name, file=file, error=error)
        return self._analyze_one(raw)

    # ── Core analysis ─────────────────────────────────────────────────────────

    def _analyze_one(self, raw: _RawFailure) -> AnalyzedFailure:
        prompt = (
            f"## Failed Test\n"
            f"**Name:** {raw.test_name}\n"
            f"**File:** {raw.file}\n\n"
            f"## Error\n```\n{raw.error[:1200]}\n```\n"
        )
        if raw.longrepr:
            prompt += f"\n## Full Traceback (excerpt)\n```\n{raw.longrepr[:800]}\n```\n"

        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()

        try:
            # Extract JSON even if wrapped in extra text
            import re
            match = re.search(r"\{[\s\S]*\}", text)
            parsed = json.loads(match.group(0) if match else text)
        except Exception:
            parsed = {
                "category": "unknown",
                "confidence": "low",
                "root_cause": "Could not parse AI response",
                "suggested_fix": "Manual investigation required",
                "priority": "P2",
            }

        return AnalyzedFailure(
            test_name=raw.test_name,
            file=raw.file,
            category=FailureCategory(parsed.get("category", "unknown")),
            confidence=parsed.get("confidence", "low"),
            root_cause=parsed.get("root_cause", ""),
            suggested_fix=parsed.get("suggested_fix", ""),
            priority=Priority(parsed.get("priority", "P2")),
        )

    # ── Extract failures from pytest-json-report ──────────────────────────────

    def _extract_failures(self, data: dict) -> list[_RawFailure]:
        failures: list[_RawFailure] = []
        for test in data.get("tests", []):
            if test.get("outcome") not in ("failed", "error"):
                continue
            call = test.get("call", {}) or test.get("setup", {})
            longrepr = test.get("longrepr", "") or ""
            error_msg = ""
            if call.get("crash"):
                error_msg = call["crash"].get("message", "")
            elif isinstance(longrepr, str):
                error_msg = longrepr[:500]

            failures.append(_RawFailure(
                test_name=test.get("nodeid", "unknown"),
                file=test.get("nodeid", "").split("::")[0],
                error=error_msg,
                longrepr=longrepr if isinstance(longrepr, str) else str(longrepr),
            ))
        return failures

    # ── Report builder ────────────────────────────────────────────────────────

    def _build_report(self, failures: list[AnalyzedFailure]) -> AnalysisReport:
        by_cat: dict[str, int] = {c.value: 0 for c in FailureCategory}
        for f in failures:
            by_cat[f.category.value] += 1

        action_items: list[str] = []
        if by_cat["real-bug"]:
            action_items.append(f"🐛 {by_cat['real-bug']} real bug(s) — create Jira tickets")
        if by_cat["flaky"]:
            action_items.append(f"⚡ {by_cat['flaky']} flaky test(s) — add retries or fix expect()")
        if by_cat["env-issue"]:
            action_items.append(f"🔧 {by_cat['env-issue']} env issue(s) — check CI config")
        if by_cat["test-issue"]:
            action_items.append(f"✏️  {by_cat['test-issue']} test issue(s) — fix test code")

        report = AnalysisReport(
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            total_failures=len(failures),
            by_category=by_cat,
            failures=failures,
            action_items=action_items,
        )

        self._print_report_summary(report)
        return report

    # ── Console output ────────────────────────────────────────────────────────

    _EMOJI = {
        "real-bug": "🐛",
        "flaky": "⚡",
        "env-issue": "🔧",
        "test-issue": "✏️",
        "unknown": "❓",
    }

    def _print_failure(self, f: AnalyzedFailure) -> None:
        emoji = self._EMOJI.get(f.category.value, "❓")
        console.print(f"  {emoji} [{f.category.value.upper()}] [bold]{f.test_name}[/bold]")
        console.print(f"     → {f.root_cause}")
        console.print(f"     [dim]Fix: {f.suggested_fix[:100]}...[/dim]\n")

    def _print_report_summary(self, report: AnalysisReport) -> None:
        table = Table(title="📊 Analysis Summary", border_style="blue")
        table.add_column("Category")
        table.add_column("Count", justify="right")
        for cat, count in report.by_category.items():
            if count > 0:
                table.add_row(f"{self._EMOJI.get(cat, '')} {cat}", str(count))
        console.print(table)


# ── Markdown renderer (standalone function) ───────────────────────────────────

def report_to_markdown(report: AnalysisReport) -> str:
    emoji = {
        "real-bug": "🐛", "flaky": "⚡",
        "env-issue": "🔧", "test-issue": "✏️", "unknown": "❓",
    }
    lines = [
        "# 🔍 AI Failure Analysis Report",
        f"> Generated: {report.analyzed_at}",
        "",
        "## Summary",
        "| Category | Count |",
        "|---|---|",
        *[
            f"| {emoji.get(cat, '')} {cat} | **{count}** |"
            for cat, count in report.by_category.items()
        ],
        "",
        "## Action Items",
        *[f"- {a}" for a in report.action_items],
        "",
        "## Detailed Analysis",
    ]
    for f in report.failures:
        lines += [
            "",
            f"### {emoji.get(f.category.value, '')} {f.test_name}",
            f"**File:** `{f.file}`  ",
            f"**Category:** `{f.category.value}`  **Confidence:** {f.confidence}  **Priority:** {f.priority.value}",
            "",
            f"**Root Cause:** {f.root_cause}",
            "",
            "**Suggested Fix:**",
            "```python",
            f.suggested_fix,
            "```",
        ]
    return "\n".join(lines)
