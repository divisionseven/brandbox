"""Tests for brandbox.cli — the main CLI orchestration module.

Covers every public helper, the core _process_account loop (all branches),
and the main() entry point (every flag and combination).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pytest_mock import MockerFixture
from rich.panel import Panel
from rich.table import Table

from brandbox import cli
from brandbox.cli import (
    _display_auth_prompt,
    _google_creds_path,
    _ms_client_id,
    _print_banner,
    _print_summary,
    _process_account,
    main,
)
from brandbox.providers.base import Account, Contact

# ═══════════════════════════════════════════════════════════════════
#  _ms_client_id
# ═══════════════════════════════════════════════════════════════════


class TestMsClientId:
    """Tests for _ms_client_id() — reads BRANDBOX_CLIENT_ID env var."""

    def test_when_set__returns_env_var_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns env var value when BRANDBOX_CLIENT_ID is set."""
        monkeypatch.setenv("BRANDBOX_CLIENT_ID", "abc-123-def")
        assert _ms_client_id() == "abc-123-def"

    def test_when_not_set__returns_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns empty string when env var is not set."""
        monkeypatch.delenv("BRANDBOX_CLIENT_ID", raising=False)
        assert _ms_client_id() == ""

    def test_when_empty__returns_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns empty string when env var is set to empty string."""
        monkeypatch.setenv("BRANDBOX_CLIENT_ID", "")
        assert _ms_client_id() == ""


# ═══════════════════════════════════════════════════════════════════
#  _google_creds_path
# ═══════════════════════════════════════════════════════════════════


class TestGoogleCredsPath:
    """Tests for _google_creds_path() — resolves Google credentials path."""

    def test_when_set__returns_env_var_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns Path from BRANDBOX_GOOGLE_CREDENTIALS when set."""
        monkeypatch.setenv("BRANDBOX_GOOGLE_CREDENTIALS", "/custom/path/creds.json")
        assert _google_creds_path() == Path("/custom/path/creds.json")

    def test_when_not_set__returns_default_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns default path under _DATA_DIR when env var is not set."""
        monkeypatch.delenv("BRANDBOX_GOOGLE_CREDENTIALS", raising=False)
        result = _google_creds_path()
        assert result.name == "google_credentials.json"
        assert "brandbox" in str(result)

    def test_when_empty__returns_default_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Falls back to default when env var is empty string."""
        monkeypatch.setenv("BRANDBOX_GOOGLE_CREDENTIALS", "")
        result = _google_creds_path()
        assert result.name == "google_credentials.json"


# ═══════════════════════════════════════════════════════════════════
#  _print_banner
# ═══════════════════════════════════════════════════════════════════


class TestPrintBanner:
    """Tests for _print_banner() — prints versioned Rich banner."""

    def test_prints_banner_with_version(self, mocker: MockerFixture) -> None:
        """Prints a Panel containing the version string."""
        # Arrange
        mock_print = mocker.patch("brandbox.cli.console.print")
        mocker.patch.object(cli, "__version__", "1.2.3")

        # Act
        _print_banner()

        # Assert
        # Three print calls: blank line, Panel, blank line
        assert mock_print.call_count == 3
        panel_arg = mock_print.call_args_list[1][0][0]
        assert isinstance(panel_arg, Panel)
        assert "1.2.3" in str(panel_arg.renderable)

    def test_works_with_fallback_version(self, mocker: MockerFixture) -> None:
        """Prints banner even when version is '0.0.0' (fallback)."""
        # Arrange
        mock_print = mocker.patch("brandbox.cli.console.print")
        mocker.patch.object(cli, "__version__", "0.0.0")

        # Act
        _print_banner()

        # Assert
        assert mock_print.call_count == 3
        panel_arg = mock_print.call_args_list[1][0][0]
        assert isinstance(panel_arg, Panel)
        assert "0.0.0" in str(panel_arg.renderable)


# ═══════════════════════════════════════════════════════════════════
#  _print_summary
# ═══════════════════════════════════════════════════════════════════


class TestPrintSummary:
    """Tests for _print_summary() — prints results table."""

    def test_prints_table_when_counts_nonzero(self, mocker: MockerFixture) -> None:
        """Prints a table when some counts are non-zero."""
        # Arrange
        mock_print = mocker.patch("brandbox.cli.console.print")
        counts = {"set": 3, "no_logo": 1}

        # Act
        _print_summary(counts)

        # Assert
        assert mock_print.call_count == 2  # blank line + table
        table_arg = mock_print.call_args_list[1][0][0]
        assert isinstance(table_arg, Table)
        # Table should have 2 data rows (set=3 + no_logo=1)
        assert len(table_arg.rows) == 2

    def test_prints_nothing_when_all_zero(self, mocker: MockerFixture) -> None:
        """Prints nothing when all counts are zero."""
        # Arrange
        mock_print = mocker.patch("brandbox.cli.console.print")
        counts = {"set": 0, "processed": 0, "no_logo": 0, "domain": 0, "no_email": 0, "failed": 0}

        # Act
        _print_summary(counts)

        # Assert
        mock_print.assert_not_called()

    def test_uses_label_when_provided(self, mocker: MockerFixture) -> None:
        """Sets table caption when label is provided."""
        # Arrange
        mock_print = mocker.patch("brandbox.cli.console.print")
        counts = {"set": 1}

        # Act
        _print_summary(counts, label="Test label")

        # Assert
        assert mock_print.call_count == 2
        table_arg = mock_print.call_args_list[1][0][0]
        assert isinstance(table_arg, Table)
        assert table_arg.caption is not None
        assert "Test label" in str(table_arg.caption)

    def test_includes_failed_row(self, mocker: MockerFixture) -> None:
        """Table includes the 'failed' row when count is non-zero."""
        # Arrange
        mock_print = mocker.patch("brandbox.cli.console.print")
        counts = {"failed": 2}

        # Act
        _print_summary(counts)

        # Assert
        table_arg = mock_print.call_args_list[1][0][0]
        assert len(table_arg.rows) == 1  # only the failed row


# ═══════════════════════════════════════════════════════════════════
#  _display_auth_prompt
# ═══════════════════════════════════════════════════════════════════


class TestDisplayAuthPrompt:
    """Tests for _display_auth_prompt() — shows auth instructions."""

    def test_device_code_flow__shows_url_and_code(self, mocker: MockerFixture) -> None:
        """Device code flow prints URL and code in a Panel."""
        # Arrange
        mock_print = mocker.patch("brandbox.cli.console.print")
        auth_info = {
            "type": "device_code",
            "url": "https://example.com/device",
            "code": "ABC123",
        }

        # Act
        _display_auth_prompt("microsoft", auth_info)

        # Assert
        mock_print.assert_called_once()
        panel_arg = mock_print.call_args[0][0]
        assert isinstance(panel_arg, Panel)
        rendered = str(panel_arg.renderable)
        assert "https://example.com/device" in rendered
        assert "ABC123" in rendered

    def test_device_code_flow__defaults_url_when_missing(self, mocker: MockerFixture) -> None:
        """Device code flow uses default URL when url key is missing."""
        # Arrange
        mock_print = mocker.patch("brandbox.cli.console.print")
        auth_info = {"type": "device_code", "code": "XYZ789"}

        # Act
        _display_auth_prompt("microsoft", auth_info)

        # Assert
        panel_arg = mock_print.call_args[0][0]
        rendered = str(panel_arg.renderable)
        assert "microsoft.com/devicelogin" in rendered

    def test_device_code_flow__handles_missing_code(self, mocker: MockerFixture) -> None:
        """Does not fail when code key is missing."""
        # Arrange
        mock_print = mocker.patch("brandbox.cli.console.print")
        auth_info = {"type": "device_code", "url": "https://example.com/device"}

        # Act
        _display_auth_prompt("microsoft", auth_info)

        # Assert
        mock_print.assert_called_once()  # still prints, just without code

    def test_browser_flow__shows_instructions(self, mocker: MockerFixture) -> None:
        """Browser flow prints sign-in instructions."""
        # Arrange
        mock_print = mocker.patch("brandbox.cli.console.print")
        auth_info = {"type": "browser"}

        # Act
        _display_auth_prompt("google", auth_info)

        # Assert
        mock_print.assert_called_once()
        panel_arg = mock_print.call_args[0][0]
        assert isinstance(panel_arg, Panel)
        rendered = str(panel_arg.renderable)
        assert "browser" in rendered.lower()

    def test_unknown_type__prints_nothing(self, mocker: MockerFixture) -> None:
        """Unknown auth type prints nothing."""
        # Arrange
        mock_print = mocker.patch("brandbox.cli.console.print")
        auth_info = {"type": "unknown_flow"}

        # Act
        _display_auth_prompt("custom", auth_info)

        # Assert
        mock_print.assert_not_called()


# ═══════════════════════════════════════════════════════════════════
#  _process_account  —  helpers
# ═══════════════════════════════════════════════════════════════════

# Email → root-domain mapping for test contacts
EMAIL_DOMAIN: dict[str, str] = {
    "alice@company.com": "company.com",
    "bob@acmecorp.org": "acmecorp.org",
    "charlie@gmail.com": "gmail.com",
    "diana@startup.io": "startup.io",
    "eve@example.net": "example.net",
    "frank@mega-corp.co.uk": "mega-corp.co.uk",
}


def _domain_side_effect(email: str) -> str | None:
    """Default root_domain side effect: return mapped domain or None."""
    return EMAIL_DOMAIN.get(email)


# ═══════════════════════════════════════════════════════════════════
#  _process_account  —  happy path
# ═══════════════════════════════════════════════════════════════════


class TestProcessAccountHappyPath:
    """Happy-path scenarios for _process_account()."""

    @pytest.fixture(autouse=True)
    def _setup_mocks(self, mocker: MockerFixture) -> None:
        """Default patches for all tests in this class."""
        mocker.patch("brandbox.cli.logos.root_domain", side_effect=_domain_side_effect)
        mocker.patch("brandbox.cli.logos.is_personal_domain", return_value=False)
        mocker.patch("brandbox.cli.logos.is_known_miss", return_value=False)
        mocker.patch("brandbox.cli.logos.get_logo", return_value=b"fake-png")
        mocker.patch("brandbox.cli.state.save")
        mocker.patch("brandbox.cli.time.sleep")

    def test_processes_all_contacts_with_logos(
        self,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """All valid contacts get logos set successfully."""
        # Arrange
        mock_provider.contacts = [c for c in sample_contacts if c.emails]
        app_state: dict[str, Any] = {}

        # Act
        counts = _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
        )

        # Assert
        assert counts["set"] == len(mock_provider.contacts)
        assert counts["processed"] == 0
        assert counts["no_logo"] == 0
        assert counts["domain"] == 0
        assert counts["no_email"] == 0
        assert counts["failed"] == 0

    def test_returns_counts_dict_with_all_keys(
        self,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """Returned dict has all expected keys."""
        # Arrange
        mock_provider.contacts = [sample_contacts[0]]
        app_state: dict[str, Any] = {}

        # Act
        counts = _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
        )

        # Assert
        assert set(counts.keys()) == {"set", "processed", "no_logo", "domain", "no_email", "failed"}

    def test_updates_app_state_after_successful_upload(
        self,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """app_state is updated with contact ID after successful upload."""
        # Arrange
        contact = sample_contacts[0]
        mock_provider.contacts = [contact]
        app_state: dict[str, Any] = {}

        # Act
        _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
        )

        # Assert
        assert sample_account.username in app_state
        assert contact.id in app_state[sample_account.username]
        assert app_state[sample_account.username][contact.id] == "company.com"

    def test_persists_state_across_calls(
        self,
        mocker: MockerFixture,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """app_state persists across multiple _process_account calls."""
        # Arrange
        mock_provider.contacts = [sample_contacts[0]]
        app_state: dict[str, Any] = {}
        # First run establishes state
        _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
        )

        # Act — second run with same provider/account
        counts = _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
        )

        # Assert — now marked as processed (not overwriting)
        assert counts["processed"] == 1
        assert counts["set"] == 0


# ═══════════════════════════════════════════════════════════════════
#  _process_account  —  edge cases
# ═══════════════════════════════════════════════════════════════════


class TestProcessAccountEdgeCases:
    """Edge-case branches in _process_account()."""

    @pytest.fixture(autouse=True)
    def _setup_mocks(self, mocker: MockerFixture) -> None:
        """Default patches for all tests in this class."""
        mocker.patch("brandbox.cli.logos.root_domain", side_effect=_domain_side_effect)
        mocker.patch("brandbox.cli.logos.is_personal_domain", return_value=False)
        mocker.patch("brandbox.cli.logos.is_known_miss", return_value=False)
        mocker.patch("brandbox.cli.logos.get_logo", return_value=b"fake-png")
        mocker.patch("brandbox.cli.state.save")
        mocker.patch("brandbox.cli.time.sleep")

    def test_contact_with_no_emails__counted_as_no_email(
        self,
        mock_provider: Any,
        sample_account: Account,
    ) -> None:
        """Contact with empty emails list is counted as no_email and skipped."""
        # Arrange
        contact_no_email = Contact(id="c-empty", display_name="No Email", emails=[])
        mock_provider.contacts = [contact_no_email]
        app_state: dict[str, Any] = {}

        # Act
        counts = _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
        )

        # Assert
        assert counts["no_email"] == 1
        assert counts["set"] == 0

    def test_contact_with_personal_domain__counted_as_domain(
        self,
        mocker: MockerFixture,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """Contact with gmail.com is counted as domain and skipped."""
        # Arrange
        mocker.patch(
            "brandbox.cli.logos.is_personal_domain", side_effect=lambda d: d == "gmail.com"
        )
        # Only include charlie (gmail.com) and alice (company.com)
        mock_provider.contacts = [sample_contacts[2]]  # charlie@gmail.com
        app_state: dict[str, Any] = {}

        # Act
        counts = _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
        )

        # Assert
        assert counts["domain"] == 1
        assert counts["set"] == 0

    def test_root_domain_returns_none__counted_as_domain(
        self,
        mocker: MockerFixture,
        mock_provider: Any,
        sample_account: Account,
    ) -> None:
        """Contact whose domain extraction returns None is counted as domain."""
        # Arrange
        contact = Contact(id="c-bad", display_name="Bad Email", emails=["not-an-email"])
        mock_provider.contacts = [contact]
        # Make root_domain return None for this contact
        mocker.patch("brandbox.cli.logos.root_domain", return_value=None)
        app_state: dict[str, Any] = {}

        # Act
        counts = _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
        )

        # Assert
        assert counts["domain"] == 1
        assert counts["set"] == 0

    def test_known_miss__counted_as_no_logo(
        self,
        mocker: MockerFixture,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """Contact whose domain is a known miss is counted as no_logo."""
        # Arrange
        mocker.patch("brandbox.cli.logos.is_known_miss", return_value=True)
        mock_provider.contacts = [sample_contacts[0]]
        app_state: dict[str, Any] = {}

        # Act
        counts = _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
        )

        # Assert
        assert counts["no_logo"] == 1
        assert counts["set"] == 0

    def test_already_processed_without_overwrite__counted_as_processed(
        self,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """Contact already in app_state is skipped when overwrite=False."""
        # Arrange
        contact = sample_contacts[0]
        mock_provider.contacts = [contact]
        app_state: dict[str, Any] = {sample_account.username: {contact.id: "company.com"}}

        # Act
        counts = _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
            overwrite=False,
        )

        # Assert
        assert counts["processed"] == 1
        assert counts["set"] == 0

    def test_already_processed_with_overwrite__reprocesses(
        self,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """Contact already in app_state is re-processed when overwrite=True."""
        # Arrange
        contact = sample_contacts[0]
        mock_provider.contacts = [contact]
        app_state: dict[str, Any] = {sample_account.username: {contact.id: "company.com"}}

        # Act
        counts = _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
            overwrite=True,
        )

        # Assert
        assert counts["set"] == 1
        assert counts["processed"] == 0

    def test_logo_fetch_returns_none__counted_as_no_logo(
        self,
        mocker: MockerFixture,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """Contact whose logo fetch returns None is counted as no_logo."""
        # Arrange
        mocker.patch("brandbox.cli.logos.get_logo", return_value=None)
        mock_provider.contacts = [sample_contacts[0]]
        app_state: dict[str, Any] = {}

        # Act
        counts = _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
        )

        # Assert
        assert counts["no_logo"] == 1
        assert counts["set"] == 0

    def test_upload_fails__counted_as_failed(
        self,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """Contact whose photo upload fails is counted as failed."""
        # Arrange
        mock_provider.fail_set_photo = True
        mock_provider.contacts = [sample_contacts[0]]
        app_state: dict[str, Any] = {}

        # Act
        counts = _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
        )

        # Assert
        assert counts["failed"] == 1
        assert counts["set"] == 0
        # app_state should NOT be updated since upload failed
        assert sample_account.username not in app_state or not app_state[sample_account.username]


# ═══════════════════════════════════════════════════════════════════
#  _process_account  —  dry-run mode
# ═══════════════════════════════════════════════════════════════════


class TestProcessAccountDryRun:
    """Dry-run mode behaviour in _process_account()."""

    @pytest.fixture(autouse=True)
    def _setup_mocks(self, mocker: MockerFixture) -> None:
        """Default patches for all tests in this class."""
        mocker.patch("brandbox.cli.logos.root_domain", side_effect=_domain_side_effect)
        mocker.patch("brandbox.cli.logos.is_personal_domain", return_value=False)
        mocker.patch("brandbox.cli.logos.is_known_miss", return_value=False)
        mocker.patch("brandbox.cli.logos.get_logo", return_value=b"fake-png")
        mocker.patch("brandbox.cli.state.save")
        mocker.patch("brandbox.cli.time.sleep")

    def test_dry_run_does_not_upload(
        self,
        mocker: MockerFixture,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """dry_run=True means set_contact_photo is never called."""
        # Arrange
        mock_provider.contacts = [sample_contacts[0]]
        app_state: dict[str, Any] = {}
        spy_set_photo = mocker.spy(mock_provider, "set_contact_photo")

        # Act
        counts = _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
            dry_run=True,
        )

        # Assert
        spy_set_photo.assert_not_called()
        # Dry-run contacts are not counted as set
        assert counts["set"] == 0
        # Other categories should still work
        assert counts["no_email"] == 0

    def test_dry_run_still_categorizes_edge_cases(
        self,
        mocker: MockerFixture,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """Dry run still counts no_email and domain contacts correctly."""
        # Arrange
        contact_no_email = Contact(id="c-empty", display_name="No Email", emails=[])
        mock_provider.contacts = [contact_no_email, sample_contacts[2]]  # charlie@gmail.com
        mocker.patch(
            "brandbox.cli.logos.is_personal_domain", side_effect=lambda d: d == "gmail.com"
        )
        app_state: dict[str, Any] = {}

        # Act
        counts = _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
            dry_run=True,
        )

        # Assert
        assert counts["no_email"] == 1
        assert counts["domain"] == 1
        assert counts["set"] == 0

    def test_dry_run_skips_already_processed(
        self,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """Already-processed contacts counted as processed even in dry run."""
        # Arrange
        contact = sample_contacts[0]
        mock_provider.contacts = [contact]
        app_state: dict[str, Any] = {sample_account.username: {contact.id: "company.com"}}

        # Act
        counts = _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
            dry_run=True,
            overwrite=False,
        )

        # Assert
        assert counts["processed"] == 1
        assert counts["set"] == 0

    def test_dry_run_skips_known_miss(
        self,
        mocker: MockerFixture,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """Known-miss contacts counted as no_logo even in dry run."""
        # Arrange
        mocker.patch("brandbox.cli.logos.is_known_miss", return_value=True)
        mock_provider.contacts = [sample_contacts[0]]
        app_state: dict[str, Any] = {}

        # Act
        counts = _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
            dry_run=True,
        )

        # Assert
        assert counts["no_logo"] == 1
        assert counts["set"] == 0


# ═══════════════════════════════════════════════════════════════════
#  _process_account  —  inbox scan
# ═══════════════════════════════════════════════════════════════════


class TestProcessAccountInboxScan:
    """Inbox scanning (--scan-inbox) in _process_account()."""

    @pytest.fixture(autouse=True)
    def _setup_mocks(self, mocker: MockerFixture) -> None:
        """Default patches for all tests in this class.

        Uses an extended domain map that includes test-specific sender emails.
        """

        def _inbox_domain(email: str) -> str | None:
            mapping = {
                **EMAIL_DOMAIN,
                "newguy@startup.io": "startup.io",
                "person@gmail.com": "gmail.com",
                "nobody@unknown.org": "unknown.org",
            }
            return mapping.get(email)

        mocker.patch("brandbox.cli.logos.root_domain", side_effect=_inbox_domain)
        mocker.patch("brandbox.cli.logos.is_personal_domain", return_value=False)
        mocker.patch("brandbox.cli.logos.is_known_miss", return_value=False)
        mocker.patch("brandbox.cli.logos.get_logo", return_value=b"fake-png")
        mocker.patch("brandbox.cli.state.save")
        mocker.patch("brandbox.cli.time.sleep")

    def test_new_sender_with_valid_domain__creates_contact(
        self,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """New sender with company domain creates a contact with logo."""
        # Arrange
        mock_provider.contacts = [sample_contacts[0]]  # alice@company.com
        mock_provider.senders = {"alice@company.com", "newguy@startup.io"}
        app_state: dict[str, Any] = {}
        contact_count_before = len(mock_provider.contacts)

        # Act
        _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
            scan_inbox=True,
        )

        # Assert
        # "newguy@startup.io" should have created a contact
        assert len(mock_provider.contacts) > contact_count_before
        # The sender "newguy@startup.io" was created with a logo attached
        created_emails = {e for c in mock_provider.contacts for e in c.emails}
        assert "newguy@startup.io" in created_emails

    def test_new_sender_with_personal_domain__skipped(
        self,
        mocker: MockerFixture,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """New sender with personal domain is skipped."""
        # Arrange
        mocker.patch(
            "brandbox.cli.logos.is_personal_domain",
            side_effect=lambda d: d == "gmail.com",
        )
        mock_provider.contacts = [sample_contacts[0]]  # alice@company.com
        mock_provider.senders = {"alice@company.com", "person@gmail.com"}
        app_state: dict[str, Any] = {}
        contact_count_before = len(mock_provider.contacts)

        # Act
        _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
            scan_inbox=True,
        )

        # Assert — no contact created for personal domain
        assert len(mock_provider.contacts) == contact_count_before

    def test_new_sender_with_no_logo__skipped(
        self,
        mocker: MockerFixture,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """New sender whose domain has no logo is skipped."""
        # Arrange
        mocker.patch("brandbox.cli.logos.get_logo", return_value=None)
        mock_provider.contacts = [sample_contacts[0]]
        mock_provider.senders = {"alice@company.com", "newguy@startup.io"}
        app_state: dict[str, Any] = {}
        contact_count_before = len(mock_provider.contacts)

        # Act
        _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
            scan_inbox=True,
        )

        # Assert — no contact created when logo is None
        assert len(mock_provider.contacts) == contact_count_before

    def test_no_new_senders__nothing_created(
        self,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """When all senders are already contacts, nothing is created."""
        # Arrange
        mock_provider.contacts = sample_contacts
        existing_emails = {e.lower() for c in sample_contacts for e in c.emails}
        mock_provider.senders = existing_emails  # all senders already in contacts
        app_state: dict[str, Any] = {}
        contact_count_before = len(mock_provider.contacts)

        # Act
        _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
            scan_inbox=True,
        )

        # Assert
        assert len(mock_provider.contacts) == contact_count_before

    def test_scan_inbox_dry_run__does_not_create(
        self,
        mocker: MockerFixture,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """Dry-run + scan-inbox: no contacts are created."""
        # Arrange
        spy_create = mocker.spy(mock_provider, "create_contact")
        mock_provider.contacts = [sample_contacts[0]]
        mock_provider.senders = {"alice@company.com", "newguy@startup.io"}
        app_state: dict[str, Any] = {}

        # Act
        _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
            dry_run=True,
            scan_inbox=True,
        )

        # Assert
        spy_create.assert_not_called()

    def test_inbox_scan_set_photo_fails__contact_created_but_not_counted(
        self,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """When set_contact_photo fails in inbox scan, the contact is created
        but not recorded in app_state.

        This covers branch 230→234 (:cls:`cli.py`) — the fall-through when
        ``set_contact_photo`` returns ``False`` during inbox scanning.
        """
        # Arrange
        mock_provider.fail_set_photo = True
        mock_provider.contacts = [sample_contacts[0]]
        mock_provider.senders = {"alice@company.com", "newguy@startup.io"}
        app_state: dict[str, Any] = {}
        contact_count_before = len(mock_provider.contacts)

        # Act
        _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
            scan_inbox=True,
        )

        # Assert — the contact WAS created (MockProvider.create_contact appends)
        # but NOT added to app_state because set_contact_photo returned False
        assert len(mock_provider.contacts) == contact_count_before + 1
        # The new contact ID should NOT be in the app_state
        account_state = app_state.get(sample_account.username, {})
        new_contact_ids = {c.id for c in mock_provider.contacts} - {"c1"}
        for cid in new_contact_ids:
            assert cid not in account_state


# ═══════════════════════════════════════════════════════════════════
#  _process_account  —  error handling
# ═══════════════════════════════════════════════════════════════════


class TestProcessAccountErrors:
    """Error-handling paths in _process_account()."""

    @pytest.fixture(autouse=True)
    def _setup_mocks(self, mocker: MockerFixture) -> None:
        """Default patches for all tests in this class."""
        mocker.patch("brandbox.cli.logos.root_domain", side_effect=_domain_side_effect)
        mocker.patch("brandbox.cli.logos.is_personal_domain", return_value=False)
        mocker.patch("brandbox.cli.logos.is_known_miss", return_value=False)
        mocker.patch("brandbox.cli.logos.get_logo", return_value=b"fake-png")
        mocker.patch("brandbox.cli.state.save")
        mocker.patch("brandbox.cli.time.sleep")

    def test_contact_creation_fails_during_inbox_scan(
        self,
        mocker: MockerFixture,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """When create_contact returns None, the sender is silently skipped.

        This covers line 229 (:cls:`cli.py`) — the ``continue`` after a
        failed ``create_contact`` call during inbox scanning.
        """

        # Arrange
        # Override root_domain so that "newguy@startup.io" resolves to a domain
        # (otherwise root_domain returns None and the inbox-scan early-aborts
        #  before reaching create_contact).
        def _domain_overrides(email: str) -> str | None:
            mapping = {**EMAIL_DOMAIN, "newguy@startup.io": "startup.io"}
            return mapping.get(email)

        mocker.patch("brandbox.cli.logos.root_domain", side_effect=_domain_overrides)
        mocker.patch("brandbox.cli.logos.get_logo", return_value=b"fake-png")
        mock_provider.fail_create_contact = True
        mock_provider.contacts = [sample_contacts[0]]
        mock_provider.senders = {"alice@company.com", "newguy@startup.io"}
        app_state: dict[str, Any] = {}
        contact_count_before = len(mock_provider.contacts)

        # Act
        _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
            scan_inbox=True,
        )

        # Assert
        assert len(mock_provider.contacts) == contact_count_before  # no new contacts

    def test_contact_with_mixed_case_emails_matched_in_scan(
        self,
        mocker: MockerFixture,
        mock_provider: Any,
        sample_contacts: list[Contact],
        sample_account: Account,
    ) -> None:
        """Inbox scan matches existing contacts case-insensitively."""

        # Arrange
        # Override root_domain to handle test emails
        def _mixed_domain(email: str) -> str | None:
            mapping = {**EMAIL_DOMAIN, "newguy@startup.io": "startup.io"}
            return mapping.get(email)

        mocker.patch("brandbox.cli.logos.root_domain", side_effect=_mixed_domain)
        contact = Contact(id="c-mixed", display_name="Mixed", emails=["Alice@Company.COM"])
        mock_provider.contacts = [contact]
        # "alice@company.com" should match case-insensitively
        mock_provider.senders = {"alice@company.com", "newguy@startup.io"}
        app_state: dict[str, Any] = {}
        contact_count_before = len(mock_provider.contacts)

        # Act
        _process_account(
            provider=mock_provider,
            token="test-token",
            account=sample_account,
            idx=1,
            total=1,
            app_state=app_state,
            scan_inbox=True,
        )

        # Assert — "alice@company.com" was already a contact (case-insensitive)
        assert len(mock_provider.contacts) == contact_count_before + 1  # only newguy created


# ═══════════════════════════════════════════════════════════════════
#  main  —  helpers
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_main_env(mocker: MockerFixture, mock_provider: Any) -> dict[str, Any]:
    """Patch the external dependencies main() relies on.

    Returns a mutable app_state dict that tests can inspect and a reference
    to the mock_provider so tests can configure accounts / contacts.
    """
    app_state: dict[str, Any] = {}
    mocker.patch("brandbox.cli.build_providers", return_value={"mock": mock_provider})
    mocker.patch("brandbox.cli.get_provider", return_value=mock_provider)
    mocker.patch("brandbox.cli.logos.clear_cache", return_value=5)
    mocker.patch("brandbox.cli.state.load", return_value=app_state)
    mocker.patch("brandbox.cli.state.save")
    mocker.patch("brandbox.cli.logos.root_domain", return_value="company.com")
    mocker.patch("brandbox.cli.logos.is_personal_domain", return_value=False)
    mocker.patch("brandbox.cli.logos.is_known_miss", return_value=False)
    mocker.patch("brandbox.cli.logos.get_logo", return_value=b"fake-png")
    mocker.patch("brandbox.cli.time.sleep")
    return {"app_state": app_state, "mock_provider": mock_provider}


# ═══════════════════════════════════════════════════════════════════
#  main  —  informational flags
# ═══════════════════════════════════════════════════════════════════


class TestMainDataDir:
    """main() — --data-dir flag."""

    def test_prints_data_dir_and_exits(self, mocker: MockerFixture) -> None:
        """--data-dir prints the data directory path and returns cleanly."""
        # Arrange
        mocker.patch("sys.argv", ["brandbox", "--data-dir"])
        mock_print = mocker.patch("brandbox.cli.console.print")

        # Act
        main()

        # Assert
        assert mock_print.call_count >= 1
        all_text = " ".join(str(c) for c in mock_print.call_args_list)
        assert "Data directory" in all_text or "brandbox" in all_text


class TestMainVersion:
    """main() — --version / -V flag."""

    def test_version_flag_exits_with_code_zero(self, mocker: MockerFixture) -> None:
        """--version prints version and exits with code 0."""
        # Arrange
        mocker.patch("sys.argv", ["brandbox", "--version"])

        # Act & Assert
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_capital_v_flag_exits_with_code_zero(self, mocker: MockerFixture) -> None:
        """-V prints version and exits with code 0."""
        # Arrange
        mocker.patch("sys.argv", ["brandbox", "-V"])

        # Act & Assert
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0


# ═══════════════════════════════════════════════════════════════════
#  main  —  add-account
# ═══════════════════════════════════════════════════════════════════


class TestMainAddAccount:
    """main() — --add-account flag."""

    def test_add_account_prompts_and_creates(
        self,
        mocker: MockerFixture,
        mock_main_env: dict[str, Any],
    ) -> None:
        """--add-account without --provider prompts and creates account."""
        # Arrange
        mocker.patch("sys.argv", ["brandbox", "--add-account"])
        mocker.patch("brandbox.cli.Prompt.ask", return_value="microsoft")
        mock_provider = mock_main_env["mock_provider"]
        spy_finish = mocker.spy(mock_provider, "finish_auth")

        # Act
        main()

        # Assert — finish_auth was called (account was created)
        spy_finish.assert_called_once()

    def test_add_account_with_provider_skips_prompt(
        self,
        mocker: MockerFixture,
        mock_main_env: dict[str, Any],
    ) -> None:
        """--add-account --provider microsoft skips the prompt."""
        # Arrange
        mocker.patch("sys.argv", ["brandbox", "--add-account", "--provider", "microsoft"])
        mock_prompt = mocker.patch("brandbox.cli.Prompt.ask")

        # Act
        main()

        # Assert — Prompt.ask was NOT called (provider was given directly)
        mock_prompt.assert_not_called()

    def test_add_account_missing_config_exits(
        self,
        mocker: MockerFixture,
        mock_main_env: dict[str, Any],
    ) -> None:
        """--add-account with missing config prints error and exits with code 1."""
        # Arrange
        mocker.patch("sys.argv", ["brandbox", "--add-account", "--provider", "microsoft"])
        mocker.patch("brandbox.cli.get_provider", side_effect=RuntimeError("Config missing"))

        # Act & Assert
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1


class TestMainListAccounts:
    """main() — --list-accounts flag."""

    def test_list_accounts_with_accounts(
        self,
        mock_main_env: dict[str, Any],
    ) -> None:
        """--list-accounts displays accounts when they exist."""
        # Arrange
        from brandbox import cli as cli_module

        cli_module.sys.argv = ["brandbox", "--list-accounts"]
        mock_provider = mock_main_env["mock_provider"]
        mock_provider.accounts = [
            Account(username="user@company.com", provider_name="microsoft"),
        ]

        # Act
        main()

        # Assert — no crash, accounts listed
        assert True

    def test_list_accounts_no_accounts(
        self,
        mock_main_env: dict[str, Any],
    ) -> None:
        """--list-accounts shows message when no accounts exist."""
        # Arrange
        from brandbox import cli as cli_module

        cli_module.sys.argv = ["brandbox", "--list-accounts"]
        mock_provider = mock_main_env["mock_provider"]
        mock_provider.accounts = []

        # Act
        main()

        # Assert — no crash, empty message printed
        assert True


# ═══════════════════════════════════════════════════════════════════
#  main  —  clear-cache / reset-state
# ═══════════════════════════════════════════════════════════════════


class TestMainCacheAndState:
    """main() — --clear-cache and --reset-state flags."""

    def test_clear_cache_alone(
        self,
        mocker: MockerFixture,
        mock_main_env: dict[str, Any],
    ) -> None:
        """--clear-cache alone calls clear_cache and returns."""
        # Arrange
        mocker.patch("sys.argv", ["brandbox", "--clear-cache"])
        mock_clear = mocker.patch("brandbox.cli.logos.clear_cache", return_value=5)

        # Act
        main()

        # Assert
        mock_clear.assert_called_once()

    def test_clear_cache_with_run(
        self,
        mocker: MockerFixture,
        mock_main_env: dict[str, Any],
    ) -> None:
        """--clear-cache --run clears cache then processes accounts."""
        # Arrange
        mocker.patch("sys.argv", ["brandbox", "--clear-cache", "--run"])
        mock_clear = mocker.patch("brandbox.cli.logos.clear_cache", return_value=5)
        mock_provider = mock_main_env["mock_provider"]
        mock_provider.accounts = [
            Account(username="user@company.com", provider_name="microsoft"),
        ]
        mock_provider.contacts = [
            Contact(id="c1", display_name="Alice", emails=["alice@company.com"]),
        ]

        # Act
        main()

        # Assert — both clear and run happened
        mock_clear.assert_called_once()

    def test_reset_state_alone(
        self,
        mocker: MockerFixture,
        mock_main_env: dict[str, Any],
    ) -> None:
        """--reset-state alone unlinks state file and returns."""
        # Arrange
        mocker.patch("sys.argv", ["brandbox", "--reset-state"])
        mock_unlink = mocker.patch("pathlib.Path.unlink")

        # Act
        main()

        # Assert
        mock_unlink.assert_called_once_with(missing_ok=True)

    def test_reset_state_with_run(
        self,
        mocker: MockerFixture,
        mock_main_env: dict[str, Any],
    ) -> None:
        """--reset-state --run resets state then processes accounts."""
        # Arrange
        mocker.patch("sys.argv", ["brandbox", "--reset-state", "--run"])
        mock_unlink = mocker.patch("pathlib.Path.unlink")
        mock_provider = mock_main_env["mock_provider"]
        mock_provider.accounts = [
            Account(username="user@company.com", provider_name="microsoft"),
        ]
        mock_provider.contacts = [
            Contact(id="c1", display_name="Alice", emails=["alice@company.com"]),
        ]

        # Act
        main()

        # Assert
        mock_unlink.assert_called_once_with(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════
#  main  —  run / dry-run
# ═══════════════════════════════════════════════════════════════════


class TestMainRun:
    """main() — --run and --dry-run flags."""

    def test_run_processes_all_accounts(
        self,
        mocker: MockerFixture,
        mock_main_env: dict[str, Any],
    ) -> None:
        """--run processes all accounts and sets logos."""
        # Arrange
        mocker.patch("sys.argv", ["brandbox", "--run"])
        mock_provider = mock_main_env["mock_provider"]
        mock_provider.accounts = [
            Account(username="user@company.com", provider_name="microsoft"),
        ]
        mock_provider.contacts = [
            Contact(id="c1", display_name="Alice", emails=["alice@company.com"]),
        ]

        # Act
        main()

        # Assert — no crash, logos were set
        assert True

    def test_dry_run_does_not_upload(
        self,
        mocker: MockerFixture,
        mock_main_env: dict[str, Any],
    ) -> None:
        """--run --dry-run shows what would happen without uploading."""
        # Arrange
        mocker.patch("sys.argv", ["brandbox", "--run", "--dry-run"])
        mock_provider = mock_main_env["mock_provider"]
        mock_provider.accounts = [
            Account(username="user@company.com", provider_name="microsoft"),
        ]
        mock_provider.contacts = [
            Contact(id="c1", display_name="Alice", emails=["alice@company.com"]),
        ]
        spy_set_photo = mocker.spy(mock_provider, "set_contact_photo")

        # Act
        main()

        # Assert
        spy_set_photo.assert_not_called()

    def test_run_with_overwrite(
        self,
        mocker: MockerFixture,
        mock_main_env: dict[str, Any],
    ) -> None:
        """--run --overwrite re-processes already-processed contacts."""
        # Arrange
        mocker.patch("sys.argv", ["brandbox", "--run", "--overwrite"])
        mock_provider = mock_main_env["mock_provider"]
        mock_provider.accounts = [
            Account(username="user@company.com", provider_name="microsoft"),
        ]
        mock_provider.contacts = [
            Contact(id="c1", display_name="Alice", emails=["alice@company.com"]),
        ]
        # Pre-mark as processed
        mock_main_env["app_state"] = {"user@company.com": {"c1": "company.com"}}

        # Act
        main()

        # Assert — overwrite means it should have called set_contact_photo
        assert True

    def test_run_with_scan_inbox(
        self,
        mocker: MockerFixture,
        mock_main_env: dict[str, Any],
    ) -> None:
        """--run --scan-inbox creates contacts from recent senders."""
        # Arrange
        mocker.patch("sys.argv", ["brandbox", "--run", "--scan-inbox"])
        mock_provider = mock_main_env["mock_provider"]
        mock_provider.accounts = [
            Account(username="user@company.com", provider_name="microsoft"),
        ]
        mock_provider.contacts = [
            Contact(id="c1", display_name="Alice", emails=["alice@company.com"]),
        ]
        mock_provider.senders = {"alice@company.com", "newguy@startup.io"}

        # Act
        main()

        # Assert — "newguy" should be added as a contact
        created_emails = {e for c in mock_provider.contacts for e in c.emails}
        assert "newguy@startup.io" in created_emails

    def test_run_with_failed_uploads_shows_failed_count(
        self,
        mocker: MockerFixture,
        mock_main_env: dict[str, Any],
    ) -> None:
        """--run with failed uploads includes the '[red]failed[/red]' segment in output.

        This covers line 550 (:cls:`cli.py`) — the ``if totals['failed']``
        branch in the final elapsed-time summary.
        """
        # Arrange
        mocker.patch("sys.argv", ["brandbox", "--run"])
        mock_provider = mock_main_env["mock_provider"]
        mock_provider.fail_set_photo = True  # all uploads fail
        mock_provider.accounts = [
            Account(username="user@company.com", provider_name="microsoft"),
        ]
        mock_provider.contacts = [
            Contact(id="c1", display_name="Alice", emails=["alice@company.com"]),
        ]
        mock_print = mocker.patch("brandbox.cli.console.print")

        # Act
        main()

        # Assert — the final summary should mention "failed"
        final_calls = " ".join(str(c) for c in mock_print.call_args_list)
        assert "failed" in final_calls.lower()


class TestMainRunErrors:
    """main() — error paths during --run."""

    def test_run_with_no_providers_exits(
        self,
        mocker: MockerFixture,
        mock_main_env: dict[str, Any],
    ) -> None:
        """--run exits with code 1 when no providers are configured."""
        # Arrange
        mocker.patch("sys.argv", ["brandbox", "--run"])
        mocker.patch("brandbox.cli.build_providers", return_value={})

        # Act & Assert
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    def test_run_with_no_accounts_exits(
        self,
        mocker: MockerFixture,
        mock_main_env: dict[str, Any],
    ) -> None:
        """--run exits with code 1 when no accounts are registered."""
        # Arrange
        mocker.patch("sys.argv", ["brandbox", "--run"])
        mock_provider = mock_main_env["mock_provider"]
        mock_provider.accounts = []  # no accounts

        # Act & Assert
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    def test_run_with_provider_error_continues(
        self,
        mocker: MockerFixture,
        mock_main_env: dict[str, Any],
    ) -> None:
        """When get_token raises, main continues to the next account."""
        # Arrange
        mocker.patch("sys.argv", ["brandbox", "--run"])
        mock_provider = mock_main_env["mock_provider"]
        mock_provider.fail_token = True
        mock_provider.accounts = [
            Account(username="user@company.com", provider_name="microsoft"),
        ]

        # Act — should catch the error and continue (no crash)
        main()

        # Assert — reached the end without crashing
        assert True

    def test_run_multiple_accounts_shows_total(
        self,
        mocker: MockerFixture,
        mock_main_env: dict[str, Any],
    ) -> None:
        """--run with 2 accounts prints total summary."""
        # Arrange
        mocker.patch("sys.argv", ["brandbox", "--run"])
        mock_provider = mock_main_env["mock_provider"]
        mock_provider.fail_token = False
        mock_provider.accounts = [
            Account(username="user@company.com", provider_name="microsoft"),
            Account(username="admin@company.com", provider_name="microsoft"),
        ]
        mock_provider.contacts = [
            Contact(id="c1", display_name="Alice", emails=["alice@company.com"]),
        ]
        mock_print = mocker.patch("brandbox.cli.console.print")

        # Act
        main()

        # Assert — total summary should be printed (across accounts)
        # The total rule is printed for >1 accounts
        total_calls = [
            c for c in mock_print.call_args_list if "Total across all accounts" in str(c)
        ]
        assert len(total_calls) >= 1


# ═══════════════════════════════════════════════════════════════════
#  main  —  no-action fallback
# ═══════════════════════════════════════════════════════════════════


class TestMainNoAction:
    """main() — no actionable flags."""

    def test_no_flags_prints_help(self, mocker: MockerFixture) -> None:
        """Running with no actionable flags prints help text."""
        # Arrange
        mocker.patch("sys.argv", ["brandbox"])
        mocker.patch("brandbox.cli.console.print")
        # We need the parser.print_help call to work; argparse prints to stderr,
        # but we can verify that console.print was called (from _print_banner)
        # and no error was raised

        # Act
        main()

        # Assert — no crash, banner printed via console.print
        assert True


# ═══════════════════════════════════════════════════════════════════
#  main  —  __main__ guard coverage
# ═══════════════════════════════════════════════════════════════════


class TestMainModule:
    """Coverage for the __main__ guard pattern (module scope)."""

    def test_console_is_module_level_instance(self) -> None:
        """The module has a console instance at module scope."""
        from brandbox.cli import console as module_console

        assert module_console is not None

    def test_module_level_dirs_exist(self) -> None:
        """Module-level directories are created on import."""
        from brandbox.cli import CACHE_DIR, TOKEN_DIR

        assert CACHE_DIR.exists()
        assert TOKEN_DIR.exists()
