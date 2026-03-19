"""
src/generators/test_generator.py

Core AI engine — generates complete Python Playwright pytest files
from a User Story using the Claude API.

Usage:
    generator = TestGenerator()
    result = await generator.generate(story)
    path = result.save("tests/specs/auth/test_login.py")
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .models import GenerationResult, UserStory

console = Console()

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert QA automation engineer specialising in Python, Playwright and pytest.
Your role is to generate complete, production-ready Python test files from User Stories.

## Rules you MUST follow

1. **Framework**: Python + pytest + playwright (sync API via `playwright.sync_api`)
2. **Pattern**: Use Page Object Model — define a lean page class at the top of the file
3. **Structure**: Use pytest classes (`class TestFeatureName`) with `test_` methods
4. **Coverage**: Generate tests for ALL of:
   - Happy path (positive scenarios from each acceptance criterion)
   - Edge cases (boundary values, empty inputs, max lengths)
   - Error scenarios (invalid data, unauthorized access, missing fields)
   - At least one security test (unauthorized access, IDOR) when relevant
5. **Fixtures**: Use pytest fixtures for setup/teardown. Each test must be fully isolated.
6. **Marks**: Apply @pytest.mark.smoke to the most critical test, @pytest.mark.regression to others
7. **Assertions**: Use Playwright's expect() with meaningful failure messages
8. **API shortcuts**: Use `page.request` or `requests` for test setup (faster than UI)
9. **Test names**: Use descriptive French names: `test_redirige_vers_dashboard_apres_connexion_valide`
10. **Docstrings**: Add a one-line docstring to each test method explaining what it verifies

## Template structure
```python
import pytest
from playwright.sync_api import Page, expect

# ── Page Object ───────────────────────────────────────────────────────────────
class LoginPage:
    def __init__(self, page: Page):
        self.page = page
        self.email_input = page.get_by_test_id("email-input")
        ...

    def login(self, email: str, password: str) -> None:
        ...

# ── Tests ─────────────────────────────────────────────────────────────────────
class TestAuthentification:
    @pytest.fixture(autouse=True)
    def setup(self, page: Page):
        self.login_page = LoginPage(page)
        page.goto("/login")

    @pytest.mark.smoke
    def test_redirige_vers_dashboard_apres_connexion_valide(self, page: Page):
        \"\"\"Vérifie la redirection vers le dashboard après connexion réussie.\"\"\"
        ...
```

Return ONLY the Python code — no markdown fences, no explanation, just the .py file content."""


# ── TestGenerator ──────────────────────────────────────────────────────────────

class TestGenerator:
    """Generates Playwright pytest files from User Stories using Claude API."""

    def __init__(self) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set.\n"
                "Copy .env.example to .env and add your key."
            )
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model  = os.getenv("AI_MODEL", "claude-opus-4-6")
        self.max_tokens = int(os.getenv("AI_MAX_TOKENS", "4000"))

    # ── Main generation method ────────────────────────────────────────────────

    def generate(self, story: UserStory) -> GenerationResult:
        """Generate a complete pytest file from a UserStory."""
        self._print_header(story)

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Calling Claude API..."),
            transient=True,
        ) as progress:
            progress.add_task("generate", total=None)
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": story.to_prompt_text()}],
            )

        code = "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()

        # Remove accidental markdown fences
        code = re.sub(r"^```python\s*", "", code)
        code = re.sub(r"^```\s*$", "", code, flags=re.MULTILINE)
        code = code.strip()

        result = GenerationResult(
            code=code,
            test_count=len(re.findall(r"^\s+def test_", code, re.MULTILINE)),
            categories=self._detect_categories(code),
            suggested_path=self._build_path(story),
            model=self.model,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
        )

        self._print_summary(result)
        return result

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _detect_categories(self, code: str) -> list[str]:
        cats: list[str] = []
        lower = code.lower()
        if any(k in lower for k in ["happy path", "cas nominal", "valide", "réussi", "reussie"]):
            cats.append("happy-path")
        if any(k in lower for k in ["edge", "limite", "vide", "invalide", "max", "min"]):
            cats.append("edge-cases")
        if any(k in lower for k in ["erreur", "error", "401", "403", "incorrect", "wrong"]):
            cats.append("error-scenarios")
        if any(k in lower for k in ["security", "sécurité", "idor", "xss", "inject", "unauthorized"]):
            cats.append("security")
        return cats or ["happy-path"]

    def _build_path(self, story: UserStory) -> str:
        slug = re.sub(r"[^a-z0-9\s]", "", story.title.lower())
        slug = re.sub(r"\s+", "_", slug)[:50]
        return f"tests/generated/test_{slug}.py"

    def _print_header(self, story: UserStory) -> None:
        console.print(
            Panel(
                f"[bold]Story:[/bold] {story.title}\n"
                f"[bold]Priority:[/bold] {story.priority.value}   "
                f"[bold]Criteria:[/bold] {len(story.acceptance_criteria)}",
                title="[bold blue]🤖 AI Test Generator",
                border_style="blue",
            )
        )

    def _print_summary(self, result: GenerationResult) -> None:
        table = Table(title="✅ Generation Complete", border_style="green")
        table.add_column("Metric", style="bold")
        table.add_column("Value", style="green")
        table.add_row("Tests generated", str(result.test_count))
        table.add_row("Categories", ", ".join(result.categories))
        table.add_row("Tokens used", str(result.tokens_used))
        table.add_row("Suggested path", result.suggested_path)
        console.print(table)
