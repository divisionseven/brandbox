"""
Lightweight JSON state file that tracks which contact IDs have already
received a logo, keyed by account username.

Structure: { "user@example.com": { "contact-id-xyz": "stripe.com" } }

This avoids re-processing contacts on every run, and avoids overwriting
manually-set photos unless --overwrite is passed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast


def load(state_file: Path) -> dict[str, Any]:
    if state_file.exists():
        try:
            return cast(dict[str, Any], json.loads(state_file.read_text()))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save(state_file: Path, state: dict[str, Any]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2))
