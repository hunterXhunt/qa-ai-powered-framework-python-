"""
conftest.py

Global pytest fixtures — available to all tests without import.

Fixtures provided:
  - page            : Standard Playwright page (from pytest-playwright)
  - browser_context : Extended context with auth state
  - api_client      : Pre-authenticated httpx client
  - factory         : DataFactory instance (unique per test)
  - base_url        : Application base URL from env
  - auth_page       : Page pre-authenticated as test user
"""

from __future__ import annotations

import os
from typing import Generator

import httpx
import pytest
from dotenv import load_dotenv
from playwright.sync_api import Page, BrowserContext, APIRequestContext

from src.utils.data_factory import DataFactory, TestUser

load_dotenv()

# ── Configuration ──────────────────────────────────────────────────────────────

def pytest_configure(config: pytest.Config) -> None:
    """Register custom marks to avoid PytestUnknownMarkWarning."""
    marks = [
        ("smoke",       "Fast smoke tests — run on every push"),
        ("regression",  "Full regression suite"),
        ("api",         "Pure API tests — no browser"),
        ("security",    "Security-focused tests"),
        ("performance", "Performance assertions"),
        ("p1",          "Critical path tests"),
        ("p2",          "High priority tests"),
        ("p3",          "Medium priority tests"),
    ]
    for name, desc in marks:
        config.addinivalue_line("markers", f"{name}: {desc}")


# ── Base fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def base_url() -> str:
    return os.getenv("BASE_URL", "http://localhost:3000")


@pytest.fixture(scope="session")
def api_base_url() -> str:
    return os.getenv("API_BASE_URL", "http://localhost:3001")


@pytest.fixture
def factory() -> DataFactory:
    """Fresh DataFactory per test — unique data per test run."""
    return DataFactory()


# ── Browser configuration ──────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def browser_type_launch_args() -> dict:
    """Playwright browser launch options."""
    return {
        "headless": os.getenv("HEADLESS", "true").lower() == "true",
        "slow_mo": int(os.getenv("SLOW_MO", "0")),
        "args": ["--no-sandbox", "--disable-dev-shm-usage"],
    }


@pytest.fixture(scope="session")
def browser_context_args(base_url: str) -> dict:
    """Browser context options — applied to every test."""
    return {
        "base_url": base_url,
        "viewport": {"width": 1280, "height": 720},
        "locale": "fr-FR",
        "timezone_id": "Europe/Paris",
        "record_video_dir": "reports/videos" if os.getenv("CI") else None,
        "record_har_path": None,
    }


# ── API client fixture ─────────────────────────────────────────────────────────

@pytest.fixture
def api_client(api_base_url: str) -> Generator[httpx.Client, None, None]:
    """Unauthenticated httpx client for API tests."""
    with httpx.Client(
        base_url=api_base_url,
        timeout=10.0,
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture
def auth_api_client(
    api_base_url: str,
    factory: DataFactory,
) -> Generator[tuple[httpx.Client, TestUser], None, None]:
    """Authenticated httpx client — creates a test user, yields (client, user), then cleans up."""
    user = factory.user()

    with httpx.Client(base_url=api_base_url, timeout=10.0) as client:
        # Register
        reg_res = client.post("/api/auth/register", json=user.registration_payload())
        if reg_res.status_code not in (200, 201):
            pytest.skip(f"Could not create test user: {reg_res.text}")

        user.id = reg_res.json().get("id", user.id)

        # Login
        login_res = client.post("/api/auth/login", json=user.credentials())
        if login_res.status_code != 200:
            pytest.skip(f"Could not login test user: {login_res.text}")

        user.token = login_res.json().get("token", "")
        client.headers["Authorization"] = f"Bearer {user.token}"

        yield client, user

        # Cleanup
        client.delete(f"/api/users/{user.id}")


# ── Authenticated page fixture ────────────────────────────────────────────────

@pytest.fixture
def auth_page(
    page: Page,
    api_base_url: str,
    factory: DataFactory,
) -> Generator[tuple[Page, TestUser], None, None]:
    """
    Page pre-authenticated as a test user.
    Creates user via API, injects token into localStorage, then yields (page, user).
    Cleans up the user after the test.
    """
    user = factory.user()

    # Create user via API (faster than UI)
    reg_res = page.request.post(
        f"{api_base_url}/api/auth/register",
        data=user.registration_payload(),
    )
    if not reg_res.ok:
        pytest.skip(f"Could not create test user: {reg_res.text()}")

    user.id = reg_res.json().get("id", user.id)

    # Login via API to get token
    login_res = page.request.post(
        f"{api_base_url}/api/auth/login",
        data=user.credentials(),
    )
    if not login_res.ok:
        pytest.skip(f"Could not login: {login_res.text()}")

    user.token = login_res.json().get("token", "")

    # Inject token into browser storage
    page.add_init_script(f"window.localStorage.setItem('auth_token', '{user.token}')")

    yield page, user

    # Cleanup
    page.request.delete(
        f"{api_base_url}/api/users/{user.id}",
        headers={"Authorization": f"Bearer {user.token}"},
    )


# ── Screenshot on failure ─────────────────────────────────────────────────────

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call):
    """Automatically take a screenshot when a test fails."""
    outcome = yield
    report  = outcome.get_result()

    if report.when == "call" and report.failed:
        page: Page | None = item.funcargs.get("page")
        if page:
            import os
            os.makedirs("reports/screenshots", exist_ok=True)
            safe_name = item.nodeid.replace("/", "_").replace("::", "__")
            try:
                page.screenshot(
                    path=f"reports/screenshots/FAILED_{safe_name}.png",
                    full_page=True,
                )
            except Exception:
                pass  # Don't fail the test over a screenshot error
