"""Tests for the Google provider."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests
from google.oauth2.credentials import Credentials as RealCredentials

from brandbox.providers.base import Account
from brandbox.providers.google import (
    PEOPLE_BASE,
    SCOPES,
    USERINFO_URL,
    GoogleProvider,
)


class TestGoogleProvider:
    """Test suite for GoogleProvider."""

    # ── Fixtures ─────────────────────────────────────────────────────

    @pytest.fixture
    def mock_flow_cls(self, mocker):
        """Mock the InstalledAppFlow class to avoid browser OAuth flow."""
        return mocker.patch("brandbox.providers.google.InstalledAppFlow")

    @pytest.fixture
    def mock_credentials_instance(self, mocker):
        """Create a MagicMock specced to RealCredentials for isinstance checks."""
        creds = mocker.MagicMock(spec=RealCredentials)
        creds.token = "fake-token"
        creds.refresh_token = "fake-refresh"
        creds.expired = False
        creds.to_json.return_value = json.dumps(
            {
                "token": "fake-token",
                "refresh_token": "fake-refresh",
                "scopes": SCOPES,
            }
        )
        return creds

    @pytest.fixture
    def provider(self, token_dir: Path, tmp_path: Path) -> GoogleProvider:
        """A GoogleProvider with a temp credentials file and token dir."""
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text('{"installed": {"client_id": "x"}}')
        return GoogleProvider(creds_file, token_dir)

    # ── Constructor ──────────────────────────────────────────────────

    def test_constructor_creates_token_dir(self, tmp_path: Path) -> None:
        """Constructor creates token_dir if it does not exist."""
        # Arrange
        token_dir = tmp_path / "my_tokens"
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")

        # Act
        GoogleProvider(creds_file, token_dir)

        # Assert
        assert token_dir.is_dir()

    def test_constructor_uses_existing_token_dir(self, tmp_path: Path) -> None:
        """Constructor does not error when token_dir already exists."""
        # Arrange
        token_dir = tmp_path / "existing_tokens"
        token_dir.mkdir(parents=True, exist_ok=True)
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")

        # Act (should not raise)
        provider = GoogleProvider(creds_file, token_dir)

        # Assert
        assert provider._token_dir == token_dir
        assert provider._creds_file == creds_file

    # ── Internal helpers: _token_path, _save_token, _load_creds, _headers ──

    def test_token_path_standard_email(self, token_dir: Path, tmp_path: Path) -> None:
        """_token_path sanitises a standard email correctly."""
        # Arrange
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")
        provider = GoogleProvider(creds_file, token_dir)

        # Act
        path = provider._token_path("user@gmail.com")

        # Assert
        assert path == token_dir / "google_user_at_gmail_com.json"

    def test_token_path_sanitises_special_chars(self, token_dir: Path, tmp_path: Path) -> None:
        """_token_path replaces dots and plus signs in email."""
        # Arrange
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")
        provider = GoogleProvider(creds_file, token_dir)

        # Act
        path = provider._token_path("first.last+tag@sub.domain.com")

        # Assert
        assert path == token_dir / "google_first_last_tag_at_sub_domain_com.json"

    def test_save_token_writes_correct_structure(
        self, token_dir: Path, tmp_path: Path, mock_credentials_instance: MagicMock
    ) -> None:
        """_save_token writes username + credentials JSON to token file."""
        # Arrange
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")
        provider = GoogleProvider(creds_file, token_dir)

        # Act
        provider._save_token("user@gmail.com", mock_credentials_instance)

        # Assert
        token_path = token_dir / "google_user_at_gmail_com.json"
        assert token_path.exists()
        data = json.loads(token_path.read_text())
        assert data["username"] == "user@gmail.com"
        assert "credentials" in data
        assert data["credentials"]["token"] == "fake-token"

    def test_load_creds_returns_credentials(self, mocker, token_dir: Path, tmp_path: Path) -> None:
        """_load_creds reads token file and returns a Credentials object."""
        # Arrange
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")
        provider = GoogleProvider(creds_file, token_dir)

        # Write a token file
        token_path = token_dir / "google_user_at_gmail_com.json"
        token_path.write_text(
            json.dumps(
                {
                    "username": "user@gmail.com",
                    "credentials": {
                        "token": "stored-token",
                        "refresh_token": "stored-refresh",
                        "scopes": SCOPES,
                    },
                }
            )
        )

        mock_creds = mocker.MagicMock(spec=RealCredentials)
        mock_creds.token = "stored-token"
        mock_creds.refresh_token = "stored-refresh"
        mock_creds.expired = False
        mocker.patch(
            "brandbox.providers.google.Credentials.from_authorized_user_info",
            return_value=mock_creds,
        )

        # Act
        result = provider._load_creds("user@gmail.com")

        # Assert
        assert result.token == "stored-token"

    def test_load_creds_nonexistent_user_raises(self, token_dir: Path, tmp_path: Path) -> None:
        """_load_creds propagates FileNotFoundError for missing user."""
        # Arrange
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")
        provider = GoogleProvider(creds_file, token_dir)

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            provider._load_creds("nonexistent@gmail.com")

    def test_load_creds_refreshes_when_expired(
        self, mocker, token_dir: Path, tmp_path: Path
    ) -> None:
        """_load_creds refreshes credentials when expired and has refresh_token."""
        # Arrange
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")
        provider = GoogleProvider(creds_file, token_dir)

        token_path = token_dir / "google_user_at_gmail_com.json"
        token_path.write_text(
            json.dumps(
                {
                    "username": "user@gmail.com",
                    "credentials": {
                        "token": "old-token",
                        "refresh_token": "refresh-me",
                        "scopes": SCOPES,
                    },
                }
            )
        )

        mock_creds = mocker.MagicMock(spec=RealCredentials)
        mock_creds.token = "old-token"
        mock_creds.refresh_token = "refresh-me"
        mock_creds.expired = True
        mock_creds.to_json.return_value = json.dumps(
            {
                "token": "new-token",
                "refresh_token": "refresh-me",
                "scopes": SCOPES,
            }
        )
        mocker.patch(
            "brandbox.providers.google.Credentials.from_authorized_user_info",
            return_value=mock_creds,
        )
        mock_request_cls = mocker.patch("brandbox.providers.google.Request")

        # Act
        result = provider._load_creds("user@gmail.com")

        # Assert
        assert result.token == "old-token"
        mock_creds.refresh.assert_called_once_with(mock_request_cls.return_value)
        # Verify token file was re-written after refresh
        updated_data = json.loads(token_path.read_text())
        assert updated_data["username"] == "user@gmail.com"

    def test_load_creds_skips_refresh_when_not_expired(
        self, mocker, token_dir: Path, tmp_path: Path
    ) -> None:
        """_load_creds does not refresh when credentials are still valid."""
        # Arrange
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")
        provider = GoogleProvider(creds_file, token_dir)

        token_path = token_dir / "google_user_at_gmail_com.json"
        token_path.write_text(
            json.dumps(
                {
                    "username": "user@gmail.com",
                    "credentials": {
                        "token": "valid-token",
                        "refresh_token": "refresh-me",
                        "scopes": SCOPES,
                    },
                }
            )
        )

        mock_creds = mocker.MagicMock(spec=RealCredentials)
        mock_creds.token = "valid-token"
        mock_creds.refresh_token = "refresh-me"
        mock_creds.expired = False
        mocker.patch(
            "brandbox.providers.google.Credentials.from_authorized_user_info",
            return_value=mock_creds,
        )
        mocker.patch("brandbox.providers.google.Request")

        # Act
        provider._load_creds("user@gmail.com")

        # Assert
        mock_creds.refresh.assert_not_called()

    def test_load_creds_skips_refresh_when_no_refresh_token(
        self, mocker, token_dir: Path, tmp_path: Path
    ) -> None:
        """_load_creds does not refresh when refresh_token is missing."""
        # Arrange
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")
        provider = GoogleProvider(creds_file, token_dir)

        token_path = token_dir / "google_user_at_gmail_com.json"
        token_path.write_text(
            json.dumps(
                {
                    "username": "user@gmail.com",
                    "credentials": {
                        "token": "expired-token",
                        "scopes": SCOPES,
                    },
                }
            )
        )

        mock_creds = mocker.MagicMock(spec=RealCredentials)
        mock_creds.token = "expired-token"
        mock_creds.refresh_token = None
        mock_creds.expired = True
        mocker.patch(
            "brandbox.providers.google.Credentials.from_authorized_user_info",
            return_value=mock_creds,
        )

        # Act
        result = provider._load_creds("user@gmail.com")

        # Assert
        assert result.token == "expired-token"
        # refresh() should NOT have been called
        assert not hasattr(mock_creds.refresh, "called") or not mock_creds.refresh.called

    def test_headers_returns_bearer_dict(self, provider: GoogleProvider) -> None:
        """_headers returns dict with Authorization Bearer header."""
        # Act
        result = provider._headers("token-xyz")

        # Assert
        assert result == {"Authorization": "Bearer token-xyz"}

    # ── People API paging: _people_get_paged ─────────────────────────

    def test_people_get_paged_single_page(self, mocker, provider: GoogleProvider) -> None:
        """_people_get_paged returns all items from a single page."""
        # Arrange
        mock_get = mocker.patch("brandbox.providers.google.requests.get")
        mock_get.return_value.json.return_value = {
            "connections": [{"resourceName": "people/c1"}],
        }
        mock_get.return_value.raise_for_status.return_value = None

        # Act
        items = provider._people_get_paged(
            "token", f"{PEOPLE_BASE}/people/me/connections", "connections"
        )

        # Assert
        assert items == [{"resourceName": "people/c1"}]

    def test_people_get_paged_follows_next_page_token(
        self, mocker, provider: GoogleProvider
    ) -> None:
        """_people_get_paged follows nextPageToken for multi-page results."""
        # Arrange
        mock_get = mocker.patch("brandbox.providers.google.requests.get")
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.json.side_effect = [
            {
                "connections": [{"resourceName": "people/c1"}],
                "nextPageToken": "token2",
            },
            {
                "connections": [{"resourceName": "people/c2"}],
            },
        ]

        # Act
        items = provider._people_get_paged(
            "token", f"{PEOPLE_BASE}/people/me/connections", "connections"
        )

        # Assert
        assert items == [{"resourceName": "people/c1"}, {"resourceName": "people/c2"}]
        assert mock_get.call_count == 2
        # First call has no pageToken, second call includes it
        assert "pageToken" not in mock_get.call_args_list[0][1].get("params", {})
        assert mock_get.call_args_list[1][1]["params"]["pageToken"] == "token2"

    def test_people_get_paged_always_has_page_size_1000(
        self, mocker, provider: GoogleProvider
    ) -> None:
        """_people_get_paged always includes pageSize=1000 in params."""
        # Arrange
        mock_get = mocker.patch("brandbox.providers.google.requests.get")
        mock_get.return_value.json.return_value = {
            "otherContacts": [],
        }
        mock_get.return_value.raise_for_status.return_value = None

        # Act
        provider._people_get_paged(
            "token",
            f"{PEOPLE_BASE}/otherContacts",
            "otherContacts",
            params={"readMask": "names"},
        )

        # Assert
        params = mock_get.call_args[1]["params"]
        assert params["pageSize"] == 1000
        assert params["readMask"] == "names"

    def test_people_get_paged_handles_missing_key(self, mocker, provider: GoogleProvider) -> None:
        """_people_get_paged returns [] when items_key is missing from response."""
        # Arrange
        mock_get = mocker.patch("brandbox.providers.google.requests.get")
        mock_get.return_value.json.return_value = {}
        mock_get.return_value.raise_for_status.return_value = None

        # Act
        items = provider._people_get_paged("token", f"{PEOPLE_BASE}/otherContacts", "otherContacts")

        # Assert
        assert items == []

    def test_people_get_paged_raises_on_http_error(self, mocker, provider: GoogleProvider) -> None:
        """_people_get_paged raises when HTTP request fails."""
        # Arrange
        mock_get = mocker.patch("brandbox.providers.google.requests.get")
        mock_get.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "401 Unauthorized"
        )

        # Act & Assert
        with pytest.raises(requests.exceptions.HTTPError):
            provider._people_get_paged(
                "token", f"{PEOPLE_BASE}/people/me/connections", "connections"
            )

    # ── Static: _parse_contact ───────────────────────────────────────

    def test_parse_contact_full_data(self) -> None:
        """_parse_contact extracts id, display_name, and emails from person dict."""
        # Arrange
        person = {
            "resourceName": "people/c123",
            "names": [{"displayName": "Alice"}],
            "emailAddresses": [
                {"value": "  Alice@Co.com  "},
                {"value": "alice@work.com"},
            ],
        }

        # Act
        contact = GoogleProvider._parse_contact(person)

        # Assert
        assert contact.id == "people/c123"
        assert contact.display_name == "Alice"
        assert contact.emails == ["alice@co.com", "alice@work.com"]

    def test_parse_contact_missing_names(self) -> None:
        """_parse_contact uses empty display_name when names list is missing."""
        # Arrange
        person = {
            "resourceName": "people/c1",
            "emailAddresses": [{"value": "a@b.com"}],
        }

        # Act
        contact = GoogleProvider._parse_contact(person)

        # Assert
        assert contact.display_name == ""

    def test_parse_contact_empty_names(self) -> None:
        """_parse_contact uses empty display_name when names list is empty."""
        # Arrange
        person = {
            "resourceName": "people/c1",
            "names": [],
            "emailAddresses": [{"value": "a@b.com"}],
        }

        # Act
        contact = GoogleProvider._parse_contact(person)

        # Assert
        assert contact.display_name == ""

    def test_parse_contact_missing_email_addresses(self) -> None:
        """_parse_contact returns empty emails list when emailAddresses missing."""
        # Arrange
        person = {
            "resourceName": "people/c1",
            "names": [{"displayName": "Bob"}],
        }

        # Act
        contact = GoogleProvider._parse_contact(person)

        # Assert
        assert contact.emails == []

    def test_parse_contact_empty_email_list(self) -> None:
        """_parse_contact returns empty emails when emailAddresses is empty."""
        # Arrange
        person = {
            "resourceName": "people/c1",
            "emailAddresses": [],
        }

        # Act
        contact = GoogleProvider._parse_contact(person)

        # Assert
        assert contact.emails == []

    def test_parse_contact_skips_email_without_value_key(self) -> None:
        """_parse_contact filters out emails missing the 'value' key."""
        # Arrange
        person = {
            "resourceName": "people/c1",
            "emailAddresses": [
                {"value": "good@co.com"},
                {"type": "work"},  # no 'value' key
            ],
        }

        # Act
        contact = GoogleProvider._parse_contact(person)

        # Assert
        assert contact.emails == ["good@co.com"]

    def test_parse_contact_missing_resource_name(self) -> None:
        """_parse_contact uses empty string when resourceName missing."""
        # Arrange
        person = {
            "names": [{"displayName": "Carol"}],
            "emailAddresses": [{"value": "c@co.com"}],
        }

        # Act
        contact = GoogleProvider._parse_contact(person)

        # Assert
        assert contact.id == ""

    # ── Auth: start_auth ─────────────────────────────────────────────

    def test_start_auth_returns_browser_type(self, provider: GoogleProvider) -> None:
        """start_auth returns {'type': 'browser'} when creds file exists."""
        # Act
        result = provider.start_auth()

        # Assert
        assert result == {"type": "browser"}

    def test_start_auth_raises_when_creds_file_missing(
        self, token_dir: Path, tmp_path: Path
    ) -> None:
        """start_auth raises FileNotFoundError when creds file doesn't exist."""
        # Arrange
        missing_file = tmp_path / "does_not_exist.json"
        provider = GoogleProvider(missing_file, token_dir)

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="credentials file not found"):
            provider.start_auth()

    # ── Auth: finish_auth ────────────────────────────────────────────

    def test_finish_auth_runs_flow_and_returns_email(
        self, mocker, mock_flow_cls, mock_credentials_instance, provider: GoogleProvider
    ) -> None:
        """finish_auth runs OAuth flow, fetches email, saves token, returns email."""
        # Arrange
        mock_flow_cls.from_client_secrets_file.return_value.run_local_server.return_value = (
            mock_credentials_instance
        )
        mock_get = mocker.patch("brandbox.providers.google.requests.get")
        mock_get.return_value.json.return_value = {"email": "user@gmail.com"}
        mock_get.return_value.raise_for_status.return_value = None

        # Act
        result = provider.finish_auth({})

        # Assert
        assert result == "user@gmail.com"
        mock_flow_cls.from_client_secrets_file.assert_called_once_with(
            str(provider._creds_file), SCOPES
        )
        mock_get.assert_called_once_with(
            USERINFO_URL,
            headers={"Authorization": "Bearer fake-token"},
            timeout=10,
        )
        # Token should have been saved
        token_path = provider._token_path("user@gmail.com")
        assert token_path.exists()
        saved = json.loads(token_path.read_text())
        assert saved["username"] == "user@gmail.com"

    def test_finish_auth_falls_back_to_unknown_email(
        self, mocker, mock_flow_cls, mock_credentials_instance, provider: GoogleProvider
    ) -> None:
        """finish_auth uses 'unknown@google.com' when email missing from userinfo."""
        # Arrange
        mock_flow_cls.from_client_secrets_file.return_value.run_local_server.return_value = (
            mock_credentials_instance
        )
        mock_get = mocker.patch("brandbox.providers.google.requests.get")
        mock_get.return_value.json.return_value = {}
        mock_get.return_value.raise_for_status.return_value = None

        # Act
        result = provider.finish_auth({})

        # Assert
        assert result == "unknown@google.com"

    def test_finish_auth_raises_when_userinfo_fails(
        self, mocker, mock_flow_cls, mock_credentials_instance, provider: GoogleProvider
    ) -> None:
        """finish_auth raises when userinfo API request fails."""
        # Arrange
        mock_flow_cls.from_client_secrets_file.return_value.run_local_server.return_value = (
            mock_credentials_instance
        )
        mock_get = mocker.patch("brandbox.providers.google.requests.get")
        mock_get.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "401 Unauthorized"
        )

        # Act & Assert
        with pytest.raises(requests.exceptions.HTTPError):
            provider.finish_auth({})

    # ── Account management: get_accounts, get_token ──────────────────

    def test_get_accounts_returns_list(self, provider: GoogleProvider) -> None:
        """get_accounts returns Account objects from token files."""
        # Arrange
        token1 = provider._token_path("alice@gmail.com")
        token1.parent.mkdir(parents=True, exist_ok=True)
        token1.write_text(
            json.dumps({"username": "alice@gmail.com", "credentials": {"token": "t1"}})
        )
        token2 = provider._token_path("bob@work.com")
        token2.write_text(json.dumps({"username": "bob@work.com", "credentials": {"token": "t2"}}))

        # Act
        accounts = provider.get_accounts()

        # Assert
        assert len(accounts) == 2
        assert accounts[0] == Account(username="alice@gmail.com", provider_name="google")
        assert accounts[1] == Account(username="bob@work.com", provider_name="google")

    def test_get_accounts_empty(self, provider: GoogleProvider) -> None:
        """get_accounts returns [] when no token files."""
        # Act
        accounts = provider.get_accounts()

        # Assert
        assert accounts == []

    def test_get_accounts_skips_missing_username(self, provider: GoogleProvider) -> None:
        """get_accounts skips token files that lack a 'username' key."""
        # Arrange
        token_path = provider._token_path("someuser")
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(json.dumps({"credentials": {"token": "t"}}))

        # Act
        accounts = provider.get_accounts()

        # Assert
        assert accounts == []

    def test_get_accounts_skips_corrupted_files(self, provider: GoogleProvider) -> None:
        """get_accounts skips token files with invalid JSON."""
        # Arrange
        token_path = provider._token_path("broken")
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text("not-json")

        # Act
        accounts = provider.get_accounts()

        # Assert
        assert accounts == []

    def test_get_accounts_returns_sorted(self, provider: GoogleProvider) -> None:
        """get_accounts returns accounts sorted by token filename."""
        # Arrange
        token_dir = provider._token_dir
        token_dir.mkdir(parents=True, exist_ok=True)
        # Write files with filenames that sort in opposite order to the usernames
        (token_dir / "google_z_first.json").write_text(
            json.dumps(
                {
                    "username": "z_first@test.com",
                    "credentials": {"token": "t"},
                }
            )
        )
        (token_dir / "google_a_first.json").write_text(
            json.dumps(
                {
                    "username": "a_first@test.com",
                    "credentials": {"token": "t"},
                }
            )
        )

        # Act
        accounts = provider.get_accounts()

        # Assert
        assert len(accounts) == 2
        assert accounts[0].username == "a_first@test.com"
        assert accounts[1].username == "z_first@test.com"

    def test_get_token_returns_token_string(self, mocker, token_dir: Path, tmp_path: Path) -> None:
        """get_token returns token string for an existing account."""
        # Arrange
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")
        provider = GoogleProvider(creds_file, token_dir)

        token_path = provider._token_path("user@gmail.com")
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(
            json.dumps(
                {
                    "username": "user@gmail.com",
                    "credentials": {
                        "token": "stored-token",
                        "refresh_token": "rt",
                        "scopes": SCOPES,
                    },
                }
            )
        )

        mock_creds = mocker.MagicMock(spec=RealCredentials)
        mock_creds.token = "stored-token"
        mock_creds.expired = False
        mocker.patch(
            "brandbox.providers.google.Credentials.from_authorized_user_info",
            return_value=mock_creds,
        )

        account = Account(username="user@gmail.com", provider_name="google")

        # Act
        token = provider.get_token(account)

        # Assert
        assert token == "stored-token"

    def test_get_token_refreshes_if_needed(self, mocker, token_dir: Path, tmp_path: Path) -> None:
        """get_token refreshes expired credentials and returns the token."""
        # Arrange
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")
        provider = GoogleProvider(creds_file, token_dir)

        token_path = provider._token_path("user@gmail.com")
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(
            json.dumps(
                {
                    "username": "user@gmail.com",
                    "credentials": {
                        "token": "expired-token",
                        "refresh_token": "rt",
                        "scopes": SCOPES,
                    },
                }
            )
        )

        mock_creds = mocker.MagicMock(spec=RealCredentials)
        mock_creds.token = "refreshed-token"
        mock_creds.refresh_token = "rt"
        mock_creds.expired = True
        mock_creds.to_json.return_value = json.dumps(
            {
                "token": "refreshed-token",
                "refresh_token": "rt",
                "scopes": SCOPES,
            }
        )
        mocker.patch(
            "brandbox.providers.google.Credentials.from_authorized_user_info",
            return_value=mock_creds,
        )
        mocker.patch("brandbox.providers.google.Request")

        account = Account(username="user@gmail.com", provider_name="google")

        # Act
        token = provider.get_token(account)

        # Assert
        assert token == "refreshed-token"

    def test_get_token_raises_when_no_token_file(self, provider: GoogleProvider) -> None:
        """get_token raises RuntimeError when no token file exists."""
        # Arrange
        account = Account(username="missing@gmail.com", provider_name="google")

        # Act & Assert
        with pytest.raises(RuntimeError, match="No token found"):
            provider.get_token(account)

    # ── Contacts: get_contacts ───────────────────────────────────────

    def test_get_contacts_returns_mapped_contacts(self, mocker, provider: GoogleProvider) -> None:
        """get_contacts returns Contact objects from People API connections."""
        # Arrange
        mock_get = mocker.patch("brandbox.providers.google.requests.get")
        mock_get.return_value.json.return_value = {
            "connections": [
                {
                    "resourceName": "people/c1",
                    "names": [{"displayName": "Alice"}],
                    "emailAddresses": [{"value": "alice@co.com"}],
                },
                {
                    "resourceName": "people/c2",
                    "names": [{"displayName": "Bob"}],
                    "emailAddresses": [
                        {"value": "bob@work.com"},
                    ],
                },
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None

        # Act
        contacts = provider.get_contacts("some-token")

        # Assert
        assert len(contacts) == 2
        assert contacts[0].id == "people/c1"
        assert contacts[0].display_name == "Alice"
        assert contacts[0].emails == ["alice@co.com"]
        assert contacts[1].id == "people/c2"
        assert contacts[1].display_name == "Bob"
        assert contacts[1].emails == ["bob@work.com"]

    def test_get_contacts_filters_connections_without_email(
        self, mocker, provider: GoogleProvider
    ) -> None:
        """get_contacts excludes connections that have no emailAddresses."""
        # Arrange
        mock_get = mocker.patch("brandbox.providers.google.requests.get")
        mock_get.return_value.json.return_value = {
            "connections": [
                {
                    "resourceName": "people/c1",
                    "names": [{"displayName": "Has Email"}],
                    "emailAddresses": [{"value": "has@co.com"}],
                },
                {
                    "resourceName": "people/c2",
                    "names": [{"displayName": "No Email"}],
                    # no emailAddresses key
                },
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None

        # Act
        contacts = provider.get_contacts("token")

        # Assert
        assert len(contacts) == 1
        assert contacts[0].id == "people/c1"

    def test_get_contacts_empty_connections(self, mocker, provider: GoogleProvider) -> None:
        """get_contacts returns [] when connections list is empty."""
        # Arrange
        mock_get = mocker.patch("brandbox.providers.google.requests.get")
        mock_get.return_value.json.return_value = {"connections": []}
        mock_get.return_value.raise_for_status.return_value = None

        # Act
        contacts = provider.get_contacts("token")

        # Assert
        assert contacts == []

    def test_get_contacts_uses_correct_endpoint(self, mocker, provider: GoogleProvider) -> None:
        """get_contacts hits the correct People API URL and params."""
        # Arrange
        mock_get = mocker.patch("brandbox.providers.google.requests.get")
        mock_get.return_value.json.return_value = {"connections": []}
        mock_get.return_value.raise_for_status.return_value = None

        # Act
        provider.get_contacts("token")

        # Assert
        url = mock_get.call_args[0][0]
        assert url == f"{PEOPLE_BASE}/people/me/connections"
        assert mock_get.call_args[1]["params"]["personFields"] == "names,emailAddresses"

    # ── Recent senders: get_recent_senders ───────────────────────────

    def test_get_recent_senders_returns_emails(self, mocker, provider: GoogleProvider) -> None:
        """get_recent_senders returns email addresses from otherContacts."""
        # Arrange
        mock_get = mocker.patch("brandbox.providers.google.requests.get")
        mock_get.return_value.json.return_value = {
            "otherContacts": [
                {
                    "emailAddresses": [
                        {"value": "  Sender@Co.com  "},
                    ],
                },
                {
                    "emailAddresses": [
                        {"value": "other@work.com"},
                    ],
                },
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None

        # Act
        senders = provider.get_recent_senders("token", limit=100)

        # Assert
        assert senders == {"sender@co.com", "other@work.com"}

    def test_get_recent_senders_deduplicates(self, mocker, provider: GoogleProvider) -> None:
        """get_recent_senders returns unique email addresses."""
        # Arrange
        mock_get = mocker.patch("brandbox.providers.google.requests.get")
        mock_get.return_value.json.return_value = {
            "otherContacts": [
                {"emailAddresses": [{"value": "same@co.com"}]},
                {"emailAddresses": [{"value": "same@co.com"}]},
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None

        # Act
        senders = provider.get_recent_senders("token", limit=100)

        # Assert
        assert senders == {"same@co.com"}

    def test_get_recent_senders_handles_missing_email_addresses(
        self, mocker, provider: GoogleProvider
    ) -> None:
        """get_recent_senders skips persons with no emailAddresses."""
        # Arrange
        mock_get = mocker.patch("brandbox.providers.google.requests.get")
        mock_get.return_value.json.return_value = {
            "otherContacts": [
                {"emailAddresses": [{"value": "has@co.com"}]},
                {"names": [{"displayName": "No Email"}]},
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None

        # Act
        senders = provider.get_recent_senders("token", limit=100)

        # Assert
        assert senders == {"has@co.com"}

    def test_get_recent_senders_skips_email_without_value(
        self, mocker, provider: GoogleProvider
    ) -> None:
        """get_recent_senders skips emailAddresses entries missing value."""
        # Arrange
        mock_get = mocker.patch("brandbox.providers.google.requests.get")
        mock_get.return_value.json.return_value = {
            "otherContacts": [
                {
                    "emailAddresses": [
                        {"value": "good@co.com"},
                        {"type": "work"},
                    ],
                },
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None

        # Act
        senders = provider.get_recent_senders("token", limit=100)

        # Assert
        assert senders == {"good@co.com"}

    def test_get_recent_senders_empty_response(self, mocker, provider: GoogleProvider) -> None:
        """get_recent_senders returns empty set when no otherContacts."""
        # Arrange
        mock_get = mocker.patch("brandbox.providers.google.requests.get")
        mock_get.return_value.json.return_value = {"otherContacts": []}
        mock_get.return_value.raise_for_status.return_value = None

        # Act
        senders = provider.get_recent_senders("token", limit=100)

        # Assert
        assert senders == set()

    def test_get_recent_senders_uses_correct_endpoint(
        self, mocker, provider: GoogleProvider
    ) -> None:
        """get_recent_senders hits the correct People API otherContacts URL."""
        # Arrange
        mock_get = mocker.patch("brandbox.providers.google.requests.get")
        mock_get.return_value.json.return_value = {"otherContacts": []}
        mock_get.return_value.raise_for_status.return_value = None

        # Act
        provider.get_recent_senders("token", limit=100)

        # Assert
        url = mock_get.call_args[0][0]
        assert url == f"{PEOPLE_BASE}/otherContacts"
        assert mock_get.call_args[1]["params"]["readMask"] == "names,emailAddresses"

    # ── Contact CRUD: create_contact, set_contact_photo ──────────────

    def test_create_contact_returns_resource_name_on_201(
        self, mocker, provider: GoogleProvider
    ) -> None:
        """create_contact returns resourceName when API returns 201."""
        # Arrange
        mock_post = mocker.patch("brandbox.providers.google.requests.post")
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {"resourceName": "people/cNew"}
        mock_post.return_value.raise_for_status.return_value = None

        # Act
        result = provider.create_contact("token", "New Person", "new@co.com")

        # Assert
        assert result == "people/cNew"
        mock_post.assert_called_once_with(
            f"{PEOPLE_BASE}/people:createContact",
            headers={
                "Authorization": "Bearer token",
                "Content-Type": "application/json",
            },
            json={
                "names": [{"displayName": "New Person"}],
                "emailAddresses": [{"value": "new@co.com"}],
            },
            timeout=20,
        )

    def test_create_contact_returns_resource_name_on_200(
        self, mocker, provider: GoogleProvider
    ) -> None:
        """create_contact returns resourceName when API returns 200."""
        # Arrange
        mock_post = mocker.patch("brandbox.providers.google.requests.post")
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"resourceName": "people/cUpdated"}

        # Act
        result = provider.create_contact("token", "Name", "e@co.com")

        # Assert
        assert result == "people/cUpdated"

    def test_create_contact_returns_none_on_failure(self, mocker, provider: GoogleProvider) -> None:
        """create_contact returns None when API returns non-2xx."""
        # Arrange
        mock_post = mocker.patch("brandbox.providers.google.requests.post")
        mock_post.return_value.status_code = 409

        # Act
        result = provider.create_contact("token", "Name", "e@co.com")

        # Assert
        assert result is None

    def test_create_contact_returns_none_when_resource_name_missing(
        self, mocker, provider: GoogleProvider
    ) -> None:
        """create_contact returns None when success response lacks resourceName."""
        # Arrange
        mock_post = mocker.patch("brandbox.providers.google.requests.post")
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {}

        # Act
        result = provider.create_contact("token", "Name", "e@co.com")

        # Assert
        assert result is None

    def test_set_contact_photo_returns_true_on_200(self, mocker, provider: GoogleProvider) -> None:
        """set_contact_photo returns True when API returns 200."""
        # Arrange
        import base64

        mock_post = mocker.patch("brandbox.providers.google.requests.post")
        mock_post.return_value.status_code = 200
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
        expected_b64 = base64.b64encode(png_bytes).decode("utf-8")

        # Act
        result = provider.set_contact_photo("token", "people/c123", png_bytes)

        # Assert
        assert result is True
        mock_post.assert_called_once_with(
            f"{PEOPLE_BASE}/people/c123:updateContactPhoto",
            headers={
                "Authorization": "Bearer token",
                "Content-Type": "application/json",
            },
            json={
                "photoBytes": expected_b64,
                "personFields": "photos",
            },
            timeout=30,
        )

    def test_set_contact_photo_returns_false_on_non_200(
        self, mocker, provider: GoogleProvider
    ) -> None:
        """set_contact_photo returns False when API returns non-200."""
        # Arrange
        mock_post = mocker.patch("brandbox.providers.google.requests.post")
        mock_post.return_value.status_code = 204  # not 200 -> False

        # Act
        result = provider.set_contact_photo("token", "people/c1", b"fake-png")

        # Assert
        assert result is False

    def test_set_contact_photo_returns_false_on_4xx(self, mocker, provider: GoogleProvider) -> None:
        """set_contact_photo returns False when API returns 4xx."""
        # Arrange
        mock_post = mocker.patch("brandbox.providers.google.requests.post")
        mock_post.return_value.status_code = 403

        # Act
        result = provider.set_contact_photo("token", "people/c1", b"fake-png")

        # Assert
        assert result is False

    def test_set_contact_photo_sends_base64_encoded_bytes(
        self, mocker, provider: GoogleProvider
    ) -> None:
        """set_contact_photo sends base64-encoded PNG in request body."""
        # Arrange
        import base64

        mock_post = mocker.patch("brandbox.providers.google.requests.post")
        mock_post.return_value.status_code = 200
        raw_png = b"\x89PNG\x00\x01\x02"
        expected_b64 = base64.b64encode(raw_png).decode("utf-8")

        # Act
        provider.set_contact_photo("token", "people/c1", raw_png)

        # Assert
        sent_json = mock_post.call_args[1]["json"]
        assert sent_json["photoBytes"] == expected_b64

    # ── Provider name ────────────────────────────────────────────────

    def test_provider_name_is_google(self) -> None:
        """Provider name is correctly set to 'google'."""
        assert GoogleProvider.name == "google"
