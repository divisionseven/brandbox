"""
Microsoft 365 provider.

Authentication: MSAL device code flow (multi-account, single token cache file).
Contacts & photos: Microsoft Graph API.
"""

from __future__ import annotations

from pathlib import Path

import msal
import requests

from brandbox.providers.base import Account, Contact, Provider

AUTHORITY = "https://login.microsoftonline.com/common"
SCOPES = ["Contacts.ReadWrite", "Mail.Read"]
GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class MicrosoftProvider(Provider):
    name = "microsoft"

    def __init__(self, client_id: str, token_file: Path) -> None:
        self._client_id = client_id
        self._token_file = token_file
        self._cache = self._load_cache()

    # Internal helpers

    def _load_cache(self) -> msal.SerializableTokenCache:
        cache = msal.SerializableTokenCache()
        if self._token_file.exists():
            cache.deserialize(self._token_file.read_text())
        return cache

    def _save_cache(self) -> None:
        if self._cache.has_state_changed:
            self._token_file.parent.mkdir(parents=True, exist_ok=True)
            self._token_file.write_text(self._cache.serialize())

    def _app(self) -> msal.PublicClientApplication:
        return msal.PublicClientApplication(
            self._client_id,
            authority=AUTHORITY,
            token_cache=self._cache,
        )

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def _get_paged(self, token: str, url: str) -> list[dict]:
        items: list[dict] = []
        while url:
            resp = requests.get(url, headers=self._headers(token), timeout=30)
            resp.raise_for_status()
            data = resp.json()
            items.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
        return items

    # Auth

    def start_auth(self) -> dict:
        flow = self._app().initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(f"Device flow failed: {flow}")

        # Parse the human-readable MSAL message to extract URL and code
        msg = flow.get("message", "")
        url_start = msg.find("https://")
        url_end = msg.find(" ", url_start) if url_start != -1 else -1
        code_marker = "enter the code "
        code_start = msg.find(code_marker)
        code_end = msg.find(" to authenticate") if code_start != -1 else -1

        return {
            "type": "device_code",
            "url": msg[url_start:url_end]
            if url_start != -1 and url_end != -1
            else "https://microsoft.com/devicelogin",
            "code": msg[code_start + len(code_marker) : code_end]
            if code_start != -1 and code_end != -1
            else "",
            "_flow": flow,  # MSAL flow state — passed back into finish_auth
        }

    def finish_auth(self, flow: dict) -> str:
        result = self._app().acquire_token_by_device_flow(flow["_flow"])
        if "access_token" not in result:
            raise RuntimeError(f"Authentication failed: {result.get('error_description', result)}")
        self._save_cache()
        accounts = self._app().get_accounts()
        return (
            accounts[-1]["username"]
            if accounts
            else result.get("id_token_claims", {}).get("preferred_username", "unknown")
        )

    # Account management

    def get_accounts(self) -> list[Account]:
        return [
            Account(username=a["username"], provider_name=self.name)
            for a in self._app().get_accounts()
        ]

    def get_token(self, account: Account) -> str:
        msal_accounts = self._app().get_accounts()
        msal_account = next((a for a in msal_accounts if a["username"] == account.username), None)
        if not msal_account:
            raise RuntimeError(
                f"Account {account.username} not found in token cache. "
                "Re-run brandbox --add-account to re-authenticate."
            )
        result = self._app().acquire_token_silent(SCOPES, account=msal_account)
        if not result or "access_token" not in result:
            raise RuntimeError(
                f"Could not refresh token for {account.username}. "
                "Re-run brandbox --add-account to re-authenticate."
            )
        self._save_cache()
        return result["access_token"]

    # Contacts

    def get_contacts(self, token: str) -> list[Contact]:
        url = f"{GRAPH_BASE}/me/contacts?$select=id,displayName,emailAddresses&$top=999"
        items = self._get_paged(token, url)
        return [
            Contact(
                id=c["id"],
                display_name=c.get("displayName", ""),
                emails=[e["address"] for e in c.get("emailAddresses", []) if "address" in e],
            )
            for c in items
        ]

    def get_recent_senders(self, token: str, limit: int) -> set[str]:
        url = (
            f"{GRAPH_BASE}/me/mailFolders/inbox/messages"
            f"?$select=from&$top={min(limit, 999)}"
            "&$orderby=receivedDateTime desc"
        )
        items = self._get_paged(token, url)
        emails: set[str] = set()
        for msg in items:
            try:
                emails.add(msg["from"]["emailAddress"]["address"].lower().strip())
            except (KeyError, TypeError):
                pass
        return emails

    def create_contact(self, token: str, display_name: str, email: str) -> str | None:
        resp = requests.post(
            f"{GRAPH_BASE}/me/contacts",
            headers={**self._headers(token), "Content-Type": "application/json"},
            json={
                "displayName": display_name,
                "emailAddresses": [{"address": email, "name": display_name}],
            },
            timeout=20,
        )
        if resp.status_code in (200, 201):
            return resp.json().get("id")
        return None

    def set_contact_photo(self, token: str, contact_id: str, png: bytes) -> bool:
        resp = requests.put(
            f"{GRAPH_BASE}/me/contacts/{contact_id}/photo/$value",
            headers={**self._headers(token), "Content-Type": "image/png"},
            data=png,
            timeout=30,
        )
        return resp.status_code in (200, 204)
