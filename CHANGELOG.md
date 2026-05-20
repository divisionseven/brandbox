# Changelog

All notable changes to brandbox are documented here.

This project follows [Semantic Versioning](https://semver.org) and
[Conventional Commits](https://www.conventionalcommits.org).

---

## [0.1.0] — 2026-05-18

### Initial release

- Multi-account Microsoft 365 authentication via MSAL device code flow
- Fetches company logos from LogoKit → Brandfetch → Google favicon (in order)
- Auto-crops transparent pixel padding from logos and re-adds uniform padding
- Root domain extraction via `tldextract` — resolves mail prefixes correctly
  (e.g. `mail.whitehouse.gov` → `whitehouse.gov`)
- Uploads logos as PNG contact photos via Microsoft Graph API
- `--scan-inbox`: creates contacts for recent senders — only if a logo exists
- Local PNG cache and processed-contact state for fast re-runs
- Rich terminal UI with progress bars, spinners, and summary tables
- `--dry-run`, `--overwrite`, `--clear-cache`, `--reset-state` flags
- Platform-aware data directory (`~/Library/Application Support/brandbox` on macOS)

### Added

- Professional test suite with 241 unit tests and 99.47% code coverage
  (state, logos, CLI, Microsoft, Google, base, and provider registry modules)
- GitHub Actions CI workflow (Python 3.11, 3.12, 3.13 with ruff, mypy, pytest)
- pytest and coverage configuration in pyproject.toml (fail_under=90, branch=true)
- shields.io badges for CI status and supported platforms in README

### Changed

- Complete README rewrite with centered header, logo placeholder, badges row,
  navigation links, and ASCII box-drawing flowchart
- Strict type annotations on all function signatures for mypy compliance
- Type annotations in test files for Pyright/Pylance compliance

### Fixed

- `get_recent_senders()` in Microsoft provider now catches `AttributeError`
  when email address value is `None`
