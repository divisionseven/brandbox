"""
Google / Google Workspace provider.

Authentication: OAuth 2.0 via InstalledAppFlow (opens browser, local callback).
Contacts & photos: Google People API.
Scan-inbox: Google People API otherContacts endpoint (more efficient than Gmail scan).

Setup: user must create a Google Cloud project, enable the People API and Gmail API,
and download OAuth 2.0 Desktop credentials as a JSON file. See README for full steps.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from brandbox.providers.base import Account, Contact, Provider

SCOPES = [
    "https://www.googleapis.com/auth/contacts",
    "https://www.googleapis.com/auth/contacts.other.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]

PEOPLE_BASE = "https://people.googleapis.com/v1"
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleProvider(Provider):
    name = "google"

    def __init__(self, credentials_file: Path, token_dir: Path) -> None:
        """
        credentials_file: path to the OAuth 2.0 Desktop credentials JSON downloaded
                          from Google Cloud Console (set via BRANDBOX_GOOGLE_CREDENTIALS).
        token_dir:        directory where per-account token files are stored.
        """
        self._creds_file = credentials_file
        self._token_dir = token_dir
        self._token_dir.mkdir(parents=True, exist_ok=True)

    # Internal helpers

    def _token_path(self, username: str) -> Path:
        """One token file per account, named by a sanitised version of the email."""
        safe = username.replace("@", "_at_").replace(".", "_").replace("+", "_")
        return self._token_dir / f"google_{safe}.json"

    def _save_token(self, username: str, creds: Credentials) -> None:
        data = {"username": username, "credentials": json.loads(creds.to_json())}
        self._token_path(username).write_text(json.dumps(data, indent=2))

    def _load_creds(self, username: str) -> Credentials:
        data = json.loads(self._token_path(username).read_text())
        creds = Credentials.from_authorized_user_info(data["credentials"], SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            self._save_token(username, creds)
        return creds

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def _people_get_paged(
        self,
        token: str,
        url: str,
        items_key: str,
        params: dict | None = None,
    ) -> list[dict]:
        items: list[dict] = []
        page_token: str | None = None
        while True:
            p = {**(params or {}), "pageSize": 1000}
            if page_token:
                p["pageToken"] = page_token
            resp = requests.get(url, headers=self._headers(token), params=p, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            items.extend(data.get(items_key, []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return items

    @staticmethod
    def _parse_contact(person: dict) -> Contact:
        resource_name = person.get("resourceName", "")
        display_name = ""
        names = person.get("names", [])
        if names:
            display_name = names[0].get("displayName", "")

        emails = [
            e["value"].lower().strip() for e in person.get("emailAddresses", []) if "value" in e
        ]
        return Contact(id=resource_name, display_name=display_name, emails=emails)

    # Auth

    def start_auth(self) -> dict:
        if not self._creds_file.exists():
            raise FileNotFoundError(
                f"Google credentials file not found: {self._creds_file}\n"
                "See the README for how to create one in Google Cloud Console."
            )
        return {"type": "browser"}

    def finish_auth(self, flow: dict) -> str:  # noqa: ARG002
        """Opens a browser for OAuth consent and blocks until complete."""
        auth_flow = InstalledAppFlow.from_client_secrets_file(str(self._creds_file), SCOPES)
        creds = auth_flow.run_local_server(port=0, open_browser=True)
        assert isinstance(creds, Credentials), "Expected OAuth2 credentials from Google login flow"

        # Fetch the user's email from the userinfo endpoint
        resp = requests.get(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {creds.token}"},
            timeout=10,
        )
        resp.raise_for_status()
        username = resp.json().get("email", "unknown@google.com").lower()

        self._save_token(username, creds)
        return username

    # Account management

    def get_accounts(self) -> list[Account]:
        accounts = []
        for f in sorted(self._token_dir.glob("google_*.json")):
            try:
                data = json.loads(f.read_text())
                if username := data.get("username"):
                    accounts.append(Account(username=username, provider_name=self.name))
            except (json.JSONDecodeError, OSError):
                pass
        return accounts

    def get_token(self, account: Account) -> str:
        if not self._token_path(account.username).exists():
            raise RuntimeError(
                f"No token found for {account.username}. "
                "Re-run brandbox --add-account --provider google."
            )
        return self._load_creds(account.username).token

    # Contacts

    def get_contacts(self, token: str) -> list[Contact]:
        items = self._people_get_paged(
            token,
            url=f"{PEOPLE_BASE}/people/me/connections",
            items_key="connections",
            params={"personFields": "names,emailAddresses"},
        )
        return [self._parse_contact(p) for p in items if p.get("emailAddresses")]

    def get_recent_senders(self, token: str, limit: int) -> set[str]:  # noqa: ARG002
        """
        Uses the People API otherContacts endpoint — people you've interacted
        with via Gmail but haven't explicitly added to your contacts.
        More efficient than scanning individual Gmail messages.
        """
        items = self._people_get_paged(
            token,
            url=f"{PEOPLE_BASE}/otherContacts",
            items_key="otherContacts",
            params={"readMask": "names,emailAddresses"},
        )
        emails: set[str] = set()
        for person in items:
            for e in person.get("emailAddresses", []):
                if v := e.get("value"):
                    emails.add(v.lower().strip())
        return emails

    def create_contact(self, token: str, display_name: str, email: str) -> str | None:
        resp = requests.post(
            f"{PEOPLE_BASE}/people:createContact",
            headers={**self._headers(token), "Content-Type": "application/json"},
            json={
                "names": [{"displayName": display_name}],
                "emailAddresses": [{"value": email}],
            },
            timeout=20,
        )
        if resp.status_code in (200, 201):
            return resp.json().get("resourceName")
        return None

    def set_contact_photo(self, token: str, contact_id: str, png: bytes) -> bool:
        """
        contact_id here is the People API resourceName (e.g. "people/c12345").
        The photo must be base64-encoded in the request body.
        """
        resp = requests.post(
            f"{PEOPLE_BASE}/{contact_id}:updateContactPhoto",
            headers={**self._headers(token), "Content-Type": "application/json"},
            json={
                "photoBytes": base64.b64encode(png).decode("utf-8"),
                "personFields": "photos",
            },
            timeout=30,
        )
        return resp.status_code == 200
