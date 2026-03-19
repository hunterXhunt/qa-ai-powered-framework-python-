"""
src/utils/data_factory.py

Test data factory — generates isolated, realistic test data.
Uses Faker for realistic values and UUID for guaranteed uniqueness.

Usage:
    factory = DataFactory()
    user = factory.user()
    # → TestUser(email='test-a3f1-user@test.internal', password='TestPass123!', ...)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from faker import Faker

fake = Faker("fr_FR")


@dataclass
class TestUser:
    email: str
    password: str
    first_name: str
    last_name: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    token: str | None = None

    def credentials(self) -> dict[str, str]:
        return {"email": self.email, "password": self.password}

    def registration_payload(self) -> dict[str, str]:
        return {
            "email": self.email,
            "password": self.password,
            "firstName": self.first_name,
            "lastName": self.last_name,
        }


@dataclass
class TestProduct:
    name: str
    price: float
    description: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


class DataFactory:
    """
    Generates unique test data for each test run.
    Each instance has a unique prefix to avoid collisions in parallel execution.
    """

    def __init__(self) -> None:
        # Short unique prefix per test — avoids collisions across parallel workers
        self._prefix = uuid.uuid4().hex[:8]

    # ── Users ─────────────────────────────────────────────────────────────────

    def user(self, **overrides) -> TestUser:
        """Create a unique test user."""
        uid = uuid.uuid4().hex[:6]
        defaults = {
            "email":      f"test-{self._prefix}-{uid}@test.internal",
            "password":   "TestPassword123!",
            "first_name": fake.first_name(),
            "last_name":  fake.last_name(),
        }
        return TestUser(**{**defaults, **overrides})

    def admin_user(self) -> TestUser:
        """Create a test admin user."""
        return self.user(email=f"admin-{self._prefix}@test.internal")

    # ── Strings & values ──────────────────────────────────────────────────────

    def email(self) -> str:
        return f"test-{self._prefix}-{uuid.uuid4().hex[:6]}@test.internal"

    def string(self, prefix: str = "test", length: int = 8) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:length]}"

    def phone(self) -> str:
        return fake.phone_number()

    def sentence(self, nb_words: int = 6) -> str:
        return fake.sentence(nb_words=nb_words)

    def paragraph(self) -> str:
        return fake.paragraph()

    # ── Edge case values ──────────────────────────────────────────────────────

    @staticmethod
    def empty_string() -> str:
        return ""

    @staticmethod
    def long_string(length: int = 256) -> str:
        return "a" * length

    @staticmethod
    def special_chars() -> str:
        return "!@#$%^&*()_+{}|:<>?"

    @staticmethod
    def sql_injection() -> str:
        return "'; DROP TABLE users; --"

    @staticmethod
    def xss_payload() -> str:
        return '<script>alert("xss")</script>'

    @staticmethod
    def unicode_string() -> str:
        return "αβγδεζηθ 中文 العربية"

    # ── Products ──────────────────────────────────────────────────────────────

    def product(self, **overrides) -> TestProduct:
        defaults = {
            "name":        f"Produit Test {uuid.uuid4().hex[:4].upper()}",
            "price":       round(fake.pyfloat(min_value=1, max_value=999, right_digits=2), 2),
            "description": fake.sentence(nb_words=10),
        }
        return TestProduct(**{**defaults, **overrides})

    # ── Timestamps ────────────────────────────────────────────────────────────

    @staticmethod
    def now_iso() -> str:
        return datetime.utcnow().isoformat() + "Z"
