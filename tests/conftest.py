"""Shared test fixtures for the brandbox test suite."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from brandbox.providers.base import Account, Contact, Provider


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    """A temporary cache directory."""
    d = tmp_path / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def token_dir(tmp_path: Path) -> Path:
    """A temporary token directory."""
    d = tmp_path / "tokens"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def state_file(tmp_path: Path) -> Path:
    """A path to a non-existent state file in a temp dir."""
    return tmp_path / "state.json"


@pytest.fixture
def sample_contacts() -> list[Contact]:
    """Sample contacts for testing."""
    return [
        Contact(id="c1", display_name="Alice Johnson", emails=["alice@company.com"]),
        Contact(id="c2", display_name="Bob Smith", emails=["bob@acmecorp.org"]),
        Contact(id="c3", display_name="Charlie Davis", emails=["charlie@gmail.com"]),
        Contact(id="c4", display_name="Diana Lee", emails=["diana@startup.io"]),
        Contact(id="c5", display_name="Eve Williams", emails=["eve@example.net"]),
        Contact(id="c6", display_name="Frank Brown", emails=["frank@mega-corp.co.uk"]),
    ]


@pytest.fixture
def sample_account() -> Account:
    """A sample Microsoft account."""
    return Account(username="user@company.com", provider_name="microsoft")


@pytest.fixture
def sample_accounts() -> list[Account]:
    """Sample accounts for multiple providers."""
    return [
        Account(username="user@company.com", provider_name="microsoft"),
        Account(username="user@gmail.com", provider_name="google"),
    ]


class MockProvider(Provider):
    """A fully mock provider for testing CLI orchestration."""

    name = "mock"

    def __init__(self) -> None:
        self.accounts: list[Account] = []
        self.tokens: dict[str, str] = {}
        self.contacts: list[Contact] = []
        self.senders: set[str] = set()
        self.auth_result: dict[str, Any] = {"type": "browser"}
        self.next_username: str = "mock@test.com"
        self.fail_auth: bool = False
        self.fail_token: bool = False
        self.fail_contacts: bool = False
        self.fail_create_contact: bool = False
        self.fail_set_photo: bool = False

    def start_auth(self) -> dict[str, Any]:
        if self.fail_auth:
            raise RuntimeError("Auth failed")
        return self.auth_result

    def finish_auth(self, flow: dict[str, Any]) -> str:
        if self.fail_auth:
            raise RuntimeError("Finish auth failed")
        return self.next_username

    def get_accounts(self) -> list[Account]:
        return self.accounts

    def get_token(self, account: Account) -> str:
        if self.fail_token:
            raise RuntimeError("Token acquisition failed")
        return self.tokens.get(account.username, "mock-token")

    def get_contacts(self, token: str) -> list[Contact]:
        if self.fail_contacts:
            raise RuntimeError("Failed to fetch contacts")
        return self.contacts

    def get_recent_senders(self, token: str, limit: int) -> set[str]:
        return self.senders

    def create_contact(self, token: str, display_name: str, email: str) -> str | None:
        if self.fail_create_contact:
            return None
        cid = f"new-{hash(email)}"
        self.contacts.append(Contact(id=cid, display_name=display_name, emails=[email]))
        return cid

    def set_contact_photo(self, token: str, contact_id: str, png: bytes) -> bool:
        return not self.fail_set_photo


@pytest.fixture
def mock_provider() -> MockProvider:
    """A MockProvider instance with no contacts or accounts configured."""
    return MockProvider()
