"""Tests for brandbox.state — JSON state file load/save."""

from __future__ import annotations

import json
from pathlib import Path

from brandbox.state import load, save


class TestLoad:
    """Tests for the load() function."""

    def test_load_nonexistent_file_returns_empty_dict(self, state_file: Path) -> None:
        """Loading a non-existent file returns an empty dict."""
        # Arrange
        assert not state_file.exists()

        # Act
        result = load(state_file)

        # Assert
        assert result == {}

    def test_load_valid_json_returns_parsed_dict(self, state_file: Path) -> None:
        """Loading a valid JSON file returns the parsed dict."""
        # Arrange
        data = {"user@example.com": {"contact-1": "stripe.com"}}
        state_file.write_text(json.dumps(data))

        # Act
        result = load(state_file)

        # Assert
        assert result == data

    def test_load_invalid_json_returns_empty_dict(self, state_file: Path) -> None:
        """Loading malformed JSON that can't be parsed returns an empty dict."""
        # Arrange
        state_file.write_text("this is not json")

        # Act
        result = load(state_file)

        # Assert
        assert result == {}

    def test_load_empty_file_returns_empty_dict(self, state_file: Path) -> None:
        """Loading an empty file returns an empty dict (json.loads('') raises)."""
        # Arrange
        state_file.write_text("")

        # Act
        result = load(state_file)

        # Assert
        assert result == {}

    def test_load_json_null_returns_none(self, state_file: Path) -> None:
        """Loading a file containing JSON 'null' returns None.

        The current code does not validate that the result is a dict —
        json.loads('null') produces None, and load() passes it through.
        """
        # Arrange
        state_file.write_text("null")

        # Act
        result = load(state_file)

        # Assert
        assert result is None


class TestSave:
    """Tests for the save() function."""

    def test_save_writes_correct_json(self, state_file: Path) -> None:
        """Save writes correctly formatted JSON that round-trips via json.load."""
        # Arrange
        state = {"user@example.com": {"contact-1": "stripe.com"}}

        # Act
        save(state_file, state)

        # Assert
        assert state_file.exists()
        assert json.loads(state_file.read_text()) == state

    def test_save_creates_parent_directories(self, tmp_path: Path) -> None:
        """Save creates parent directories when they don't exist."""
        # Arrange
        nested = tmp_path / "a" / "b" / "c" / "state.json"

        # Act
        save(nested, {"key": "value"})

        # Assert
        assert nested.exists()
        assert json.loads(nested.read_text()) == {"key": "value"}

    def test_save_empty_dict_writes_empty_object(self, state_file: Path) -> None:
        """Save with an empty dict writes exactly '{}' to the file."""
        # Arrange

        # Act
        save(state_file, {})

        # Assert
        assert state_file.read_text().strip() == "{}"
