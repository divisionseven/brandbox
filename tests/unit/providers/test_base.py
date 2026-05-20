"""Tests for brandbox.providers.base — Contact, Account, and Provider ABC."""

from __future__ import annotations

import pytest

from brandbox.providers.base import Account, Contact, Provider


class TestContact:
    """Tests for the Contact dataclass."""

    def test_contact_creates_with_all_fields(self) -> None:
        """Contact can be created with all four fields."""
        # Arrange
        contact = Contact(
            id="abc-123",
            display_name="Alice Johnson",
            emails=["alice@company.com"],
        )

        # Assert
        assert contact.id == "abc-123"
        assert contact.display_name == "Alice Johnson"
        assert contact.emails == ["alice@company.com"]

    def test_contact_done_defaults_to_false(self) -> None:
        """Contact._done defaults to False when not provided."""
        # Arrange
        contact = Contact(
            id="abc-123",
            display_name="Alice Johnson",
            emails=["alice@company.com"],
        )

        # Assert
        assert contact._done is False

    def test_contact_done_excluded_from_repr(self) -> None:
        """Contact._done is excluded from __repr__ (repr=False)."""
        # Arrange
        contact = Contact(
            id="abc-123",
            display_name="Alice Johnson",
            emails=["alice@company.com"],
        )

        # Act
        r = repr(contact)

        # Assert
        assert "_done" not in r

    def test_contact_done_true_when_set(self) -> None:
        """Contact._done can be set to True."""
        # Arrange
        contact = Contact(
            id="abc-123",
            display_name="Alice Johnson",
            emails=["alice@company.com"],
            _done=True,
        )

        # Assert
        assert contact._done is True


class TestAccount:
    """Tests for the Account dataclass."""

    def test_account_creates_with_both_fields(self) -> None:
        """Account can be created with username and provider_name."""
        # Arrange
        account = Account(username="user@company.com", provider_name="microsoft")

        # Assert
        assert account.username == "user@company.com"
        assert account.provider_name == "microsoft"


class TestProvider:
    """Tests for the Provider ABC."""

    def test_provider_abc_cannot_be_instantiated(self) -> None:
        """Provider ABC raises TypeError because it has abstract methods."""
        # Act / Assert
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            Provider()  # type: ignore[abstract]

    def test_complete_subclass_can_be_instantiated(self) -> None:
        """A subclass that implements all abstract methods can be instantiated."""

        # Arrange
        class CompleteProvider(Provider):
            name = "complete"

            def start_auth(self) -> dict:
                return {"type": "browser"}

            def finish_auth(self, flow: dict) -> str:
                return "user@test.com"

            def get_accounts(self) -> list[Account]:
                return []

            def get_token(self, account: Account) -> str:
                return "token"

            def get_contacts(self, token: str) -> list[Contact]:
                return []

            def get_recent_senders(self, token: str, limit: int) -> set[str]:
                return set()

            def create_contact(self, token: str, display_name: str, email: str) -> str | None:
                return None

            def set_contact_photo(self, token: str, contact_id: str, png: bytes) -> bool:
                return True

        # Act
        instance = CompleteProvider()

        # Assert
        assert isinstance(instance, Provider)

    def test_incomplete_subclass_raises_type_error(self) -> None:
        """A subclass that doesn't implement all abstract methods raises TypeError."""

        # Arrange
        class IncompleteProvider(Provider):
            name = "incomplete"

            def start_auth(self) -> dict:
                return {"type": "browser"}

            # finish_auth is intentionally not implemented

            def get_accounts(self) -> list[Account]:
                return []

            def get_token(self, account: Account) -> str:
                return "token"

            def get_contacts(self, token: str) -> list[Contact]:
                return []

            def get_recent_senders(self, token: str, limit: int) -> set[str]:
                return set()

            def create_contact(self, token: str, display_name: str, email: str) -> str | None:
                return None

            def set_contact_photo(self, token: str, contact_id: str, png: bytes) -> bool:
                return True

        # Act / Assert
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteProvider()  # type: ignore[abstract]
