"""Knowledge base loader with progressive disclosure metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class KnowledgeEntry:
    """Metadata for a knowledge markdown entry."""

    file_name: str
    name: str
    description: str


class KnowledgeLoader:
    """Loads knowledge metadata and supports on-demand content loading."""

    def __init__(self, workspace_path: Path) -> None:
        self.workspace_path = workspace_path
        self.knowledge_dir = workspace_path / "knowledge"

    def list_entries(self) -> list[KnowledgeEntry]:
        """List knowledge entries by parsing markdown frontmatter only."""
        entries: list[KnowledgeEntry] = []
        if not self.knowledge_dir.exists():
            return entries

        for md_file in sorted(self.knowledge_dir.glob("*.md")):
            name, description = self._read_frontmatter(md_file)
            entries.append(
                KnowledgeEntry(
                    file_name=md_file.name,
                    name=name or md_file.stem,
                    description=description or "No description provided.",
                )
            )

        return entries

    def load_entry_content(self, entry_name: str) -> str | None:
        """Load full markdown content by file name or metadata name."""
        direct_file = self.knowledge_dir / entry_name
        if direct_file.exists() and direct_file.is_file():
            return direct_file.read_text(encoding="utf-8")

        # Try with .md suffix.
        if not entry_name.endswith(".md"):
            candidate = self.knowledge_dir / f"{entry_name}.md"
            if candidate.exists() and candidate.is_file():
                return candidate.read_text(encoding="utf-8")

        # Try matching by frontmatter name.
        for entry in self.list_entries():
            if entry.name == entry_name:
                target = self.knowledge_dir / entry.file_name
                if target.exists() and target.is_file():
                    return target.read_text(encoding="utf-8")

        return None

    def get_catalog_for_context(self, limit: int = 30) -> str:
        """Return knowledge catalog summary for system context without full content."""
        entries = self.list_entries()
        if not entries:
            return ""

        lines: list[str] = []
        for entry in entries[:limit]:
            lines.append(
                f"- {entry.name}: {entry.description} (file: knowledge/{entry.file_name})"
            )

        return "\n".join(lines)

    def _read_frontmatter(self, path: Path) -> tuple[str | None, str | None]:
        """Parse simple YAML frontmatter containing name and description."""
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None, None

        lines = text.splitlines()
        if len(lines) < 3 or lines[0].strip() != "---":
            return None, None

        end_index = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_index = i
                break

        if end_index is None:
            return None, None

        meta: dict[str, str] = {}
        for line in lines[1:end_index]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()

        name = meta.get("name")
        description = meta.get("description")
        return name, description


__all__ = ["KnowledgeEntry", "KnowledgeLoader"]
