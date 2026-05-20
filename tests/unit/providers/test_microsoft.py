"""Tests for the Microsoft 365 provider."""

from __future__ import annotations

from pathlib import Path

import pytest
import requests

from brandbox.providers.base import Account
from brandbox.providers.microsoft import (
    AUTHORITY,
    GRAPH_BASE,
    SCOPES,
    MicrosoftProvider,
)


class TestMicrosoftProvider:
    """Test suite for MicrosoftProvider."""

    # ── Fixtures ─────────────────────────────────────────────────────────────

    # ── Internal helpers: _load_cache, _save_cache, _app, _headers, _get_paged ──

    def test_constructor_creates_empty_cache_when_no_file(self, mocker, tmp_path: Path) -> None:
        """Token file missing -> creates a fresh empty cache without deserialize."""
        # Arrange
        mock_cache_cls = mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        token_file = tmp_path / "token.json"

        # Act
        provider = MicrosoftProvider("test-client-id", token_file)

        # Assert
        assert provider._client_id == "test-client-id"
        assert provider._token_file == token_file
        mock_cache_cls.assert_called_once()
        mock_cache_cls.return_value.deserialize.assert_not_called()

    def test_constructor_loads_existing_cache(self, mocker, tmp_path: Path) -> None:
        """Token file exists -> deserializes cache from file contents."""
        # Arrange
        mock_cache_cls = mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        token_file = tmp_path / "token.json"
        token_file.write_text('{"some": "cached-data"}')

        # Act
        MicrosoftProvider("test-client-id", token_file)

        # Assert
        mock_cache_cls.return_value.deserialize.assert_called_once_with('{"some": "cached-data"}')

    def test_constructor_uses_provided_client_id_and_token_file(
        self, mocker, tmp_path: Path
    ) -> None:
        """Constructor stores the exact client_id and token_file passed in."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        token_file = tmp_path / "nested" / "token.json"

        # Act
        provider = MicrosoftProvider("my-app-id", token_file)

        # Assert
        assert provider._client_id == "my-app-id"
        assert provider._token_file == token_file

    def test_save_cache_writes_when_state_changed(self, mocker, tmp_path: Path) -> None:
        """_save_cache writes serialized cache to file only when state changed."""
        # Arrange
        mock_cache_cls = mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_cache_cls.return_value.has_state_changed = True
        mock_cache_cls.return_value.serialize.return_value = "serialized-data"
        token_file = tmp_path / "token.json"
        provider = MicrosoftProvider("test-client-id", token_file)

        # Act
        provider._save_cache()

        # Assert
        assert token_file.read_text() == "serialized-data"
        mock_cache_cls.return_value.serialize.assert_called_once()

    def test_save_cache_does_nothing_when_not_changed(self, mocker, tmp_path: Path) -> None:
        """_save_cache does nothing when has_state_changed is False."""
        # Arrange
        mock_cache_cls = mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_cache_cls.return_value.has_state_changed = False
        token_file = tmp_path / "token.json"
        provider = MicrosoftProvider("test-client-id", token_file)

        # Act
        provider._save_cache()

        # Assert
        assert not token_file.exists()
        mock_cache_cls.return_value.serialize.assert_not_called()

    def test_save_cache_creates_parent_directory(self, mocker, tmp_path: Path) -> None:
        """_save_cache creates parent dirs when they don't exist."""
        # Arrange
        mock_cache_cls = mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_cache_cls.return_value.has_state_changed = True
        mock_cache_cls.return_value.serialize.return_value = "data"
        token_file = tmp_path / "a" / "b" / "token.json"
        provider = MicrosoftProvider("test-client-id", token_file)

        # Act
        provider._save_cache()

        # Assert
        assert token_file.exists()
        assert token_file.read_text() == "data"

    def test_app_creates_public_client_application(self, mocker, tmp_path: Path) -> None:
        """_app() creates PublicClientApplication with correct parameters."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_app_cls = mocker.patch("brandbox.providers.microsoft.msal.PublicClientApplication")
        provider = MicrosoftProvider("test-client-id", tmp_path / "token.json")

        # Act
        app = provider._app()

        # Assert
        mock_app_cls.assert_called_once_with(
            "test-client-id", authority=AUTHORITY, token_cache=provider._cache
        )
        assert app == mock_app_cls.return_value

    def test_headers_returns_bearer_dict(self, mocker, tmp_path: Path) -> None:
        """_headers returns dict with Authorization Bearer header."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        result = provider._headers("token-abc")

        # Assert
        assert result == {"Authorization": "Bearer token-abc"}

    def test_get_paged_single_page(self, mocker, tmp_path: Path) -> None:
        """_get_paged returns all items from a single-page response."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_get = mocker.patch("brandbox.providers.microsoft.requests.get")
        mock_get.return_value.json.return_value = {"value": [{"id": "1"}, {"id": "2"}]}
        mock_get.return_value.raise_for_status.return_value = None
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        items = provider._get_paged("token", "https://graph.example.com/items")

        # Assert
        assert items == [{"id": "1"}, {"id": "2"}]
        mock_get.assert_called_once_with(
            "https://graph.example.com/items",
            headers={"Authorization": "Bearer token"},
            timeout=30,
        )

    def test_get_paged_multiple_pages(self, mocker, tmp_path: Path) -> None:
        """_get_paged follows @odata.nextLink to collect all pages."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_get = mocker.patch("brandbox.providers.microsoft.requests.get")
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.json.side_effect = [
            {
                "value": [{"id": "1"}],
                "@odata.nextLink": "https://graph.example.com/next",
            },
            {
                "value": [{"id": "2"}],
                "@odata.nextLink": None,
            },
        ]
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        items = provider._get_paged("token", "https://graph.example.com/first")

        # Assert
        assert items == [{"id": "1"}, {"id": "2"}]
        assert mock_get.call_count == 2
        assert mock_get.call_args_list[1][0][0] == "https://graph.example.com/next"

    def test_get_paged_empty_response(self, mocker, tmp_path: Path) -> None:
        """_get_paged returns [] when response has no 'value' key."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_get = mocker.patch("brandbox.providers.microsoft.requests.get")
        mock_get.return_value.json.return_value = {}
        mock_get.return_value.raise_for_status.return_value = None
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        items = provider._get_paged("token", "https://graph.example.com/items")

        # Assert
        assert items == []

    def test_get_paged_raises_on_http_error(self, mocker, tmp_path: Path) -> None:
        """_get_paged raises when the HTTP request fails."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_get = mocker.patch("brandbox.providers.microsoft.requests.get")
        mock_get.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "403 Forbidden"
        )
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act & Assert
        with pytest.raises(requests.exceptions.HTTPError):
            provider._get_paged("token", "https://graph.example.com/items")

    # ── Auth: start_auth ────────────────────────────────────────────

    def test_start_auth_successful_device_flow(self, mocker, tmp_path: Path) -> None:
        """start_auth returns device_code dict with URL, code, and flow."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_app_cls = mocker.patch("brandbox.providers.microsoft.msal.PublicClientApplication")
        mock_app_cls.return_value.initiate_device_flow.return_value = {
            "user_code": "ABC123",
            "message": (
                "To sign in, use a web browser to open the page "
                "https://microsoft.com/devicelogin and enter the code "
                "ABC123 to authenticate."
            ),
        }
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        result = provider.start_auth()

        # Assert
        assert result["type"] == "device_code"
        assert result["url"] == "https://microsoft.com/devicelogin"
        assert result["code"] == "ABC123"
        assert "_flow" in result
        assert result["_flow"]["user_code"] == "ABC123"
        mock_app_cls.return_value.initiate_device_flow.assert_called_once_with(scopes=SCOPES)

    def test_start_auth_raises_when_device_flow_fails(self, mocker, tmp_path: Path) -> None:
        """start_auth raises RuntimeError when device flow lacks user_code."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_app_cls = mocker.patch("brandbox.providers.microsoft.msal.PublicClientApplication")
        mock_app_cls.return_value.initiate_device_flow.return_value = {
            "error": "invalid_client",
            "error_description": "Bad client ID",
        }
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Device flow failed"):
            provider.start_auth()

    def test_start_auth_parses_url_from_msal_message(self, mocker, tmp_path: Path) -> None:
        """start_auth extracts URL from MSAL message when format varies."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_app_cls = mocker.patch("brandbox.providers.microsoft.msal.PublicClientApplication")
        mock_app_cls.return_value.initiate_device_flow.return_value = {
            "user_code": "DEF456",
            "message": "Open https://mysite.com/auth and enter the code DEF456 to authenticate.",
        }
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        result = provider.start_auth()

        # Assert
        assert result["url"] == "https://mysite.com/auth"
        assert result["code"] == "DEF456"

    def test_start_auth_fallback_url_and_code_when_message_malformed(
        self, mocker, tmp_path: Path
    ) -> None:
        """start_auth falls back to defaults when message is empty."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_app_cls = mocker.patch("brandbox.providers.microsoft.msal.PublicClientApplication")
        mock_app_cls.return_value.initiate_device_flow.return_value = {
            "user_code": "GHI789",
            "message": "",
        }
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        result = provider.start_auth()

        # Assert
        assert result["url"] == "https://microsoft.com/devicelogin"
        assert result["code"] == ""

    # ── Auth: finish_auth ───────────────────────────────────────────

    def test_finish_auth_returns_username(self, mocker, tmp_path: Path) -> None:
        """finish_auth acquires token and returns last account username."""
        # Arrange
        mock_cache_cls = mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_app_cls = mocker.patch("brandbox.providers.microsoft.msal.PublicClientApplication")
        mock_app_cls.return_value.acquire_token_by_device_flow.return_value = {
            "access_token": "at-123",
        }
        mock_app_cls.return_value.get_accounts.return_value = [
            {"username": "user1@co.com"},
            {"username": "user2@co.com"},
        ]
        mock_cache_cls.return_value.has_state_changed = True
        mock_cache_cls.return_value.serialize.return_value = "{}"
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        username = provider.finish_auth({"_flow": {"some": "flow"}})

        # Assert
        assert username == "user2@co.com"
        mock_app_cls.return_value.acquire_token_by_device_flow.assert_called_once_with(
            {"some": "flow"}
        )

    def test_finish_auth_falls_back_to_id_token_when_no_accounts(
        self, mocker, tmp_path: Path
    ) -> None:
        """finish_auth uses id_token_claims when no accounts in cache."""
        # Arrange
        mock_cache_cls = mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_cache_cls.return_value.has_state_changed = True
        mock_cache_cls.return_value.serialize.return_value = "{}"
        mock_app_cls = mocker.patch("brandbox.providers.microsoft.msal.PublicClientApplication")
        mock_app_cls.return_value.acquire_token_by_device_flow.return_value = {
            "access_token": "at-123",
            "id_token_claims": {"preferred_username": "fallback@co.com"},
        }
        mock_app_cls.return_value.get_accounts.return_value = []
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        username = provider.finish_auth({"_flow": {}})

        # Assert
        assert username == "fallback@co.com"

    def test_finish_auth_returns_unknown_when_no_username_source(
        self, mocker, tmp_path: Path
    ) -> None:
        """finish_auth returns 'unknown' when no accounts or id_token_claims."""
        # Arrange
        mock_cache_cls = mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_cache_cls.return_value.has_state_changed = True
        mock_cache_cls.return_value.serialize.return_value = "{}"
        mock_app_cls = mocker.patch("brandbox.providers.microsoft.msal.PublicClientApplication")
        mock_app_cls.return_value.acquire_token_by_device_flow.return_value = {
            "access_token": "at-123",
        }
        mock_app_cls.return_value.get_accounts.return_value = []
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        username = provider.finish_auth({"_flow": {}})

        # Assert
        assert username == "unknown"

    def test_finish_auth_raises_when_acquisition_fails(self, mocker, tmp_path: Path) -> None:
        """finish_auth raises RuntimeError when token acquisition fails."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_app_cls = mocker.patch("brandbox.providers.microsoft.msal.PublicClientApplication")
        mock_app_cls.return_value.acquire_token_by_device_flow.return_value = {
            "error": "access_denied",
            "error_description": "User cancelled",
        }
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Authentication failed"):
            provider.finish_auth({"_flow": {}})

    def test_finish_auth_calls_save_cache(self, mocker, tmp_path: Path) -> None:
        """finish_auth persists cache after successful token acquisition."""
        # Arrange
        mock_cache_cls = mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_cache_cls.return_value.has_state_changed = True
        mock_cache_cls.return_value.serialize.return_value = "fresh-cache"
        mock_app_cls = mocker.patch("brandbox.providers.microsoft.msal.PublicClientApplication")
        mock_app_cls.return_value.acquire_token_by_device_flow.return_value = {
            "access_token": "at-123",
        }
        mock_app_cls.return_value.get_accounts.return_value = [
            {"username": "user@co.com"},
        ]
        token_file = tmp_path / "token.json"
        provider = MicrosoftProvider("test-id", token_file)

        # Act
        provider.finish_auth({"_flow": {}})

        # Assert
        assert token_file.read_text() == "fresh-cache"

    # ── Account management: get_accounts, get_token ──────────────────

    def test_get_accounts_returns_list(self, mocker, tmp_path: Path) -> None:
        """get_accounts returns Account objects from MSAL accounts."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_app_cls = mocker.patch("brandbox.providers.microsoft.msal.PublicClientApplication")
        mock_app_cls.return_value.get_accounts.return_value = [
            {"username": "alice@co.com"},
            {"username": "bob@co.com"},
        ]
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        accounts = provider.get_accounts()

        # Assert
        assert len(accounts) == 2
        assert accounts[0] == Account(username="alice@co.com", provider_name="microsoft")
        assert accounts[1] == Account(username="bob@co.com", provider_name="microsoft")

    def test_get_accounts_empty(self, mocker, tmp_path: Path) -> None:
        """get_accounts returns [] when no MSAL accounts."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_app_cls = mocker.patch("brandbox.providers.microsoft.msal.PublicClientApplication")
        mock_app_cls.return_value.get_accounts.return_value = []
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        accounts = provider.get_accounts()

        # Assert
        assert accounts == []

    def test_get_token_found(self, mocker, tmp_path: Path) -> None:
        """get_token returns access token when account is found."""
        # Arrange
        mock_cache = mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_cache.return_value.has_state_changed = True
        mock_cache.return_value.serialize.return_value = "{}"
        mock_app_cls = mocker.patch("brandbox.providers.microsoft.msal.PublicClientApplication")
        mock_app_cls.return_value.get_accounts.return_value = [
            {"username": "user@co.com"},
        ]
        mock_app_cls.return_value.acquire_token_silent.return_value = {
            "access_token": "silent-token",
        }
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")
        account = Account(username="user@co.com", provider_name="microsoft")

        # Act
        token = provider.get_token(account)

        # Assert
        assert token == "silent-token"
        mock_app_cls.return_value.acquire_token_silent.assert_called_once_with(
            SCOPES, account={"username": "user@co.com"}
        )

    def test_get_token_account_not_found(self, mocker, tmp_path: Path) -> None:
        """get_token raises RuntimeError when account not in cache."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_app_cls = mocker.patch("brandbox.providers.microsoft.msal.PublicClientApplication")
        mock_app_cls.return_value.get_accounts.return_value = [
            {"username": "other@co.com"},
        ]
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")
        account = Account(username="missing@co.com", provider_name="microsoft")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Account missing@co.com not found"):
            provider.get_token(account)

    def test_get_token_silent_acquisition_fails(self, mocker, tmp_path: Path) -> None:
        """get_token raises RuntimeError when silent acquisition fails."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_app_cls = mocker.patch("brandbox.providers.microsoft.msal.PublicClientApplication")
        mock_app_cls.return_value.get_accounts.return_value = [
            {"username": "user@co.com"},
        ]
        mock_app_cls.return_value.acquire_token_silent.return_value = None
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")
        account = Account(username="user@co.com", provider_name="microsoft")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Could not refresh token"):
            provider.get_token(account)

    def test_get_token_silent_acquisition_returns_dict_without_access_token(
        self, mocker, tmp_path: Path
    ) -> None:
        """get_token raises when silent result lacks access_token."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_app_cls = mocker.patch("brandbox.providers.microsoft.msal.PublicClientApplication")
        mock_app_cls.return_value.get_accounts.return_value = [
            {"username": "user@co.com"},
        ]
        mock_app_cls.return_value.acquire_token_silent.return_value = {
            "error": "token_expired",
        }
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")
        account = Account(username="user@co.com", provider_name="microsoft")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Could not refresh token"):
            provider.get_token(account)

    def test_get_token_calls_save_cache(self, mocker, tmp_path: Path) -> None:
        """get_token persists cache after successful token acquisition."""
        # Arrange
        mock_cache_cls = mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_cache_cls.return_value.has_state_changed = True
        mock_cache_cls.return_value.serialize.return_value = "post-token-cache"
        mock_app_cls = mocker.patch("brandbox.providers.microsoft.msal.PublicClientApplication")
        mock_app_cls.return_value.get_accounts.return_value = [
            {"username": "user@co.com"},
        ]
        mock_app_cls.return_value.acquire_token_silent.return_value = {
            "access_token": "tok",
        }
        token_file = tmp_path / "token.json"
        provider = MicrosoftProvider("test-id", token_file)
        account = Account(username="user@co.com", provider_name="microsoft")

        # Act
        provider.get_token(account)

        # Assert
        assert token_file.read_text() == "post-token-cache"

    # ── Contacts: get_contacts ──────────────────────────────────────

    def test_get_contacts_returns_mapped_contacts(self, mocker, tmp_path: Path) -> None:
        """get_contacts returns Contact objects mapped from Graph response."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_get = mocker.patch("brandbox.providers.microsoft.requests.get")
        mock_get.return_value.json.return_value = {
            "value": [
                {
                    "id": "c1",
                    "displayName": "Alice",
                    "emailAddresses": [{"address": "alice@co.com"}],
                },
                {
                    "id": "c2",
                    "displayName": "Bob",
                    "emailAddresses": [
                        {"address": "bob@work.com"},
                        {"address": "bob@pers.com"},
                    ],
                },
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        contacts = provider.get_contacts("some-token")

        # Assert
        assert len(contacts) == 2
        assert contacts[0].id == "c1"
        assert contacts[0].display_name == "Alice"
        assert contacts[0].emails == ["alice@co.com"]
        assert contacts[1].id == "c2"
        assert contacts[1].display_name == "Bob"
        assert contacts[1].emails == ["bob@work.com", "bob@pers.com"]

    def test_get_contacts_handles_missing_email_addresses(self, mocker, tmp_path: Path) -> None:
        """get_contacts assigns empty emails list when emailAddresses missing."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_get = mocker.patch("brandbox.providers.microsoft.requests.get")
        mock_get.return_value.json.return_value = {
            "value": [
                {
                    "id": "c1",
                    "displayName": "No Email",
                },
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        contacts = provider.get_contacts("token")

        # Assert
        assert len(contacts) == 1
        assert contacts[0].id == "c1"
        assert contacts[0].display_name == "No Email"
        assert contacts[0].emails == []

    def test_get_contacts_handles_null_display_name(self, mocker, tmp_path: Path) -> None:
        """get_contacts uses empty string when displayName is missing."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_get = mocker.patch("brandbox.providers.microsoft.requests.get")
        mock_get.return_value.json.return_value = {
            "value": [
                {
                    "id": "c1",
                    "emailAddresses": [{"address": "anon@co.com"}],
                },
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        contacts = provider.get_contacts("token")

        # Assert
        assert contacts[0].display_name == ""

    def test_get_contacts_skips_email_without_address_key(self, mocker, tmp_path: Path) -> None:
        """get_contacts filters out emailAddresses entries missing 'address'."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_get = mocker.patch("brandbox.providers.microsoft.requests.get")
        mock_get.return_value.json.return_value = {
            "value": [
                {
                    "id": "c1",
                    "displayName": "Partial",
                    "emailAddresses": [
                        {"name": "No Address Key"},
                    ],
                },
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        contacts = provider.get_contacts("token")

        # Assert
        assert contacts[0].emails == []

    def test_get_contacts_raises_when_id_missing(self, mocker, tmp_path: Path) -> None:
        """get_contacts lets KeyError propagate when contact has no id."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_get = mocker.patch("brandbox.providers.microsoft.requests.get")
        mock_get.return_value.json.return_value = {
            "value": [
                {"displayName": "No ID"},
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act & Assert
        with pytest.raises(KeyError):
            provider.get_contacts("token")

    def test_get_contacts_empty_response(self, mocker, tmp_path: Path) -> None:
        """get_contacts returns [] when Graph returns no contacts."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_get = mocker.patch("brandbox.providers.microsoft.requests.get")
        mock_get.return_value.json.return_value = {"value": []}
        mock_get.return_value.raise_for_status.return_value = None
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        contacts = provider.get_contacts("token")

        # Assert
        assert contacts == []

    # ── Recent senders: get_recent_senders ───────────────────────────

    def test_get_recent_senders_returns_lowered_stripped_emails(
        self, mocker, tmp_path: Path
    ) -> None:
        """get_recent_senders returns sender emails lowered and stripped."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_get = mocker.patch("brandbox.providers.microsoft.requests.get")
        mock_get.return_value.json.return_value = {
            "value": [
                {"from": {"emailAddress": {"address": "  Alice@Co.com  "}}},
                {"from": {"emailAddress": {"address": "BOB@WORK.COM"}}},
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        senders = provider.get_recent_senders("token", limit=10)

        # Assert
        assert senders == {"alice@co.com", "bob@work.com"}

    def test_get_recent_senders_deduplicates(self, mocker, tmp_path: Path) -> None:
        """get_recent_senders returns unique email addresses via set."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_get = mocker.patch("brandbox.providers.microsoft.requests.get")
        mock_get.return_value.json.return_value = {
            "value": [
                {"from": {"emailAddress": {"address": "alice@co.com"}}},
                {"from": {"emailAddress": {"address": "alice@co.com"}}},
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        senders = provider.get_recent_senders("token", limit=10)

        # Assert
        assert senders == {"alice@co.com"}

    def test_get_recent_senders_skips_missing_from_key(self, mocker, tmp_path: Path) -> None:
        """get_recent_senders skips messages without 'from' key."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_get = mocker.patch("brandbox.providers.microsoft.requests.get")
        mock_get.return_value.json.return_value = {
            "value": [
                {"from": {"emailAddress": {"address": "alice@co.com"}}},
                {"no_from": True},
                {"from": {"emailAddress": {"address": "bob@co.com"}}},
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        senders = provider.get_recent_senders("token", limit=10)

        # Assert
        assert senders == {"alice@co.com", "bob@co.com"}

    def test_get_recent_senders_skips_missing_email_address(self, mocker, tmp_path: Path) -> None:
        """get_recent_senders skips messages without emailAddress key."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_get = mocker.patch("brandbox.providers.microsoft.requests.get")
        mock_get.return_value.json.return_value = {
            "value": [
                {"from": {"emailAddress": {"address": "alice@co.com"}}},
                {"from": {"no_address": True}},
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        senders = provider.get_recent_senders("token", limit=10)

        # Assert
        assert senders == {"alice@co.com"}

    def test_get_recent_senders_skips_none_address(self, mocker, tmp_path: Path) -> None:
        """get_recent_senders skips when address value is None."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_get = mocker.patch("brandbox.providers.microsoft.requests.get")
        mock_get.return_value.json.return_value = {
            "value": [
                {"from": {"emailAddress": {"address": None}}},
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        senders = provider.get_recent_senders("token", limit=10)

        # Assert
        assert senders == set()

    def test_get_recent_senders_respects_limit(self, mocker, tmp_path: Path) -> None:
        """get_recent_senders passes min(limit, 999) as $top parameter."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_get = mocker.patch("brandbox.providers.microsoft.requests.get")
        mock_get.return_value.json.return_value = {"value": []}
        mock_get.return_value.raise_for_status.return_value = None
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        provider.get_recent_senders("token", limit=50)

        # Assert
        url = mock_get.call_args[0][0]
        assert "$top=50" in url

    def test_get_recent_senders_caps_limit_at_999(self, mocker, tmp_path: Path) -> None:
        """get_recent_senders caps $top at 999 per Graph API limit."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_get = mocker.patch("brandbox.providers.microsoft.requests.get")
        mock_get.return_value.json.return_value = {"value": []}
        mock_get.return_value.raise_for_status.return_value = None
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        provider.get_recent_senders("token", limit=9999)

        # Assert
        url = mock_get.call_args[0][0]
        assert "$top=999" in url

    def test_get_recent_senders_uses_correct_graph_endpoint(self, mocker, tmp_path: Path) -> None:
        """get_recent_senders hits the correct Graph inbox messages URL."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_get = mocker.patch("brandbox.providers.microsoft.requests.get")
        mock_get.return_value.json.return_value = {"value": []}
        mock_get.return_value.raise_for_status.return_value = None
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        provider.get_recent_senders("token", limit=10)

        # Assert
        url = mock_get.call_args[0][0]
        assert url.startswith(f"{GRAPH_BASE}/me/mailFolders/inbox/messages")
        assert "$select=from" in url
        assert "$orderby=receivedDateTime desc" in url

    # ── Contact CRUD: create_contact, set_contact_photo ──────────────

    def test_create_contact_returns_id_on_201(self, mocker, tmp_path: Path) -> None:
        """create_contact returns contact id when API returns 201."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_post = mocker.patch("brandbox.providers.microsoft.requests.post")
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {"id": "new-contact-id"}
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        result = provider.create_contact("token", "New Person", "new@co.com")

        # Assert
        assert result == "new-contact-id"
        mock_post.assert_called_once_with(
            f"{GRAPH_BASE}/me/contacts",
            headers={
                "Authorization": "Bearer token",
                "Content-Type": "application/json",
            },
            json={
                "displayName": "New Person",
                "emailAddresses": [{"address": "new@co.com", "name": "New Person"}],
            },
            timeout=20,
        )

    def test_create_contact_returns_id_on_200(self, mocker, tmp_path: Path) -> None:
        """create_contact returns contact id when API returns 200."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_post = mocker.patch("brandbox.providers.microsoft.requests.post")
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"id": "updated-id"}
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        result = provider.create_contact("token", "Name", "e@co.com")

        # Assert
        assert result == "updated-id"

    def test_create_contact_returns_none_on_failure(self, mocker, tmp_path: Path) -> None:
        """create_contact returns None when API returns non-2xx."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_post = mocker.patch("brandbox.providers.microsoft.requests.post")
        mock_post.return_value.status_code = 400
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        result = provider.create_contact("token", "Name", "e@co.com")

        # Assert
        assert result is None

    def test_create_contact_returns_none_when_id_missing(self, mocker, tmp_path: Path) -> None:
        """create_contact returns None when success response lacks 'id'."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_post = mocker.patch("brandbox.providers.microsoft.requests.post")
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {}
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        result = provider.create_contact("token", "Name", "e@co.com")

        # Assert
        assert result is None

    def test_create_contact_non_json_response_raises(self, mocker, tmp_path: Path) -> None:
        """create_contact propagates exception when JSON parsing fails."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_post = mocker.patch("brandbox.providers.microsoft.requests.post")
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.side_effect = ValueError("Expecting value")
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act & Assert
        with pytest.raises(ValueError, match="Expecting value"):
            provider.create_contact("token", "Name", "e@co.com")

    def test_set_contact_photo_returns_true_on_200(self, mocker, tmp_path: Path) -> None:
        """set_contact_photo returns True when API returns 200."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_put = mocker.patch("brandbox.providers.microsoft.requests.put")
        mock_put.return_value.status_code = 200
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20

        # Act
        result = provider.set_contact_photo("token", "c123", png_bytes)

        # Assert
        assert result is True
        mock_put.assert_called_once_with(
            f"{GRAPH_BASE}/me/contacts/c123/photo/$value",
            headers={
                "Authorization": "Bearer token",
                "Content-Type": "image/png",
            },
            data=png_bytes,
            timeout=30,
        )

    def test_set_contact_photo_returns_true_on_204(self, mocker, tmp_path: Path) -> None:
        """set_contact_photo returns True when API returns 204."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_put = mocker.patch("brandbox.providers.microsoft.requests.put")
        mock_put.return_value.status_code = 204
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        result = provider.set_contact_photo("token", "c123", b"fake-png")

        # Assert
        assert result is True

    def test_set_contact_photo_returns_false_on_failure(self, mocker, tmp_path: Path) -> None:
        """set_contact_photo returns False when API returns 4xx/5xx."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_put = mocker.patch("brandbox.providers.microsoft.requests.put")
        mock_put.return_value.status_code = 403
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        result = provider.set_contact_photo("token", "c123", b"fake-png")

        # Assert
        assert result is False

    # ── Constructor edge cases ───────────────────────────────────────

    def test_constructor_handles_empty_token_file(self, mocker, tmp_path: Path) -> None:
        """Constructor handles empty token file gracefully."""
        # Arrange
        mock_cache_cls = mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        token_file = tmp_path / "token.json"
        token_file.write_text("")

        # Act
        provider = MicrosoftProvider("test-id", token_file)

        # Assert
        mock_cache_cls.return_value.deserialize.assert_called_once_with("")
        assert provider._cache == mock_cache_cls.return_value

    def test_start_auth_uses_correct_scopes(self, mocker, tmp_path: Path) -> None:
        """start_auth passes correct scopes to MSAL device flow."""
        # Arrange
        mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_app_cls = mocker.patch("brandbox.providers.microsoft.msal.PublicClientApplication")
        mock_app_cls.return_value.initiate_device_flow.return_value = {
            "user_code": "X",
            "message": "Open https://microsoft.com/devicelogin and enter code X.",
        }
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        provider.start_auth()

        # Assert
        mock_app_cls.return_value.initiate_device_flow.assert_called_once_with(scopes=SCOPES)

    def test_get_token_uses_next_to_find_account(self, mocker, tmp_path: Path) -> None:
        """get_token uses next() to find the exact matching account."""
        # Arrange
        mock_cache = mocker.patch("brandbox.providers.microsoft.msal.SerializableTokenCache")
        mock_cache.return_value.has_state_changed = True
        mock_cache.return_value.serialize.return_value = "{}"
        mock_app_cls = mocker.patch("brandbox.providers.microsoft.msal.PublicClientApplication")
        mock_app_cls.return_value.get_accounts.return_value = [
            {"username": "alice@co.com"},
            {"username": "bob@co.com"},
            {"username": "charlie@co.com"},
        ]
        mock_app_cls.return_value.acquire_token_silent.return_value = {
            "access_token": "tok",
        }
        provider = MicrosoftProvider("test-id", tmp_path / "token.json")

        # Act
        token = provider.get_token(Account(username="bob@co.com", provider_name="microsoft"))

        # Assert
        assert token == "tok"
        mock_app_cls.return_value.acquire_token_silent.assert_called_once_with(
            SCOPES, account={"username": "bob@co.com"}
        )
