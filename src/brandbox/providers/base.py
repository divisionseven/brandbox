"""
Abstract base class and shared data models for brandbox email providers.

Each provider implements the same interface so the CLI can work with
Microsoft 365, Google, or any future provider identically.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Contact:
    """A normalised contact record, independent of provider."""

    id: str  # provider-native ID (Graph GUID or People resourceName)
    display_name: str
    emails: list[str]
    _done: bool = field(default=False, repr=False)  # internal: skip re-processing flag


@dataclass
class Account:
    """A user account registered with a provider."""

    username: str  # email address
    provider_name: str  # "microsoft" | "google"


class Provider(ABC):
    """
    Interface every email provider must implement.

    Auth is split into two steps so the CLI can display provider-specific
    instructions (device code URL+code for Microsoft, browser prompt for Google)
    between initiating and completing the flow.
    """

    name: str  # set as a class attribute in each subclass

    # Auth

    @abstractmethod
    def start_auth(self) -> dict:
        """
        Begin the authentication flow.

        Returns a dict with at minimum a "type" key:
          {"type": "device_code", "url": "...", "code": "..."}   # Microsoft
          {"type": "browser"}                                     # Google
        Any provider-internal flow state needed by finish_auth is also included.
        """

    @abstractmethod
    def finish_auth(self, flow: dict) -> str:
        """
        Complete the auth flow (may block waiting for user). Returns the username."""

    # Account management

    @abstractmethod
    def get_accounts(self) -> list[Account]:
        """Return all accounts authenticated with this provider."""

    @abstractmethod
    def get_token(self, account: Account) -> str:
        """Return a valid (refreshed if necessary) access token for the account."""

    # Data operations

    @abstractmethod
    def get_contacts(self, token: str) -> list[Contact]:
        """Return all personal contacts for the authenticated user."""

    @abstractmethod
    def get_recent_senders(self, token: str, limit: int) -> set[str]:
        """
        Return email addresses of people who've sent the user mail but aren't
        yet in their contacts. Used to populate contacts via --scan-inbox.
        """

    @abstractmethod
    def create_contact(self, token: str, display_name: str, email: str) -> str | None:
        """Create a new contact. Returns the provider-native contact ID, or None."""

    @abstractmethod
    def set_contact_photo(self, token: str, contact_id: str, png: bytes) -> bool:
        """Upload PNG bytes as the contact's profile photo. Returns True on success."""
