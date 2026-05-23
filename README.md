<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://github.com/divisionseven/brandbox/raw/main/docs/assets/brand/brandbox-social-preview.png">
    <img src="https://github.com/divisionseven/brandbox/raw/main/docs/assets/brand/brandbox-social-preview.png" width="700" alt="Brandbox Logo" />
  </picture>

# BrandBox

### Ditch the generic sender initials, add some branding to your inbox.

[![License: MIT][license-badge-icon]][license-badge-link]
[![Python Versions][python-badge-icon]][python-badge-link]
[![Codecov][codecov-badge-icon]][codecov-badge-link]
[![CI Build][ci-badge-icon]][ci-badge-link]

[![PyPI Version][pypi-version-badge-icon]][github-releases-badge-link]
[![PyPI Downloads][pypi-downloads-badge-icon]][pypi-badge-link]

<p>
  <a href="https://github.com/divisionseven/brandbox/blob/main/docs/microsoft.md">Microsoft Setup</a> &nbsp;·&nbsp; <a href="https://github.com/divisionseven/brandbox/blob/main/docs/google.md">Google Setup</a> &nbsp;·&nbsp; <a href="https://github.com/divisionseven/brandbox/issues">Report Bugs</a> &nbsp;·&nbsp; <a href="https://github.com/divisionseven/brandbox/issues/new">Request Features</a>
</p>

</div>

## Why It Exists

Every version of Outlook and Gmail shows a colored circle with the sender's initials next to their name. When your inbox is full of "JD", "AS", and "MT", you're left squinting at colored circles trying to remember who's who.

**BrandBox fixes that.** It fetches each sender's company logo and uploads it as their contact photo via the Microsoft Graph API and Google People API. It works at the account backend level, so logos propagate everywhere automatically — desktop Outlook, Outlook on the web, Gmail mobile, Google Contacts, and all other connected clients.

**No more colored circles. Just recognizable brand logos in your inbox.**

## Features

| Feature                    | Description                                                                                                                                                                                                                                                                         |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Logo Injection**         | Replaces generic initials with real company logos in Outlook and Gmail                                                                                                                                                                                                              |
| **Cross-Client Sync**      | Logos appear on desktop, web, and mobile — set once at the API level                                                                                                                                                                                                                |
| **Smart Logo Pipeline**    | SVG-first with 7 sources: SimpleIcons → VectorLogo.Zone → Wikimedia Commons → Hunter → DeBounce → LogoKit → Brandfetch. SVGs provide inherent transparency — no white backgrounds in dark-mode Outlook/Gmail. Rasterized at 400×400px via cairosvg for crisp, high-resolution logos |
| **Smart Image Processing** | Auto-crops transparency, scales to fill 200×200 preserving aspect ratio, centers on transparent canvas                                                                                                                                                                              |
| **Multi-Provider**         | Microsoft 365, Outlook.com, Hotmail, Gmail, Google Workspace — all at once                                                                                                                                                                                                          |
| **Local Privacy**          | All data stays on your machine; nothing leaves except API calls for photos                                                                                                                                                                                                          |
| **Incremental Runs**       | Logo cache and contact state tracking make repeat runs near-instant                                                                                                                                                                                                                 |
| **Inbox Scan**             | Optionally creates contacts for recent senders (only when a logo is found)                                                                                                                                                                                                          |
| **Logo Provider Label**    | Optional `--logo-provider` flag shows the logo source (e.g. `[hunter]`, `[simpleicons]`) next to each logo in the progress output                                                                                                                                                   |
| **Scan-Inbox Progress**    | Real-time progress bar with per-sender status, MofN counters, and elapsed time during inbox scan — no more silent waiting                                                                                                                                                           |
| **Interactive Selection**  | When multiple logos are found for a domain, `--interactive` renders each candidate as braille art in the terminal so you can arrow-key pick the best one — no more guessing which source has the right logo                                                                         |

## Compatibility

| Provider      | Supported account types                                                |
| ------------- | ---------------------------------------------------------------------- |
| **Microsoft** | Microsoft 365 work/school, Personal/Family, Outlook.com, Hotmail, Live |
| **Google**    | Gmail (personal), Google Workspace (business)                          |

> [!Note]
> On-premises Exchange (non-hybrid) and IMAP/POP3 accounts are not supported. If you have Gmail connected inside Outlook, add it separately as a Google provider account — see the [Google setup guide][docs-google-link].

Both providers can run simultaneously. brandbox processes all authenticated accounts in a single `--run`.

## Requirements

- **Python 3.11+**
- A free **Azure App Registration** for Microsoft 365 accounts → [Microsoft Setup Guide][docs-microsoft-link]
- A free **Google Cloud project** for Gmail / Workspace accounts → [Google Setup Guide][docs-google-link]

## Installation

### With `uv` (Recommended)

```bash
uv tool install brandbox
```

### With `pip`

```bash
pip install brandbox
```

### From Source

```bash
git clone https://github.com/divisionseven/brandbox
cd brandbox
uv sync
uv run brandbox --help
```

### Verify

```bash
brandbox --version
# Output: brandbox <version>
```

## Setup

<details>
<summary><b>Microsoft 365 Setup</b> — Azure App Registration</summary>

1. Follow the [Microsoft setup guide][docs-microsoft-link] to create an Azure App Registration
2. Copy the **client ID** from the Azure portal
3. Set the environment variable:

```bash
export BRANDBOX_CLIENT_ID="your-client-id-here"
```

Add to `~/.zshrc` or `~/.zshenv` to persist across shell sessions. See the [Microsoft setup guide][docs-microsoft-link] for the recommended macOS Keychain approach.

</details>

<details>
<summary><b>Google / Gmail Setup</b> — Google Cloud Project</summary>

1. Follow the [Google setup guide][docs-google-link] to create a Google Cloud project and download OAuth credentials
2. Set the path to your credentials JSON file:

```bash
export BRANDBOX_GOOGLE_CREDENTIALS="$HOME/.config/brandbox/google_credentials.json"
```

Add to `~/.zshrc` or `~/.zshenv` to persist across shell sessions.

</details>

## Usage

### Add an Account

Authenticate your first account. You'll be prompted to choose a provider:

```bash
brandbox --add-account
```

Or specify the provider directly:

```bash
brandbox --add-account --provider microsoft
brandbox --add-account --provider google
```

A browser window (Google) or device code prompt (Microsoft) will guide you through sign-in. Repeat for each account across both providers.

### List Accounts

```bash
brandbox --list-accounts
```

### Run Logo Injection

Process all authenticated accounts and inject logos:

```bash
brandbox --run
```

**Example Output:**

```
  ┌────────────────────────────────────┐
  │ brandbox  v0.3.0                   │
  │ Add some branding to your inbox!   │
  └────────────────────────────────────┘

  ── you@company.com  ·  Microsoft 365  ·  1 of 1 ───────────────────────

  Contacts   147 found

  Processing contacts ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 147/147 15s
  ✓  Alice Johnson         company.com
  ✓  Bob Smith             acmecorp.com
  ·  Charlie Davis         gmail.com          (personal domain)
  ✓  Eve Williams          example.io
  ...

  ✓  118 set  ·  22 already processed  ·  4 no logo  ·  2 personal domain
```

### Automatically Create Contacts for Recent Senders

Logos only show for people already in your contacts. This flag scans recent inbox senders and creates a contact for each one — but only if a logo can be found first. No logo = no contact created.

```bash
brandbox --run --scan-inbox
```

> [!Note]
> A full `--run` with `--scan-inbox` can take 10+ minutes depending on inbox size and number of contacts.
> So if you are processing a large number of contacts, or a full inbox, please be patient as brandbox works its magic.

### Preview Without Making Changes

```bash
brandbox --run --dry-run
```

### Re-Process Contacts That Already Have Logos

```bash
brandbox --run --overwrite
```

### Show Logo Provider Labels

Shows the source provider (e.g. `[hunter]`, `[simpleicons]`) next to each logo
in the progress output:

```bash
brandbox --run --logo-provider
```

### Interactive Logo Selection

Sometimes a domain has different logo versions out there, and you may have a favorite that you want to use. The `--interactive` flag lets you
see all candidates (if more than one logo was found for a domain), and pick the best one right in the terminal:

```bash
brandbox --run --interactive
```

Each candidate is rendered as braille art (using the `artty` Python API) inside a labelled panel, so you can
visually compare logos before making your choice. Your logo choice for that domain will then be cached and reused like in normal mode.

#### See Interactive Mode in Action

<br>

> [!Note]
> The horizontal scan lines visible in these recordings are an unfortunate side-effect from the screen recorder used and the gif conversion process — they don't appear on the actual terminal output. The braille art renders cleanly without artifacts.

<br>

<div align="center">

**Interactive Logo Selection Example 1: Obsidian**

<a href="https://raw.githubusercontent.com/divisionseven/brandbox/main/docs/assets/screen-recordings/interactive-selection-1.gif" target="_blank">
<img src="https://raw.githubusercontent.com/divisionseven/brandbox/main/docs/assets/screen-recordings/interactive-selection-1.gif" alt="Interactive Logo Selection Example 1: Obsidian" width="700">
</a>
<p><em>The logos displayed above are trademarks or registered trademarks of their respective owners.<br>They are shown here for demonstration purposes only.</em></p>

<br>

**Interactive Logo Selection Example 2: GoDaddy**

<a href="https://raw.githubusercontent.com/divisionseven/brandbox/main/docs/assets/screen-recordings/interactive-selection-2.gif" target="_blank">
<img src="https://raw.githubusercontent.com/divisionseven/brandbox/main/docs/assets/screen-recordings/interactive-selection-2.gif" alt="Interactive Logo Selection Example 2: GoDaddy" width="700">
</a>
<p><em>The logos displayed above are trademarks or registered trademarks of their respective owners.<br>They are shown here for demonstration purposes only.</em></p>

<br>

**Interactive Logo Selection Example 3: Novo**

<a href="https://raw.githubusercontent.com/divisionseven/brandbox/main/docs/assets/screen-recordings/interactive-selection-3.gif" target="_blank">
<img src="https://raw.githubusercontent.com/divisionseven/brandbox/main/docs/assets/screen-recordings/interactive-selection-3.gif" alt="Interactive Logo Selection Example 3: Novo" width="700">
</a>
<p><em>The logos displayed above are trademarks or registered trademarks of their respective owners.<br>They are shown here for demonstration purposes only.</em></p>

</div>

#### How It Works:

1. All 7 logo sources are fetched **in parallel** for each domain
2. If **multiple logos** are found, each is rendered as braille art inside a
   Rich Panel with the source name in the title
3. Use the **↑/↓ arrow keys** to highlight your choice and press **Enter** to
   confirm
4. If **only one logo** is found, it's auto-selected with an
   `[auto: only 1 source]` label — no prompt needed
5. If **no logos** are found, the contact is skipped silently and processing
   continues
6. The chosen logo is cached normally, so interactive mode only appears for
   domains with genuine multi-source choices

> [!Tip]
> Combine with `--logo-provider` for a consistent experience: the source labels
> in the interactive panels match the `[source]` tags shown in the progress
> output during non-interactive runs.

### Refresh All Logos from Scratch

Clears the cached logo files and re-fetches everything on the next run:

```bash
brandbox --clear-cache --run
```

### Reset Processed-Contact State

Forces brandbox to re-evaluate every contact on the next run:

```bash
brandbox --reset-state --run
```

### Show Data Directory

```bash
brandbox --data-dir
```

---

## Full Command Reference

<details>
<summary><b>Click to expand full command reference</b></summary>

| Flag                                 | Description                                                                                      |
| ------------------------------------ | ------------------------------------------------------------------------------------------------ |
| `--add-account`                      | Authenticate a new account                                                                       |
| `--add-account --provider microsoft` | Authenticate a Microsoft 365 account                                                             |
| `--add-account --provider google`    | Authenticate a Google / Workspace account                                                        |
| `--list-accounts`                    | List all authenticated accounts                                                                  |
| `--run`                              | Inject logos for all accounts                                                                    |
| `--run --dry-run`                    | Preview without making changes                                                                   |
| `--run --overwrite`                  | Re-process contacts that already have logos                                                      |
| `--run --scan-inbox`                 | Also create contacts from recent senders (logo required)                                         |
| `--run --logo-provider`              | Show logo source label (e.g. `[hunter]`) next to each logo                                       |
| `--run --interactive`                | Try all 7 logo sources in parallel and visually pick your preferred logo from braille art panels |
| `--clear-cache`                      | Delete all cached logos (re-fetched on next `--run`)                                             |
| `--reset-state`                      | Reset processed-contact state (re-evaluate all contacts)                                         |
| `--data-dir`                         | Show the brandbox data directory path                                                            |
| `--version` / `-V`                   | Print version number                                                                             |

### Environment Variables

| Variable                      | Description                                       |
| ----------------------------- | ------------------------------------------------- |
| `BRANDBOX_CLIENT_ID`          | Azure App Registration client ID (Microsoft auth) |
| `BRANDBOX_GOOGLE_CREDENTIALS` | Path to Google OAuth credentials JSON file        |

</details>

## After Running

Outlook and Gmail cache contact photos and won't show updates until they reload:

| Client              | What to do                                  |
| ------------------- | ------------------------------------------- |
| Outlook for Mac     | Quit fully (`⌘Q`) and reopen                |
| Outlook for Windows | Close fully and reopen                      |
| Outlook on the web  | Hard-refresh (`⌘+Shift+R` / `Ctrl+Shift+R`) |
| Outlook mobile      | Close and reopen the app                    |
| Gmail (web)         | Hard-refresh the page                       |
| Gmail mobile        | Close and reopen the app                    |
| Google Contacts     | Logos appear immediately after running      |

## Data & Privacy

### Logo APIs (No Personal Data)

When fetching company logos, BrandBox sends **only the company domain name** (e.g. `stripe.com`) to these services:

| Service           | Data sent                                                                 |
| ----------------- | ------------------------------------------------------------------------- |
| SimpleIcons CDN   | Domain slug only (`stripe`)                                               |
| VectorLogo.Zone   | Domain slug only (`stripe`)                                               |
| Wikimedia Commons | Domain-based filename lookup. Includes `User-Agent: Brandbox/1.0` header. |
| Hunter.io         | Domain in URL (`stripe.com`)                                              |
| DeBounce          | Domain in URL (`stripe.com`)                                              |
| LogoKit           | Domain in URL (`stripe.com`) + public free-tier token                     |
| Brandfetch        | Domain in URL (`stripe.com`)                                              |

**No authentication tokens, no user identifiers, and no personal data are sent to any logo API.**

### Provider APIs (Your Data, Your Account)

All contact operations go through your authenticated provider account (Google or Microsoft 365) under your own OAuth token. No third party has access to this data.

**Microsoft Graph API** (`Mail.Read`, `Contacts.ReadWrite` scopes):
- **Contacts**: Reads your contact list (`id`, `displayName`, `emailAddresses`). Uploads company logos as contact photos.
- **Inbox scan** (`--scan-inbox`): Reads **only the `from` field** of recent inbox messages to discover new sender email addresses. **Message subjects, bodies, and attachments are never requested or read.**
- **Contact creation**: New contacts are created with a display name and email address, derived from the sender's email (e.g. `john.doe@co.com` → `John Doe`).

**Google People API** (`contacts`, `contacts.other.readonly`, `gmail.readonly` scopes):
- **Contacts**: Reads your contact list (names, email addresses). Uploads company logos as contact photos.
- **Inbox scan** (`--scan-inbox`): Uses the `otherContacts` endpoint — Google's pre-computed list of people you've interacted with. This is populated from your Gmail activity but accessed via the People API, not by reading individual messages.
- **Contact creation**: Same as Microsoft — new contacts created with display name and email.

### Authentication

- **Google**: OAuth 2.0 browser flow via `InstalledAppFlow`. Tokens stored locally in `~/.local/share/brandbox/tokens/` and never shared with third parties.
- **Microsoft**: MSAL device code flow. Tokens cached locally in the same directory.

### Local Storage

All data is stored **locally on your machine** — **none of this data is ever transmitted**:

| File                    | Contents                                                                                      |
| ----------------------- | --------------------------------------------------------------------------------------------- |
| `cache/*.png`           | Downloaded company logos (processed as 200×200 PNGs)                                          |
| `cache/*.miss`          | Empty sentinel files marking domains with no logo (prevents retries)                          |
| `state.json`            | Processing state: which contacts have been processed per account (contact IDs + domains only) |
| `tokens/google_*.json`  | Google OAuth credentials                                                                      |
| `tokens/microsoft.json` | Microsoft MSAL token cache                                                                    |

Platform-specific data directory paths:

| Platform | Path                                      |
| -------- | ----------------------------------------- |
| macOS    | `~/Library/Application Support/brandbox/` |
| Windows  | `%LOCALAPPDATA%\brandbox\brandbox\`       |
| Linux    | `~/.local/share/brandbox/`                |

Run `brandbox --data-dir` to see the exact path.

> [!Important]
> **Keep the `tokens/` directory private.** It contains OAuth refresh tokens. Never share this or commit it to version control.

### Telemetry

**BrandBox does not collect telemetry, analytics, crash reports, or usage data of any kind.** No data is ever sent to services other than the logo APIs and authentication providers listed above. There are no "phone-home" calls, no tracking pixels, and no third-party analytics SDKs.

See our [security documentation][security-docs-link] to report any security issues.

## Testing

```bash
# Using uv (recommended)
uv run pytest tests/ -v

# Using pip
pytest tests/ -v
```

## Documentation

| Document                                   | Description                                                                              |
| ------------------------------------------ | ---------------------------------------------------------------------------------------- |
| [Microsoft 365 Setup][docs-microsoft-link] | How to configure Azure App Registration for Outlook contacts                             |
| [Google Setup][docs-google-link]           | How to configure Google Cloud project for Gmail contacts                                 |
| [How It Works][docs-how-it-works-link]     | Technical deep dive into the logo pipeline, contact discovery, and provider architecture |

## Contributing

Contributions are welcome! Please open an issue before submitting a large PR to discuss your proposed changes.

```bash
git clone https://github.com/divisionseven/brandbox
cd brandbox
uv sync
uv run brandbox --help
```
See our [Contributing Guide][contributing-link].

Run the linter and type checker before submitting:

```bash
uv run ruff check src/
uv run mypy src/
```

## License

Distributed under the [MIT License][license-link].

<!-- Badge Links -->
[python-badge-icon]: https://img.shields.io/pypi/pyversions/brandbox?logo=python&style=plastic&label=Python
[python-badge-link]: https://www.python.org/
[license-badge-icon]: https://img.shields.io/badge/license-MIT-blue?style=plastic&logo=open-source-initiative&label=License
[license-badge-link]: https://opensource.org/licenses/MIT
[codecov-badge-icon]: https://img.shields.io/codecov/c/github/divisionseven/brandbox?logo=codecov&style=plastic&label=Codecov
[codecov-badge-link]: https://app.codecov.io/gh/divisionseven/brandbox
[ci-badge-icon]: https://img.shields.io/github/actions/workflow/status/divisionseven/brandbox/ci.yml?branch=main&logo=github&style=plastic&label=Build
[ci-badge-link]: https://github.com/divisionseven/brandbox/actions/workflows/ci.yml

[pypi-version-badge-icon]: https://img.shields.io/pypi/v/brandbox?style=plastic&logo=pypi&label=Version
[github-releases-badge-link]: https://github.com/divisionseven/brandbox/releases
[pypi-downloads-badge-icon]: https://img.shields.io/pepy/dt/brandbox?style=plastic&logo=pypi&label=Downloads
[pypi-badge-link]: https://pypi.org/project/brandbox/

<!-- Documentation Links -->
[docs-how-it-works-link]: https://github.com/divisionseven/brandbox/blob/main/docs/how-it-works.md
[docs-google-link]: https://github.com/divisionseven/brandbox/blob/main/docs/google.md
[docs-microsoft-link]: https://github.com/divisionseven/brandbox/blob/main/docs/microsoft.md
[contributing-link]: https://github.com/divisionseven/brandbox/blob/main/CONTRIBUTING.md
[security-docs-link]: https://github.com/divisionseven/brandbox/blob/main/.github/SECURITY.md
[license-link]: https://github.com/divisionseven/brandbox/blob/main/LICENSE
