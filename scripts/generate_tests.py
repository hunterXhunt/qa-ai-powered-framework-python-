#!/usr/bin/env python3
"""
scripts/generate_tests.py

CLI tool — generate a Playwright pytest file from a User Story.

Usage:
    python scripts/generate_tests.py --story stories/auth/login.json
    python scripts/generate_tests.py --story stories/auth/login.json --output tests/specs/auth/
    python scripts/generate_tests.py --interactive
    python scripts/generate_tests.py --dry-run --story stories/auth/login.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Prompt
from rich.syntax import Syntax

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from src.generators import TestGenerator, UserStory, Priority

app     = typer.Typer(help="🤖 QA AI Test Generator — generate Playwright tests from User Stories")
console = Console()


@app.command()
def generate(
    story: Path | None = typer.Option(
        None, "--story", "-s",
        help="Path to User Story JSON file",
        exists=False,
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o",
        help="Output directory (default: tests/generated/)",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Print generated code without saving",
    ),
    interactive: bool = typer.Option(
        False, "--interactive", "-i",
        help="Prompt for User Story details interactively",
    ),
) -> None:
    """Generate a complete pytest Playwright test file from a User Story."""

    # Load or build the story
    if interactive:
        us = _prompt_story()
    elif story:
        if not story.exists():
            console.print(f"[red]❌ Story file not found: {story}[/red]")
            raise typer.Exit(1)
        us = UserStory(**json.loads(story.read_text(encoding="utf-8")))
        console.print(f"[green]📖 Loaded story:[/green] {us.title}")
    else:
        console.print("[yellow]ℹ️  No --story provided. Using demo story.[/yellow]")
        us = _demo_story()

    # Generate
    generator = TestGenerator()
    result    = generator.generate(us)

    if dry_run:
        console.print("\n[bold]── Generated Code (dry-run) ──[/bold]")
        console.print(Syntax(result.code, "python", theme="monokai", line_numbers=True))
        return

    # Save
    if output:
        out_path = output / Path(result.suggested_path).name
    else:
        out_path = Path(result.suggested_path)

    saved = result.save(str(out_path))
    console.print(f"\n[bold green]🎉 Done![/bold green] Run your tests with:")
    console.print(f"   [bold]pytest {saved}[/bold]")
    console.print(f"   [dim]pytest {saved} -m smoke  [smoke only][/dim]")


# ── Interactive mode ──────────────────────────────────────────────────────────

def _prompt_story() -> UserStory:
    console.print("\n[bold blue]📝 Interactive User Story Builder[/bold blue]\n")

    title       = Prompt.ask("Story title")
    description = Prompt.ask("Description")
    url         = Prompt.ask("Target URL (e.g. /login)", default="")
    priority    = Prompt.ask("Priority", choices=["P1", "P2", "P3"], default="P2")

    criteria: list[str] = []
    console.print("\n[bold]Acceptance criteria[/bold] (empty line to finish):")
    while True:
        ac = Prompt.ask(f"  AC{len(criteria) + 1}", default="")
        if not ac.strip():
            break
        criteria.append(ac.strip())

    if not criteria:
        console.print("[red]At least one acceptance criterion is required.[/red]")
        raise typer.Exit(1)

    return UserStory(
        title=title,
        description=description,
        acceptanceCriteria=criteria,
        url=url or None,
        priority=Priority(priority),
    )


# ── Demo story ────────────────────────────────────────────────────────────────

def _demo_story() -> UserStory:
    return UserStory(
        title="Inscription utilisateur avec email",
        priority=Priority.P1,
        description=(
            "En tant que visiteur, je veux m'inscrire avec mon email et un mot de passe "
            "pour créer un compte et accéder à l'application."
        ),
        acceptanceCriteria=[
            "L'utilisateur peut s'inscrire avec un email valide et un mot de passe d'au moins 8 caractères",
            "Un email de confirmation est envoyé après l'inscription réussie",
            "Le formulaire affiche une erreur si l'email est déjà utilisé",
            "Le formulaire affiche une erreur si le mot de passe est trop court (< 8 caractères)",
            "Le formulaire affiche une erreur si les deux mots de passe ne correspondent pas",
            "L'utilisateur est redirigé vers le dashboard après inscription réussie",
        ],
        url="/register",
        tags=["smoke", "regression"],
        selectors={
            "emailInput":           "[data-testid='email-input']",
            "passwordInput":        "[data-testid='password-input']",
            "confirmPasswordInput": "[data-testid='confirm-password-input']",
            "submitButton":         "[data-testid='register-btn']",
            "errorMessage":         "[data-testid='error-message']",
        },
    )


if __name__ == "__main__":
    app()
