"""
brandbox provider system.

Providers abstract all email-platform-specific logic (auth, contacts, photos)
behind a common interface so the CLI and logo pipeline are fully provider-agnostic.
"""

from __future__ import annotations

from pathlib import Path

from brandbox.providers.base import Account, Contact, Provider
from brandbox.providers.google import GoogleProvider
from brandbox.providers.microsoft import MicrosoftProvider

__all__ = [
    "Account",
    "Contact",
    "Provider",
    "MicrosoftProvider",
    "GoogleProvider",
    "build_providers",
    "get_provider",
    "PROVIDER_NAMES",
]

PROVIDER_NAMES = ["microsoft", "google"]


def build_providers(
    ms_client_id: str,
    google_creds: Path,
    token_dir: Path,
) -> dict[str, Provider]:
    """
    Return a dict of {provider_name: Provider} for every provider that has
    sufficient configuration to operate. Providers with missing config are
    silently omitted so users who only use one provider aren't affected.
    """
    providers: dict[str, Provider] = {}

    if ms_client_id:
        providers["microsoft"] = MicrosoftProvider(
            client_id=ms_client_id,
            token_file=token_dir / "microsoft.json",
        )

    if google_creds.exists():
        providers["google"] = GoogleProvider(
            credentials_file=google_creds,
            token_dir=token_dir,
        )

    return providers


def get_provider(
    name: str,
    ms_client_id: str,
    google_creds: Path,
    token_dir: Path,
) -> Provider:
    """Instantiate a single named provider. Raises if config is missing."""
    if name == "microsoft":
        if not ms_client_id:
            raise RuntimeError(
                "BRANDBOX_CLIENT_ID is not set. See brandbox --help for setup instructions."
            )
        return MicrosoftProvider(
            client_id=ms_client_id,
            token_file=token_dir / "microsoft.json",
        )

    if name == "google":
        if not google_creds.exists():
            raise RuntimeError(
                f"Google credentials file not found at {google_creds}.\n"
                "Set BRANDBOX_GOOGLE_CREDENTIALS to its path. "
                "See brandbox --help for setup instructions."
            )
        return GoogleProvider(
            credentials_file=google_creds,
            token_dir=token_dir,
        )

    raise ValueError(f"Unknown provider '{name}'. Choose from: {', '.join(PROVIDER_NAMES)}")
