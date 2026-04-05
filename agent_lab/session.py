"""Session and conversation history management."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class Session:
    """Manages a conversation session."""

    def __init__(self, session_id: str, workspace: Path) -> None:
        """Initialize session."""
        self.session_id = session_id
        self.workspace = workspace
        self.history_file = workspace / "sessions" / f"{session_id}.json"

    def load_history(self) -> list[dict[str, Any]]:
        """Load conversation history."""
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        return []

    def save_history(self, messages: list[dict[str, Any]]) -> None:
        """Save conversation history."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(messages, f, indent=2, ensure_ascii=False)

    def append_message(self, message: dict[str, Any]) -> None:
        """Append a message to history."""
        history = self.load_history()
        history.append(message)
        self.save_history(history)

    def clear_history(self) -> None:
        """Clear all history."""
        self.save_history([])
