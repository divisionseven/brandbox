# Contributing to BrandBox

First off, thank you for considering contributing. All contributions — bug reports, feature requests, documentation, and code — are welcome.

Before submitting a significant change, please [open an issue](https://github.com/divisionseven/brandbox/issues) first to discuss your approach. This avoids wasted effort on changes that may not align with the project direction.

---

## Getting Started

### Prerequisites

- **Python 3.11 or later**
- **uv** (recommended) or **pip**
- **Git**

### Setup

```bash
git clone https://github.com/divisionseven/brandbox
cd brandbox
uv sync
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows
brandbox --help
```

To install with pip instead:

```bash
pip install -e ".[dev]"
```

Development dependencies include: `pytest`, `pytest-cov`, `pytest-mock`, `ruff`, `mypy`.

---

## Project Structure

```
brandbox/
├── src/
│   └── brandbox/              # Main package source code
│       ├── cli.py             # CLI entry point and argument parsing
│       ├── logos.py           # Logo pipeline and image processing
│       ├── state.py           # Processing state tracking
│       └── providers/         # Provider implementations
│           ├── base.py        # Abstract provider base class
│           ├── microsoft.py   # Microsoft 365 / Outlook provider
│           └── google.py      # Google / Gmail provider
├── tests/
│   ├── conftest.py            # Shared test fixtures
│   └── unit/                  # Unit tests (fully mocked)
│       ├── test_cli.py
│       ├── test_logos.py
│       ├── test_state.py
│       └── providers/
├── docs/                      # Documentation
│   ├── microsoft.md           # Microsoft 365 setup guide
│   ├── google.md              # Google / Gmail setup guide
│   └── how-it-works.md        # Technical deep-dive
├── .github/                   # CI/CD and community files
│   ├── workflows/
│   │   ├── ci.yml             # CI pipeline (lint, type-check, test)
│   │   └── release.yml        # PyPI release workflow
│   ├── ISSUE_TEMPLATE/        # Bug report and feature request templates
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── SECURITY.md            # Security vulnerability reporting
│   └── dependabot.yml
├── pyproject.toml             # Project configuration and tool settings
├── CHANGELOG.md               # Release changelog
├── CONTRIBUTING.md            # This guide
├── README.md                  # Main project README
└── LICENSE                    # MIT License
```

---

## Running Tests

Run the full test suite:

```bash
pytest tests/ -v
```

Run with coverage:

```bash
pytest --tb=short -q --cov=brandbox --cov-report=term-missing tests/
```

Coverage must be **≥90%** (enforced by CI). Tests live in `tests/unit/` and follow the naming convention `test_<module>.py`. The test suite is fully mocked — no real accounts or credentials needed.

---

## Code Style

This project uses strict tooling for consistent code quality.

| Tool   | Command                                     |
| ------ | ------------------------------------------- |
| Linter | `ruff check src/ tests/`                    |
| Format | `ruff format --check src/ tests/`           |
| Auto   | `ruff format src/ tests/`                   |
| Types  | `mypy src/ tests/`                          |

**Rules:** Ruff is configured with rule sets `E`, `F`, `I`, `UP`, `B`.
**Line length:** 100 characters.
**Mypy:** Strict mode enabled.
**Python target:** 3.11+.

### Pre-submit checklist

Before submitting any pull request, run the full suite:

```bash
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/ tests/
pytest tests/ -v
```

All commands must pass cleanly.

---

## Git and Commit Conventions

- **Semantic Versioning** — version follows `MAJOR.MINOR.PATCH` format (see `pyproject.toml` for the current version).
- **Conventional Commits** — commit messages use the form `type(scope): description` in imperative mood, max 72 characters, no trailing period.
- **Keep a Changelog** — all notable changes are documented in `CHANGELOG.md` under `## [Unreleased]`.

### Good commit messages

```
feat(cli): add --dry-run flag for preview mode
fix(logos): render SVGs at 400px instead of viewBox size
docs: add technical deep-dive on logo pipeline
```

---

## Pull Request Process

1. **Open an issue first** for significant changes so the approach can be discussed before work begins.
2. **Clone the repo** and create a branch from `main`.
3. **Make your changes.** Keep the scope focused — a single logical change per PR is preferred.
4. **Run the full lint and test suite** (see pre-submit checklist above).
5. **Update `CHANGELOG.md`** under the `## [Unreleased]` heading.
6. **Update documentation** if your change alters user-facing behavior (`README.md`, docstrings, or files in `docs/`).
7. **Open a pull request** with a clear description of what changed and why.

---

## Authentication for Local Testing

To run brandbox against real accounts (outside the test suite), you will need:

- **Microsoft 365:** Set `BRANDBOX_CLIENT_ID` to your Azure App Registration client ID (see [docs/microsoft.md](docs/microsoft.md)).
- **Google / Gmail:** Set `BRANDBOX_GOOGLE_CREDENTIALS` to the path of your OAuth credentials JSON file (see [docs/google.md](docs/google.md)).

The test suite uses mocks for all provider interactions — **no real accounts are required to run tests.**

---

## Reporting Issues

- **Bug reports:** Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.yml). Include your Python version, operating system, reproduction steps, and expected versus actual behavior.
- **Security vulnerabilities:** Do **not** open a public issue. Report via [GitHub Security Advisories](https://github.com/divisionseven/brandbox/security/advisories) as described in [SECURITY.md](.github/SECURITY.md).
