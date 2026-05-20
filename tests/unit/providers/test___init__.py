"""Tests for brandbox.providers — build_providers() and get_provider()."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from brandbox.providers import PROVIDER_NAMES, build_providers, get_provider


class TestBuildProviders:
    """Tests for the build_providers() function."""

    def test_both_providers_enabled_returns_dict_with_both(
        self, token_dir: Path, mocker: MockerFixture
    ) -> None:
        """When both ms_client_id and google_creds are set, both providers are built."""
        # Arrange
        mock_ms = mocker.patch("brandbox.providers.MicrosoftProvider")
        mock_google = mocker.patch("brandbox.providers.GoogleProvider")
        google_creds = token_dir / "credentials.json"
        google_creds.write_text('{"dummy": true}')
        ms_client_id = "my-client-id"

        # Act
        result = build_providers(ms_client_id, google_creds, token_dir)

        # Assert
        assert "microsoft" in result
        assert "google" in result
        mock_ms.assert_called_once_with(
            client_id=ms_client_id,
            token_file=token_dir / "microsoft.json",
        )
        mock_google.assert_called_once_with(
            credentials_file=google_creds,
            token_dir=token_dir,
        )

    def test_only_ms_client_id_returns_only_microsoft(
        self, token_dir: Path, mocker: MockerFixture
    ) -> None:
        """When only ms_client_id is set, only the Microsoft provider is built."""
        # Arrange
        mocker.patch("brandbox.providers.MicrosoftProvider")
        mocker.patch("brandbox.providers.GoogleProvider")
        google_creds = token_dir / "credentials.json"  # does not exist

        # Act
        result = build_providers("my-client-id", google_creds, token_dir)

        # Assert
        assert "microsoft" in result
        assert "google" not in result

    def test_only_google_creds_returns_only_google(
        self, token_dir: Path, mocker: MockerFixture
    ) -> None:
        """When only google_creds is set, only the Google provider is built."""
        # Arrange
        mocker.patch("brandbox.providers.MicrosoftProvider")
        mocker.patch("brandbox.providers.GoogleProvider")
        google_creds = token_dir / "credentials.json"
        google_creds.write_text('{"dummy": true}')

        # Act
        result = build_providers("", google_creds, token_dir)

        # Assert
        assert "microsoft" not in result
        assert "google" in result

    def test_neither_provider_returns_empty_dict(
        self, token_dir: Path, mocker: MockerFixture
    ) -> None:
        """When neither ms_client_id nor google_creds is set, returns empty dict."""
        # Arrange
        mocker.patch("brandbox.providers.MicrosoftProvider")
        mocker.patch("brandbox.providers.GoogleProvider")
        google_creds = token_dir / "credentials.json"  # does not exist

        # Act
        result = build_providers("", google_creds, token_dir)

        # Assert
        assert result == {}

    def test_empty_ms_client_id_omits_microsoft(
        self, token_dir: Path, mocker: MockerFixture
    ) -> None:
        """An empty string ms_client_id causes Microsoft to be omitted (falsy check)."""
        # Arrange
        mocker.patch("brandbox.providers.MicrosoftProvider")
        mocker.patch("brandbox.providers.GoogleProvider")
        google_creds = token_dir / "credentials.json"  # does not exist

        # Act
        result = build_providers("", google_creds, token_dir)

        # Assert
        assert "microsoft" not in result


class TestGetProvider:
    """Tests for the get_provider() function."""

    def test_get_microsoft_with_valid_client_id_returns_provider(
        self, token_dir: Path, mocker: MockerFixture
    ) -> None:
        """get_provider('microsoft') with a valid client_id returns a MicrosoftProvider."""
        # Arrange
        mock_ms = mocker.patch("brandbox.providers.MicrosoftProvider")
        google_creds = token_dir / "credentials.json"

        # Act
        result = get_provider("microsoft", "my-client-id", google_creds, token_dir)

        # Assert
        assert result is not None
        mock_ms.assert_called_once_with(
            client_id="my-client-id",
            token_file=token_dir / "microsoft.json",
        )

    def test_get_microsoft_with_empty_client_id_raises_runtime_error(
        self, token_dir: Path, mocker: MockerFixture
    ) -> None:
        """get_provider('microsoft') with an empty client_id raises RuntimeError."""
        # Arrange
        mocker.patch("brandbox.providers.MicrosoftProvider")
        google_creds = token_dir / "credentials.json"

        # Act / Assert
        with pytest.raises(RuntimeError, match="BRANDBOX_CLIENT_ID is not set"):
            get_provider("microsoft", "", google_creds, token_dir)

    def test_get_google_with_existing_creds_returns_provider(
        self, token_dir: Path, mocker: MockerFixture
    ) -> None:
        """get_provider('google') with existing creds file returns a GoogleProvider."""
        # Arrange
        mocker.patch("brandbox.providers.MicrosoftProvider")
        mock_google = mocker.patch("brandbox.providers.GoogleProvider")
        google_creds = token_dir / "credentials.json"
        google_creds.write_text('{"dummy": true}')

        # Act
        result = get_provider("google", "", google_creds, token_dir)

        # Assert
        assert result is not None
        mock_google.assert_called_once_with(
            credentials_file=google_creds,
            token_dir=token_dir,
        )

    def test_get_google_with_missing_creds_raises_runtime_error(
        self, token_dir: Path, mocker: MockerFixture
    ) -> None:
        """get_provider('google') with non-existent creds file raises RuntimeError."""
        # Arrange
        mocker.patch("brandbox.providers.MicrosoftProvider")
        mocker.patch("brandbox.providers.GoogleProvider")
        google_creds = token_dir / "credentials.json"  # does not exist

        # Act / Assert
        with pytest.raises(RuntimeError, match="credentials file not found"):
            get_provider("google", "", google_creds, token_dir)

    def test_get_unknown_provider_raises_value_error(
        self, token_dir: Path, mocker: MockerFixture
    ) -> None:
        """get_provider('unknown') raises ValueError with the provider name."""
        # Arrange
        mocker.patch("brandbox.providers.MicrosoftProvider")
        mocker.patch("brandbox.providers.GoogleProvider")
        google_creds = token_dir / "credentials.json"

        # Act / Assert
        with pytest.raises(ValueError, match="Unknown provider 'unknown'"):
            get_provider("unknown", "", google_creds, token_dir)


class TestProviderNames:
    """Tests for the PROVIDER_NAMES constant."""

    def test_provider_names_contains_expected_values(self) -> None:
        """PROVIDER_NAMES lists the built-in providers."""
        # Assert
        assert PROVIDER_NAMES == ["microsoft", "google"]
