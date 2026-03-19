"""
src/generators/models.py

Pydantic models for User Story validation and generation result.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Priority(str, Enum):
    P1 = "P1"  # Critical — auth, payment, data loss
    P2 = "P2"  # High — core features
    P3 = "P3"  # Medium — edge cases, cosmetic


class UserStory(BaseModel):
    """Represents a User Story to generate tests from."""

    title: str = Field(..., description="Short title — used as test file name")
    description: str = Field(..., description="Full User Story description")
    acceptance_criteria: list[str] = Field(
        ..., min_length=1, alias="acceptanceCriteria",
        description="List of acceptance criteria (one per item)"
    )
    url: str | None = Field(None, description="Target page URL")
    selectors: dict[str, str] = Field(
        default_factory=dict,
        description="Known CSS/data-testid selectors to use"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Pytest marks e.g. ['smoke', 'regression']"
    )
    priority: Priority = Field(Priority.P2, description="Test priority")

    model_config = {"populate_by_name": True}

    @field_validator("acceptance_criteria")
    @classmethod
    def validate_criteria(cls, v: list[str]) -> list[str]:
        return [ac.strip() for ac in v if ac.strip()]

    def to_prompt_text(self) -> str:
        """Format the story as a clear prompt for Claude."""
        lines = [
            f"## User Story",
            f"**Title:** {self.title}",
            f"**Priority:** {self.priority.value}",
            "",
            f"**Description:**",
            self.description,
            "",
            f"## Acceptance Criteria",
        ]
        for i, ac in enumerate(self.acceptance_criteria, 1):
            lines.append(f"{i}. {ac}")

        if self.url:
            lines += ["", f"## Target URL", self.url]

        if self.selectors:
            lines += ["", "## Known Selectors (use these exactly)"]
            for name, selector in self.selectors.items():
                lines.append(f"- {name}: `{selector}`")

        if self.tags:
            lines += ["", f"## Pytest marks to use", ", ".join(self.tags)]

        lines += [
            "",
            "## Instructions",
            "Generate a complete Python Playwright pytest test file.",
            "Return ONLY the Python code — no markdown fences, no explanation.",
        ]
        return "\n".join(lines)


class GenerationResult(BaseModel):
    """Result of a test generation."""

    code: str
    test_count: int = 0
    categories: list[str] = Field(default_factory=list)
    suggested_path: str = ""
    model: str = ""
    tokens_used: int = 0

    def save(self, output_path: str | None = None) -> str:
        """Save generated code to a file."""
        import os

        path = output_path or self.suggested_path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.code)
        return path


class FailureCategory(str, Enum):
    REAL_BUG   = "real-bug"    # App defect — dev fix needed
    FLAKY      = "flaky"       # Timing / race condition
    ENV_ISSUE  = "env-issue"   # CI/CD environment problem
    TEST_ISSUE = "test-issue"  # Test itself is wrong
    UNKNOWN    = "unknown"


class AnalyzedFailure(BaseModel):
    test_name: str
    file: str
    category: FailureCategory
    confidence: str  # high | medium | low
    root_cause: str
    suggested_fix: str
    priority: Priority


class AnalysisReport(BaseModel):
    analyzed_at: str
    total_failures: int
    by_category: dict[str, int] = Field(default_factory=dict)
    failures: list[AnalyzedFailure] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
