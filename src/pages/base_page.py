"""
src/pages/base_page.py

Base Page Object — all page classes inherit from this.
Provides common helpers: goto, fill, click, wait, assert_visible, etc.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect, Locator


class BasePage:
    """Base class for all Page Objects."""

    def __init__(self, page: Page) -> None:
        self.page = page

    # ── Navigation ────────────────────────────────────────────────────────────

    def goto(self, path: str = "") -> None:
        self.page.goto(path)
        self.wait_for_ready()

    def wait_for_ready(self) -> None:
        self.page.wait_for_load_state("networkidle")

    def reload(self) -> None:
        self.page.reload()
        self.wait_for_ready()

    # ── Interaction ───────────────────────────────────────────────────────────

    def fill(self, selector: str, value: str) -> None:
        self.page.locator(selector).fill(value)

    def click(self, selector: str) -> None:
        self.page.locator(selector).click()

    def select_option(self, selector: str, value: str) -> None:
        self.page.locator(selector).select_option(value)

    def check(self, selector: str) -> None:
        self.page.locator(selector).check()

    # ── Assertions ────────────────────────────────────────────────────────────

    def assert_visible(self, selector: str, message: str = "") -> None:
        expect(self.page.locator(selector), message or f"{selector} should be visible").to_be_visible()

    def assert_hidden(self, selector: str) -> None:
        expect(self.page.locator(selector)).to_be_hidden()

    def assert_text(self, selector: str, text: str) -> None:
        expect(self.page.locator(selector)).to_contain_text(text)

    def assert_value(self, selector: str, value: str) -> None:
        expect(self.page.locator(selector)).to_have_value(value)

    def assert_url(self, pattern: str) -> None:
        expect(self.page).to_have_url(pattern)

    def assert_url_contains(self, fragment: str) -> None:
        import re
        expect(self.page).to_have_url(re.compile(re.escape(fragment)))

    def assert_disabled(self, selector: str) -> None:
        expect(self.page.locator(selector)).to_be_disabled()

    def assert_enabled(self, selector: str) -> None:
        expect(self.page.locator(selector)).to_be_enabled()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def get_text(self, selector: str) -> str:
        return self.page.locator(selector).inner_text()

    def is_visible(self, selector: str) -> bool:
        return self.page.locator(selector).is_visible()

    def screenshot(self, name: str) -> None:
        import os
        os.makedirs("reports/screenshots", exist_ok=True)
        self.page.screenshot(path=f"reports/screenshots/{name}.png")
