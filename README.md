# 🤖 QA AI-Powered Framework — Python

> **Playwright + Claude API + pytest** — Generate complete test suites from User Stories.  
> Analyse failures automatically. Ship quality faster.

[![CI](https://github.com/micheLange-kouame/qa-ai-powered-framework-python/actions/workflows/ci.yml/badge.svg)](https://github.com/micheLange-kouame/qa-ai-powered-framework-python/actions)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![Playwright](https://img.shields.io/badge/tested%20with-Playwright-45ba4b)](https://playwright.dev/python)
[![Claude API](https://img.shields.io/badge/AI-Claude%20API-orange)](https://anthropic.com)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 🎯 What this does

**Problem:** Writing Playwright tests is repetitive. Analysing CI failures manually is slow.

**Solution:** Two AI-powered tools built on top of the Claude API:

| Tool | Command | What it does |
|---|---|---|
| **Test Generator** | `make generate` | Reads a User Story JSON → generates a complete `test_*.py` file with happy path + edge cases + error scenarios + security tests |
| **Failure Analyzer** | `make analyze` | Reads pytest JSON results → categorises each failure as `real-bug` / `flaky` / `env-issue` / `test-issue` and suggests a fix |

---

## 📁 Project Structure

```
qa-ai-powered-framework-python/
│
├── src/
│   ├── generators/
│   │   ├── models.py            ← Pydantic models (UserStory, GenerationResult, AnalysisReport…)
│   │   └── test_generator.py    ← Core AI engine — TestGenerator class
│   ├── analyzers/
│   │   └── failure_analyzer.py  ← AI failure categorisation — FailureAnalyzer class
│   ├── pages/
│   │   └── base_page.py         ← BasePage — all Page Objects inherit from this
│   └── utils/
│       └── data_factory.py      ← DataFactory — unique, isolated test data per test
│
├── tests/
│   ├── specs/
│   │   └── auth/
│   │       └── test_login.py    ← Example generated spec (13 tests — BDD-style)
│   └── api/
│       └── test_users_api.py    ← Pure API tests (no browser — httpx)
│
├── scripts/
│   ├── generate_tests.py        ← CLI: generate tests from a User Story
│   └── analyze_failures.py      ← CLI: analyse failures with AI
│
├── stories/
│   └── auth/
│       └── login.json           ← Example User Story for the generator
│
├── .github/workflows/
│   └── ci.yml                   ← Full CI pipeline (6 jobs)
│
├── conftest.py                  ← Global pytest fixtures (auth, API client, factory)
├── pyproject.toml               ← Project config + pytest settings + ruff config
├── requirements.txt
├── Makefile                     ← Common commands
└── .env.example
```

---

## 🚀 Quick Start

### 1. Clone & install

```bash
git clone https://github.com/micheLange-kouame/qa-ai-powered-framework-python.git
cd qa-ai-powered-framework-python

# Create virtualenv
python -m venv .venv
source .venv/bin/activate      # Linux/Mac
# .venv\Scripts\activate       # Windows

# Install everything (deps + browsers)
make setup
```

### 2. Configure

```bash
# .env was created by make setup — edit it:
nano .env
```

```env
ANTHROPIC_API_KEY=sk-ant-...      # Required for AI features
BASE_URL=http://localhost:3000    # Your app URL
API_BASE_URL=http://localhost:3001
TEST_USER_EMAIL=test@example.com
TEST_USER_PASSWORD=TestPassword123!
```

Get your API key at [console.anthropic.com](https://console.anthropic.com).

---

### 3. Generate tests from a User Story

```bash
# From a JSON story file
make generate
# or: python scripts/generate_tests.py --story stories/auth/login.json

# Interactive mode — prompts you for story details
make generate-interactive

# Preview without saving
python scripts/generate_tests.py --story stories/auth/login.json --dry-run
```

**Example output:**
```
╭──────────────────────────────────────────────────────╮
│ 🤖 AI Test Generator                                 │
│ Story: Connexion utilisateur avec email et mot passe │
│ Priority: P1   Criteria: 10                          │
╰──────────────────────────────────────────────────────╯
Calling Claude API...

┌─────────────────────────────────────────────────────┐
│               ✅ Generation Complete                  │
├──────────────────┬──────────────────────────────────┤
│ Tests generated  │ 12                               │
│ Categories       │ happy-path, edge-cases, error-.. │
│ Tokens used      │ 1923                             │
│ Suggested path   │ tests/generated/test_connexion.. │
└──────────────────┴──────────────────────────────────┘

🎉 Done! Run your tests with:
   pytest tests/generated/test_connexion_utilisateur.py
   pytest tests/generated/test_connexion_utilisateur.py -m smoke
```

### 4. Run tests

```bash
make test             # All tests
make smoke            # Smoke tests only (~2 min)
make regression       # Full regression suite
make api              # API tests only (no browser)
make test-parallel    # All tests in parallel (pytest-xdist)

# Specific browser
pytest tests/ --browser firefox
pytest tests/ --browser webkit

# Specific test file
pytest tests/specs/auth/test_login.py -v

# By mark
pytest tests/ -m "smoke and not api" -v
```

### 5. Analyse failures

```bash
# Run tests to generate results
pytest tests/ --json-report --json-report-file=reports/results.json

# Analyse with AI
make analyze
# or: python scripts/analyze_failures.py
```

**Example output:**
```
🔍 Analysing 3 failure(s) with AI...

  🐛 [REAL-BUG] test_affiche_erreur_mot_de_passe_incorrect
     → Le message retourné par l'API est "Wrong credentials" mais le test attend "Identifiants invalides"
     Fix: Soit mettre à jour le message dans l'API, soit adapter l'assertion...

  ⚡ [FLAKY] test_redirige_vers_dashboard_apres_connexion_valide
     → Race condition — le token n'est pas encore stocké dans localStorage au moment de la redirection
     Fix: Ajouter page.wait_for_load_state("networkidle") avant l'assertion d'URL...

  🔧 [ENV-ISSUE] test_retourne_401_sans_token
     → La variable API_BASE_URL n'est pas définie dans le CI — les requêtes pointent vers localhost
     Fix: Ajouter API_BASE_URL dans GitHub Secrets/Variables...

┌─────────────────┬───────┐
│ Category        │ Count │
├─────────────────┼───────┤
│ 🐛 real-bug     │   1   │
│ ⚡ flaky        │   1   │
│ 🔧 env-issue    │   1   │
└─────────────────┴───────┘

📄 Analysis saved: reports/failure-analysis.md
```

---

## 📖 User Story JSON format

```json
{
  "title": "Short title — used as test filename",
  "priority": "P1",
  "description": "Full User Story description",
  "url": "/target-page",
  "acceptanceCriteria": [
    "AC1: what the feature must do",
    "AC2: another criterion"
  ],
  "tags": ["smoke", "regression"],
  "selectors": {
    "submitButton": "[data-testid='submit-btn']"
  }
}
```

**Tips for better generation:**
- More specific acceptance criteria → better tests
- Add `selectors` to avoid the AI guessing element names
- Use `"priority": "P1"` for auth/payment — the AI adds more security tests
- Add `"smoke"` tag to tell the AI which test should be in the smoke suite

---

## 🧩 Use the generator programmatically

```python
from src.generators import TestGenerator, UserStory, Priority

generator = TestGenerator()

story = UserStory(
    title="Paiement par carte bancaire",
    priority=Priority.P1,
    description="En tant qu'utilisateur, je veux payer par carte...",
    acceptanceCriteria=[
        "Le paiement réussit avec une carte valide",
        "Un message d'erreur s'affiche si la carte est refusée",
        "Un email de confirmation est envoyé après paiement",
    ],
    url="/checkout/payment",
)

result = generator.generate(story)
print(result.code)          # Generated Python code
print(result.test_count)    # Number of tests
result.save("tests/specs/checkout/test_payment.py")
```

---

## 🧩 Extend the framework

### Add a new Page Object

```python
# src/pages/checkout_page.py
from playwright.sync_api import Page, expect
from src.pages.base_page import BasePage

class CheckoutPage(BasePage):
    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.price_total    = page.get_by_test_id("price-total")
        self.confirm_button = page.get_by_test_id("confirm-order")

    def confirm_order(self) -> None:
        self.confirm_button.click()
        self.wait_for_ready()
```

### Add a new fixture in conftest.py

```python
@pytest.fixture
def checkout_page(page: Page) -> CheckoutPage:
    from src.pages.checkout_page import CheckoutPage
    return CheckoutPage(page)
```

---

## ⚙️ CI/CD Pipeline

```
Lint (ruff)
    ↓
API Tests (httpx, no browser — ~30s)
    ↓
E2E Tests × 3 browsers in parallel (chromium / firefox / webkit)
    ↓
Quality Gate (≥ 90% pass rate — fails build if not met)
    ↓
AI Failure Analysis (only when tests fail — posts summary to PR)
    ↓
Publish HTML Report to GitHub Pages (main branch)
```

**Required GitHub Secrets:**

| Secret | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key for AI analysis |
| `TEST_USER_EMAIL` | Test user email |
| `TEST_USER_PASSWORD` | Test user password |

**Required GitHub Variables:**

| Variable | Description |
|---|---|
| `BASE_URL` | App URL for E2E tests |
| `API_BASE_URL` | API URL for API tests |

---

## 👤 Author

**Michel Ange KOUAME**  
Quality Engineer · ISTQB Foundation & Agile Tester · Île-de-France

📧 michelangeeliek@gmail.com  
🌐 [micheLange-kouame.github.io](https://micheLange-kouame.github.io)  
💼 [LinkedIn](https://linkedin.com/in/michel-ange-elie-kouame-8255a3b1)

---

## 📄 License

MIT — free to use, modify and share.
