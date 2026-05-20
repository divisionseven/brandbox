# brandbox

**Stop squinting at colored circles. brandbox automatically injects company logos into your Outlook and Gmail contacts.**

Every version of Outlook and Gmail shows a colored circle with the sender's initials next to their name. brandbox fixes that — it fetches company logos and uploads them as contact photos via the Microsoft Graph API and Google People API. Because it works at the account backend level, logos appear across all your clients automatically: desktop, web, and mobile.

---

## How it works

1. Authenticates each of your accounts via browser login (once per account)
2. Fetches your personal contacts list
3. Extracts the root domain from each contact's email address
4. Downloads the company logo (LogoKit → Brandfetch → Google favicon fallback)
5. Auto-crops any transparent padding baked into the logo file
6. Uploads the processed logo as a contact photo via the provider API
7. Your email client picks it up and shows the logo in your inbox

Logos and processed state are cached locally — re-runs are fast and only process new contacts.

---

## Compatibility

| Provider      | Supported account types                                                |
| ------------- | ---------------------------------------------------------------------- |
| **Microsoft** | Microsoft 365 work/school, Personal/Family, Outlook.com, Hotmail, Live |
| **Google**    | Gmail (personal), Google Workspace (business)                          |

> On-premises Exchange (non-hybrid) and IMAP/POP3 accounts are not supported. If you have Gmail connected inside Outlook, add it separately as a Google provider account — see [Google setup](docs/google.md).

Both providers can run simultaneously. brandbox processes all authenticated accounts in a single `--run`.

---

## Requirements

- Python 3.11+
- A free **Azure App Registration** for Microsoft 365 accounts → [full setup guide](docs/microsoft.md)
- A free **Google Cloud project** for Gmail / Workspace accounts → [full setup guide](docs/google.md)

---

## Installation

**With uv (recommended):**

```bash
uv tool install brandbox
```

**With pip:**

```bash
pip install brandbox
```

**From source:**

```bash
git clone https://github.com/divisionseven/brandbox
cd brandbox
uv sync
uv run brandbox --help
```

---

## Setup

### Microsoft 365

1. [Create an Azure App Registration](docs/microsoft.md) and copy the **client ID**
2. Set the environment variable:

```bash
export BRANDBOX_CLIENT_ID="your-client-id-here"
```

Add to `~/.zshrc` or `~/.zshenv` to persist. See the [Microsoft setup guide](docs/microsoft.md) for the recommended macOS Keychain approach.

### Google / Gmail

1. [Create a Google Cloud project and download OAuth credentials](docs/google.md)
2. Set the path to your credentials file:

```bash
export BRANDBOX_GOOGLE_CREDENTIALS="$HOME/.config/brandbox/google_credentials.json"
```

Add to `~/.zshrc` or `~/.zshenv` to persist.

---

## Usage

### Add an account

```bash
brandbox --add-account
```

You'll be prompted to choose a provider if `--provider` isn't specified. Repeat for each account across both providers.

```bash
brandbox --add-account --provider microsoft
brandbox --add-account --provider google
```

### Run

```bash
brandbox --run
```

Processes all authenticated accounts across all providers in one pass.

### Also create contacts for recent senders

Logos only show for people already in your contacts. This flag finds senders who aren't contacts yet and creates them — but only if a logo can be found first. No logo = no contact created.

```bash
brandbox --run --scan-inbox
```

### Preview without making changes

```bash
brandbox --run --dry-run
```

### Re-process contacts that already have logos

```bash
brandbox --run --overwrite
```

### Refresh all logos

```bash
brandbox --clear-cache --run
```

### All commands

```
brandbox --add-account                       authenticate a new account
brandbox --add-account --provider google     authenticate a Google / Workspace account
brandbox --add-account --provider microsoft  authenticate a Microsoft 365 account
brandbox --list-accounts                     list all authenticated accounts
brandbox --run                               inject logos for all accounts
brandbox --run --dry-run                     preview without making changes
brandbox --run --overwrite                   re-process already-completed contacts
brandbox --run --scan-inbox                  also create contacts from recent senders
brandbox --clear-cache                       delete all cached logos (re-fetched on next run)
brandbox --reset-state                       re-evaluate all contacts on next run
brandbox --data-dir                          show where brandbox stores its data
brandbox --version                           print version
```

---

## After running

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

---

## Data & privacy

All data is stored locally on your machine:

| Platform | Path                                      |
| -------- | ----------------------------------------- |
| macOS    | `~/Library/Application Support/brandbox/` |
| Windows  | `%LOCALAPPDATA%\brandbox\brandbox\`       |
| Linux    | `~/.local/share/brandbox/`                |

Run `brandbox --data-dir` to see the exact path. The data directory contains a logo cache, OAuth tokens, and a processed-contacts state file.

> **Keep the `tokens/` directory private.** It contains OAuth refresh tokens. Never commit it to version control.

brandbox only transmits data to the provider APIs (to set contact photos) and logo APIs (LogoKit, Brandfetch, Google) to fetch images. Nothing else leaves your machine.

---

## Provider docs

- [Microsoft 365 setup guide](docs/microsoft.md)
- [Google / Gmail setup guide](docs/google.md)

---

## Contributing

Contributions are welcome. Please open an issue before submitting a large PR.

```bash
git clone https://github.com/divisionseven/brandbox
cd brandbox
uv sync
uv run brandbox --help
```

```bash
uv run ruff check src/
uv run mypy src/
```

---

## License

[MIT](LICENSE)
