# Makefile — QA AI Powered Framework (Python)
# Usage: make <target>

.PHONY: install install-browsers test smoke regression api lint format check generate analyze clean help

# ── Setup ──────────────────────────────────────────────────────────────────────
install:
	pip install -r requirements.txt
	@echo "✅ Dependencies installed"

install-browsers:
	playwright install --with-deps
	@echo "✅ Playwright browsers installed"

setup: install install-browsers
	cp -n .env.example .env || true
	mkdir -p reports tests/generated
	@echo "✅ Project ready — edit .env and add your ANTHROPIC_API_KEY"

# ── Tests ──────────────────────────────────────────────────────────────────────
test:
	mkdir -p reports
	pytest tests/ -v \
		--json-report --json-report-file=reports/results.json \
		--html=reports/report.html --self-contained-html

smoke:
	mkdir -p reports
	pytest tests/ -m smoke -v \
		--json-report --json-report-file=reports/smoke-results.json

regression:
	mkdir -p reports
	pytest tests/ -m regression -v \
		--json-report --json-report-file=reports/regression-results.json

api:
	mkdir -p reports
	pytest tests/api/ -m api -v

# ── Parallel (requires pytest-xdist) ──────────────────────────────────────────
test-parallel:
	mkdir -p reports
	pytest tests/ -n auto -v \
		--json-report --json-report-file=reports/results.json \
		--html=reports/report.html

# ── AI Tools ──────────────────────────────────────────────────────────────────
generate:
	python scripts/generate_tests.py --story stories/auth/login.json

generate-interactive:
	python scripts/generate_tests.py --interactive

analyze:
	python scripts/analyze_failures.py

# ── Code quality ───────────────────────────────────────────────────────────────
lint:
	ruff check src/ tests/ scripts/

format:
	ruff format src/ tests/ scripts/

check: lint
	ruff format --check src/ tests/ scripts/

# ── Cleanup ────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf reports/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	@echo "🧹 Clean!"

# ── Help ───────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  QA AI Powered Framework — Python"
	@echo ""
	@echo "  Setup"
	@echo "    make setup              Install deps + browsers + create .env"
	@echo "    make install            pip install -r requirements.txt"
	@echo "    make install-browsers   playwright install --with-deps"
	@echo ""
	@echo "  Tests"
	@echo "    make test               Run all tests"
	@echo "    make smoke              Smoke tests only"
	@echo "    make regression         Regression suite"
	@echo "    make api                API tests (no browser)"
	@echo "    make test-parallel      All tests in parallel (pytest-xdist)"
	@echo ""
	@echo "  AI Tools"
	@echo "    make generate           Generate tests from stories/auth/login.json"
	@echo "    make generate-interactive  Prompt for story details"
	@echo "    make analyze            Analyse last test failures with AI"
	@echo ""
	@echo "  Code quality"
	@echo "    make lint               Ruff lint check"
	@echo "    make format             Ruff auto-format"
	@echo "    make check              Lint + format check (CI mode)"
	@echo ""
	@echo "  make clean               Remove reports and cache"
	@echo ""
