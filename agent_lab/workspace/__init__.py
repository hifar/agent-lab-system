"""Workspace management."""

from pathlib import Path


class Workspace:
    """Manages agent workspace."""

    SUBDIRS = ["skills", "memories", "sessions"]

    def __init__(self, path: Path) -> None:
        """Initialize workspace."""
        self.path = path.expanduser().resolve()

    def initialize(self) -> None:
        """Initialize workspace directory structure."""
        self.path.mkdir(parents=True, exist_ok=True)
        for subdir in self.SUBDIRS:
            (self.path / subdir).mkdir(exist_ok=True)

    @property
    def skills_dir(self) -> Path:
        """Get skills directory."""
        return self.path / "skills"

    @property
    def memories_dir(self) -> Path:
        """Get memories directory."""
        return self.path / "memories"

    @property
    def sessions_dir(self) -> Path:
        """Get sessions directory."""
        return self.path / "sessions"

    def __str__(self) -> str:
        return str(self.path)
