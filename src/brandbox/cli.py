"""
brandbox — CLI entry point.

All user-facing output lives here. Core logic is provider-agnostic:
the same process_account loop runs identically for Microsoft and Google.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import questionary
from artty import image_to_braille
from platformdirs import user_data_dir
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from brandbox import __version__, logos, state
from brandbox.logos import LogoSrc
from brandbox.providers import (
    PROVIDER_NAMES,
    Account,
    Provider,
    build_providers,
    get_provider,
)

console = Console()

# ── Data directories ───────────────────────────────────────────────────────────

_DATA_DIR = Path(user_data_dir("brandbox", "brandbox"))
TOKEN_DIR = _DATA_DIR / "tokens"
CACHE_DIR = _DATA_DIR / "cache"
STATE_FILE = _DATA_DIR / "state.json"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
TOKEN_DIR.mkdir(parents=True, exist_ok=True)

# ── Misc constants ─────────────────────────────────────────────────────────────

GRAPH_WRITE_DELAY = 0.25
INBOX_SCAN_LIMIT = 500

PROVIDER_LABELS = {
    "microsoft": "Microsoft 365",
    "google": "Google / Workspace",
}

# ── Config from environment ────────────────────────────────────────────────────


def _ms_client_id() -> str:
    return os.environ.get("BRANDBOX_CLIENT_ID", "")


def _google_creds_path() -> Path:
    env = os.environ.get("BRANDBOX_GOOGLE_CREDENTIALS", "")
    return Path(env) if env else _DATA_DIR / "google_credentials.json"


# ── Rich helpers ───────────────────────────────────────────────────────────────


def _print_banner() -> None:
    console.print()
    console.print(
        Panel(
            Text.from_markup(
                f"[bold]brandbox[/bold]  [dim]v{__version__}[/dim]\n"
                "[dim]Inject company logos into Outlook and Gmail contacts[/dim]"
            ),
            border_style="cyan",
            padding=(0, 2),
            expand=False,
        )
    )
    console.print()


def _print_summary(counts: dict[str, Any], label: str = "") -> None:
    rows = [
        ("set", "green", "✓", "Logos set"),
        ("processed", "dim", "·", "Already processed"),
        ("no_logo", "dim", "·", "No logo available"),
        ("domain", "dim", "·", "Personal email domain"),
        ("no_email", "dim", "·", "No email address"),
        ("failed", "red", "✗", "Upload failed"),
    ]

    table = Table(
        box=box.ROUNDED,
        border_style="dim",
        show_header=False,
        padding=(0, 2),
        expand=False,
        caption=f"[dim]{label}[/dim]" if label else None,
    )
    table.add_column("", no_wrap=True)
    table.add_column("", justify="right", style="bold")

    any_rows = False
    for key, style, icon, label_text in rows:
        v = counts.get(key, 0)
        if not v:
            continue
        table.add_row(
            Text(f"{icon}  {label_text}", style=style),
            Text(str(v), style=style),
        )
        any_rows = True

    if any_rows:
        console.print()
        console.print(table)


def _display_auth_prompt(provider_name: str, auth_info: dict[str, Any]) -> None:
    """Render provider-specific sign-in instructions between start and finish auth."""
    kind = auth_info.get("type")

    if kind == "device_code":
        panel_text = Text()
        panel_text.append("1. Open:  ", style="dim")
        panel_text.append(
            auth_info.get("url", "https://microsoft.com/devicelogin") + "\n",
            style="bold cyan underline",
        )
        if code := auth_info.get("code"):
            panel_text.append("2. Enter: ", style="dim")
            panel_text.append(code, style="bold yellow")
        panel_text.append("\n\nWaiting for sign-in...", style="dim italic")
        console.print(
            Panel(
                panel_text,
                title="[bold]Microsoft Sign In[/bold]",
                border_style="cyan",
                padding=(1, 3),
            )
        )

    elif kind == "browser":
        console.print(
            Panel(
                Text.from_markup(
                    "[dim]A browser window will open for Google sign-in.\n"
                    "If it doesn't open automatically, check your taskbar.[/dim]"
                ),
                title="[bold]Google Sign In[/bold]",
                border_style="cyan",
                padding=(1, 3),
            )
        )


# ── Interactive logo selection ─────────────────────────────────────────────────


def _get_artty_width(console_width: int) -> int:
    """
    Calculate the optimal artty rendering width based on terminal width.

    - If console_width >= 105: return 100 (max width)
    - If console_width >= 25: return console_width - 5 (fit with margin)
    - Otherwise: return 0 (terminal too narrow)
    """
    if console_width >= 105:
        return 100
    elif console_width >= 25:
        return console_width - 5
    else:
        return 0


def _show_logo_preview_and_select(
    results: list[LogoSrc],
    domain: str,
    console: Console,
    progress: Progress,
) -> LogoSrc:
    """
    Display all logo candidates via artty and let user pick one.

    For each LogoSrc in results:
    1. Write PNG bytes to a temp file
    2. Call image_to_braille() to render as braille art
    3. Display in a Rich Panel with a numbered title

    Then use questionary.select() for user to pick.
    Clean up temp files when done.
    """
    tmpdir = None
    try:
        # Pause the progress display
        progress.stop()

        # Create temp directory
        tmpdir = Path(tempfile.mkdtemp(prefix=f"brandbox_{domain}_"))

        # Calculate artty width based on terminal
        artty_width = _get_artty_width(console.width)

        # Print header
        console.print()
        console.rule(f"[bold yellow]Logo candidates for [cyan]{domain}[/cyan][/bold yellow]")
        console.print()

        rendered_displays: list[tuple[int, str, LogoSrc]] = []

        for i, logo_result in enumerate(results):
            slug = (
                logo_result.source.split(":")[0]
                if ":" in logo_result.source
                else logo_result.source
            )

            if artty_width > 0:
                # Write PNG to temp file
                png_path = tmpdir / f"{i}_{slug}.png"
                png_path.write_bytes(logo_result.png)

                # Render via artty
                try:
                    artty_output = image_to_braille(
                        path=str(png_path),
                        width=artty_width,
                        threshold=50,
                        contrast=1.0,
                        sharpness=1.0,
                        crop_padding=30,
                        color=True,
                        transparent="ignore",
                    )
                except Exception:
                    artty_output = f"[red]Failed to render {logo_result.source}[/red]"

                # Display in a panel
                console.print(
                    Panel(
                        artty_output,
                        title=f"[bold]{i + 1}[/bold]. {logo_result.source}",
                        title_align="left",
                        border_style="dim",
                        padding=(0, 1),
                    )
                )
                console.print()
            else:
                # Terminal too narrow for images — fallback to text
                console.print(
                    f"  [bold]{i + 1}.[/bold] {logo_result.source}  [dim]({logo_result.dims})[/dim]"
                )

            rendered_displays.append((i, logo_result.source, logo_result))

        if artty_width == 0:
            console.print(
                f"\n  [yellow]⚠ Terminal too narrow ({console.width}) to render logo images. Minimum 25 columns required.[/yellow]"
            )
            console.print("  [dim]Showing text-only selection.[/dim]\n")

        # Build choices for questionary
        choices = [{"name": r.source, "value": r} for _, _, r in rendered_displays]

        console.print("")  # spacing

        selected = questionary.select(
            f"  Which logo for [bold cyan]{domain}[/bold cyan]?",
            choices=choices,
            qmark="▶",
            pointer="◆",
            use_arrow_keys=True,
            use_emojis=False,
            style=questionary.Style(
                [
                    ("qmark", "fg:yellow bold"),
                    ("question", "bold"),
                    ("answer", "fg:cyan bold"),
                    ("pointer", "fg:cyan bold"),
                    ("highlighted", "fg:cyan bold"),
                    ("selected", "fg:green"),
                ]
            ),
        ).ask()

        if selected is None:
            # User cancelled — pick first as default
            selected = results[0]
            console.print(f"  [dim]No selection made, using: [cyan]{selected.source}[/cyan][/dim]")

        console.print(f"  [green]✓[/green] Selected: [bold]{selected.source}[/bold]")

        return selected

    finally:
        # Clean up temp directory
        if tmpdir is not None and Path(tmpdir).exists():
            shutil.rmtree(tmpdir, ignore_errors=True)
        # Resume progress display
        progress.start()


# ── Core: process one account ──────────────────────────────────────────────────


def _process_account(
    provider: Provider,
    token: str,
    account: Account,
    idx: int,
    total: int,
    app_state: dict[str, Any],
    dry_run: bool = False,
    overwrite: bool = False,
    scan_inbox: bool = False,
    logo_provider: bool = False,
    interactive: bool = False,
) -> dict[str, Any]:

    provider_label = PROVIDER_LABELS.get(provider.name, provider.name)
    console.print()
    console.print(
        Rule(
            f"[bold]{account.username}[/bold]  [dim]{provider_label}  ·  {idx} of {total}[/dim]",
            style="dim",
            align="left",
        )
    )
    console.print()

    account_state: dict[str, str] = app_state.setdefault(account.username, {})
    counts = dict(set=0, processed=0, no_logo=0, domain=0, no_email=0, failed=0)
    added = 0

    # ── 1. Fetch contacts ──────────────────────────────────────────────────────
    with console.status("[dim]Fetching contacts...[/dim]", spinner="dots"):
        contacts = provider.get_contacts(token)
    console.print(f"  [dim]Contacts[/dim]   [bold]{len(contacts)}[/bold] found")

    # ── 2. Scan for new senders ────────────────────────────────────────────────
    if scan_inbox:
        console.print()
        console.print(
            Rule("[bold]Inbox Scan: Creating contacts from recent senders[/bold]", style="cyan")
        )
        console.print()
        with console.status("[dim]Scanning for new senders...[/dim]", spinner="dots"):
            existing_emails = {e.lower() for c in contacts for e in c.emails}
            all_senders = provider.get_recent_senders(token, INBOX_SCAN_LIMIT)
            new_senders = all_senders - existing_emails

        console.print(f"  [dim]New senders[/dim] [bold]{len(new_senders)}[/bold] found")

        if new_senders and not dry_run:
            # Group senders by root domain so logo is fetched once per domain
            domain_senders: dict[str, list[str]] = {}
            for email in sorted(new_senders):
                domain = logos.root_domain(email)
                if not domain or logos.is_personal_domain(domain):
                    if domain is None:
                        counts["no_email"] += 1
                    else:
                        counts["domain"] += 1
                    continue
                domain_senders.setdefault(domain, []).append(email)

            scan_total = sum(len(emails) for emails in domain_senders.values())

            if scan_total > 0:
                scan_progress = Progress(
                    SpinnerColumn(style="cyan"),
                    TextColumn("[bold]{task.description}"),
                    BarColumn(bar_width=30, style="dim", complete_style="cyan"),
                    MofNCompleteColumn(),
                    TimeElapsedColumn(),
                    console=console,
                    transient=False,
                )

                with scan_progress:
                    task = scan_progress.add_task("Creating contacts", total=scan_total)

                    for domain, emails in sorted(domain_senders.items()):
                        logo_result = logos.get_logo(CACHE_DIR, domain)
                        if not logo_result:
                            counts["no_logo"] += len(emails)
                            for _ in emails:
                                scan_progress.update(
                                    task,
                                    advance=1,
                                    description=f"[dim]No logo ({domain})[/dim]",
                                )
                            continue

                        for email in emails:
                            display_name = email.split("@")[0].replace(".", " ").title()
                            scan_progress.update(
                                task,
                                description=f"[dim]{display_name}[/dim] [cyan]{domain}[/cyan]",
                            )

                            cid = provider.create_contact(token, display_name, email)
                            if not cid:
                                counts["failed"] += 1
                                scan_progress.update(task, advance=1)
                                continue

                            if provider.set_contact_photo(token, cid, logo_result.png):
                                account_state[cid] = domain
                                added += 1
                                provider_tag = (
                                    f"  [dim]{logo_result.source}[/dim]" if logo_provider else ""
                                )
                                scan_progress.console.print(
                                    f"  [green]✓[/green]  [bold]{display_name}[/bold]"
                                    f"  [dim cyan]{domain}[/dim cyan]"
                                    f"{provider_tag}"
                                )
                            else:
                                counts["failed"] += 1

                            scan_progress.update(task, advance=1)
                            time.sleep(GRAPH_WRITE_DELAY)

                    scan_progress.update(task, description="[dim]Done[/dim]")

            # Batch-save once after all contacts created
            state.save(STATE_FILE, app_state)
            counts["set"] += added

            console.print(f"  [dim]Created[/dim]    [bold]{added}[/bold] new contacts with logos")

    console.print()
    console.print(
        Rule("[bold]Contact Photos: Setting logos on existing contacts[/bold]", style="cyan")
    )
    console.print()
    if added:
        with console.status("[dim]Refreshing contacts...[/dim]", spinner="dots"):
            contacts = provider.get_contacts(token)

    console.print()

    if not contacts:
        console.print("  [dim]No contacts to process[/dim]")
        _print_summary(counts)
        return counts

    progress = Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=30, style="dim", complete_style="cyan"),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )

    with progress:
        task = progress.add_task("Processing contacts", total=len(contacts))

        for contact in contacts:
            progress.update(
                task,
                description=f"[dim]{contact.display_name[:42]}[/dim]",
                advance=1,
            )

            if not contact.emails:
                counts["no_email"] += 1
                continue

            domain = logos.root_domain(contact.emails[0])

            if not domain or logos.is_personal_domain(domain):
                counts["domain"] += 1
                continue

            if logos.is_known_miss(CACHE_DIR, domain):
                counts["no_logo"] += 1
                continue

            if not overwrite and contact.id in account_state:
                counts["processed"] += 1
                continue

            # ── Dry-run: non-interactive only (short-circuit before fetch) ──
            if dry_run and not interactive:
                progress.console.print(
                    f"  [dim]~[/dim]  [bold]{contact.display_name[:40]}[/bold]"
                    f"  [dim cyan]{domain}[/dim cyan]"
                    f"  [dim italic](dry run)[/dim italic]"
                )
                continue

            # ── Logo fetch (interactive or normal) ──────────────────────────────
            if interactive:
                results = logos.get_all_logos(CACHE_DIR, domain)
                if not results:
                    counts["no_logo"] += 1
                    continue
                elif len(results) == 1:
                    logo_result = results[0]
                    progress.console.print(
                        f"  [dim]~[/dim]  [bold]{contact.display_name[:40]}[/bold]"
                        f"  [dim cyan]{domain}[/dim cyan]"
                        f"  [dim]{logo_result.source}[/dim]  [auto: only 1 source]"
                    )
                    if not dry_run and logo_result.source != "cache":
                        logos._png_path(CACHE_DIR, domain).write_bytes(logo_result.png)
                    provider_tag = f"  [dim]{logo_result.source}[/dim]  [auto: only 1 source]"
                else:
                    logo_result = _show_logo_preview_and_select(results, domain, console, progress)
                    # Cache the selected logo
                    if not dry_run:
                        logos._png_path(CACHE_DIR, domain).write_bytes(logo_result.png)
                    provider_tag = f"  [dim]{logo_result.source}[/dim]  [green]✓ selected[/green]"
            else:
                logo_result = logos.get_logo(CACHE_DIR, domain)
                if not logo_result:
                    counts["no_logo"] += 1
                    continue
                provider_tag = f"  [dim]{logo_result.source}[/dim]" if logo_provider else ""

            # ── Dry-run: skip upload ─────────────────────────────────────────────
            if dry_run:
                continue

            # ── Upload (shared path) ─────────────────────────────────────────────
            if provider.set_contact_photo(token, contact.id, logo_result.png):
                counts["set"] += 1
                account_state[contact.id] = domain
                state.save(STATE_FILE, app_state)
                provider_tag = (
                    f"  [dim]{logo_result.source}[/dim]" if (logo_provider or interactive) else ""
                )
                progress.console.print(
                    f"  [green]✓[/green]  [bold]{contact.display_name[:40]}[/bold]"
                    f"  [dim cyan]{domain}[/dim cyan]"
                    f"{provider_tag}"
                )
            else:
                counts["failed"] += 1
                progress.console.print(
                    f"  [red]✗[/red]  [bold]{contact.display_name[:40]}[/bold]"
                    f"  [dim]{domain}[/dim]  [red dim]upload failed[/red dim]"
                )

            time.sleep(GRAPH_WRITE_DELAY)

        progress.update(task, description="[dim]Done[/dim]")

    _print_summary(counts)
    return counts


# ── CLI ────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="brandbox",
        usage="brandbox [OPTIONS]",
        description="Inject company logos as contact photos in Outlook and Gmail",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  brandbox --add-account                        add a Microsoft 365 account\n"
            "  brandbox --add-account --provider google      add a Google / Workspace account\n"
            "  brandbox --run                                inject logos for all accounts\n"
            "  brandbox --run --scan-inbox                   also add contacts from recent senders\n"
            "  brandbox --run --dry-run                      preview without making changes\n"
            "  brandbox --run --overwrite                    re-process already-completed contacts\n"
            "  brandbox --clear-cache --run                  purge logo cache and re-fetch everything\n"
            "\n"
            "environment variables:\n"
            "  BRANDBOX_CLIENT_ID             Azure App Registration client ID (Microsoft)\n"
            "  BRANDBOX_GOOGLE_CREDENTIALS    path to Google OAuth credentials JSON file\n"
            "\n"
            f"data directory:\n  {_DATA_DIR}\n"
            "\n"
            "docs:\n"
            "  https://github.com/divisionseven/brandbox"
        ),
    )

    parser.add_argument("-V", "--version", action="version", version=f"brandbox {__version__}")
    parser.add_argument("--add-account", action="store_true", help="authenticate a new account")
    parser.add_argument(
        "--provider",
        choices=PROVIDER_NAMES,
        metavar="PROVIDER",
        help=f"provider for --add-account: {', '.join(PROVIDER_NAMES)} (prompted interactively if omitted)",
    )
    parser.add_argument(
        "--list-accounts", action="store_true", help="list all authenticated accounts"
    )
    parser.add_argument("--run", action="store_true", help="inject logos for all accounts")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would change without making any modifications",
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="re-process contacts that already have a logo set"
    )
    parser.add_argument(
        "--scan-inbox",
        action="store_true",
        help="create contacts (with logos) for recent senders not yet in your contacts",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="delete all cached logo files so they are re-fetched on next run",
    )
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help="reset processed-contact state so all contacts are re-evaluated",
    )
    parser.add_argument(
        "--data-dir", action="store_true", help="print the brandbox data directory path and exit"
    )
    parser.add_argument(
        "--logo-provider",
        action="store_true",
        help="show the logo provider name (e.g. [hunter], [simpleicons]) next to each logo",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="when multiple logos found, let you pick interactively",
    )
    args = parser.parse_args()

    _print_banner()

    if args.data_dir:
        console.print(f"  [dim]Data directory:[/dim]  {_DATA_DIR}\n")
        return

    ms_client_id = _ms_client_id()
    google_creds = _google_creds_path()

    # ── --add-account ──────────────────────────────────────────────────────────
    if args.add_account:
        provider_name = args.provider
        if not provider_name:
            console.print("  Which provider would you like to add?\n")
            for key, label in PROVIDER_LABELS.items():
                console.print(f"  [bold cyan]{key}[/bold cyan]  {label}")
            console.print()
            provider_name = Prompt.ask(
                "  Provider",
                choices=PROVIDER_NAMES,
                default="microsoft",
                console=console,
            )

        try:
            provider = get_provider(provider_name, ms_client_id, google_creds, TOKEN_DIR)
        except (RuntimeError, FileNotFoundError) as e:
            console.print(
                Panel(str(e), title="[red]Setup Required[/red]", border_style="red", padding=(1, 2))
            )
            sys.exit(1)

        console.print()
        auth_info = provider.start_auth()
        _display_auth_prompt(provider_name, auth_info)
        username = provider.finish_auth(auth_info)
        console.print(
            f"\n  [green]✓[/green]  [bold]{username}[/bold] authenticated via "
            f"[dim]{PROVIDER_LABELS.get(provider_name, provider_name)}[/dim].\n"
        )
        return

    # ── --list-accounts ────────────────────────────────────────────────────────
    if args.list_accounts:
        all_providers = build_providers(ms_client_id, google_creds, TOKEN_DIR)
        accounts: list[Account] = [acc for p in all_providers.values() for acc in p.get_accounts()]

        if not accounts:
            console.print(
                "  [yellow]No accounts registered.[/yellow] "
                "Run [bold]brandbox --add-account[/bold] first.\n"
            )
        else:
            table = Table(box=box.ROUNDED, border_style="dim", show_header=True, padding=(0, 2))
            table.add_column("#", style="dim", justify="right", width=3)
            table.add_column("Account", style="bold")
            table.add_column("Provider", style="dim")
            for i, acc in enumerate(accounts, 1):
                table.add_row(
                    str(i),
                    acc.username,
                    PROVIDER_LABELS.get(acc.provider_name, acc.provider_name),
                )
            console.print(f"  [dim]Registered accounts[/dim]  [bold]{len(accounts)}[/bold]\n")
            console.print(table)
            console.print()
        return

    # ── --clear-cache ──────────────────────────────────────────────────────────
    if args.clear_cache:
        removed = logos.clear_cache(CACHE_DIR)
        console.print(
            f"  [green]✓[/green]  Cache cleared — [bold]{removed}[/bold] file(s) removed.\n"
        )
        if not (args.run or args.dry_run):
            return

    # ── --reset-state ──────────────────────────────────────────────────────────
    if args.reset_state:
        STATE_FILE.unlink(missing_ok=True)
        console.print(
            "  [green]✓[/green]  State reset — all contacts will be re-evaluated on next run.\n"
        )
        if not (args.run or args.dry_run):
            return

    # ── --run / --dry-run ──────────────────────────────────────────────────────
    if args.run or args.dry_run:
        all_providers = build_providers(ms_client_id, google_creds, TOKEN_DIR)

        if not all_providers:
            console.print(
                Panel(
                    "No providers are configured.\n\n"
                    "For Microsoft 365, set [bold]BRANDBOX_CLIENT_ID[/bold]\n"
                    "For Google, set [bold]BRANDBOX_GOOGLE_CREDENTIALS[/bold]\n\n"
                    "Then run [bold]brandbox --add-account[/bold] to authenticate.",
                    title="[yellow]No Configuration Found[/yellow]",
                    border_style="yellow",
                    padding=(1, 2),
                )
            )
            sys.exit(1)

        all_accounts: list[tuple[Provider, Account]] = [
            (provider, account)
            for provider in all_providers.values()
            for account in provider.get_accounts()
        ]

        if not all_accounts:
            console.print(
                "  [yellow]No accounts registered.[/yellow] "
                "Run [bold]brandbox --add-account[/bold] first.\n"
            )
            sys.exit(1)

        if args.dry_run:
            console.print(
                Panel(
                    "[yellow bold]DRY RUN[/yellow bold] — no changes will be made.",
                    border_style="yellow",
                    padding=(0, 2),
                    expand=False,
                )
            )

        app_state = state.load(STATE_FILE)
        t_start = time.monotonic()
        totals = dict(set=0, processed=0, no_logo=0, domain=0, no_email=0, failed=0)

        try:
            for i, (provider, account) in enumerate(all_accounts, 1):
                try:
                    token = provider.get_token(account)
                    counts = _process_account(
                        provider=provider,
                        token=token,
                        account=account,
                        idx=i,
                        total=len(all_accounts),
                        app_state=app_state,
                        dry_run=args.dry_run,
                        overwrite=args.overwrite,
                        scan_inbox=args.scan_inbox,
                        logo_provider=args.logo_provider,
                        interactive=args.interactive,
                    )
                    for k in totals:
                        totals[k] += counts.get(k, 0)
                except Exception as e:
                    console.print(
                        f"\n  [red]✗[/red]  Error on [bold]{account.username}[/bold]: {e}\n"
                    )
        except KeyboardInterrupt:
            console.print("\n\n  [yellow]Interrupted by user.[/yellow] Exiting...\n")
            sys.exit(130)

        if len(all_accounts) > 1:
            console.print()
            console.print(Rule("[dim]Total across all accounts[/dim]", style="dim"))
            _print_summary(totals)

        elapsed = time.monotonic() - t_start
        mins, secs = divmod(int(elapsed), 60)
        elapsed_str = f"{mins}m {secs}s" if mins else f"{secs}s"

        parts = [
            f"[bold]{len(all_accounts)}[/bold] [dim]account{'s' if len(all_accounts) > 1 else ''}[/dim]",
            f"[green bold]{totals['set']}[/green bold] [dim]logo{'s' if totals['set'] != 1 else ''} set[/dim]",
            f"[dim]{elapsed_str}[/dim]",
        ]
        if totals["failed"]:
            parts.append(f"[red bold]{totals['failed']}[/red bold] [dim]failed[/dim]")

        console.print()
        console.print("  [green]✓[/green]  " + "  ·  ".join(parts))
        console.print()
        return

    parser.print_help()
    console.print()
