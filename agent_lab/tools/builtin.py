"""Built-in file operation tools."""

from pathlib import Path
from typing import Any

from agent_lab.tools.base import Tool


class ReadFileTool(Tool):
    """Read file contents."""

    def __init__(self, workspace: Path | None = None) -> None:
        """Initialize read file tool."""
        self.workspace = workspace or Path.cwd()

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the contents of a file."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read (relative to workspace)",
                }
            },
            "required": ["path"],
        }

    async def execute(self, path: str) -> str:
        """Execute read file."""
        try:
            file_path = self.workspace / path
            if not file_path.exists():
                return f"Error: File not found: {path}"
            if not file_path.is_file():
                return f"Error: Path is not a file: {path}"
            return file_path.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading file: {str(e)}"


class WriteFileTool(Tool):
    """Write content to a file."""

    def __init__(self, workspace: Path | None = None) -> None:
        """Initialize write file tool."""
        self.workspace = workspace or Path.cwd()

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to write (relative to workspace)",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["path", "content"],
        }

    async def execute(self, path: str, content: str) -> str:
        """Execute write file."""
        try:
            file_path = self.workspace / path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return f"File written: {path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"


class ListDirTool(Tool):
    """List directory contents."""

    def __init__(self, workspace: Path | None = None) -> None:
        """Initialize list dir tool."""
        self.workspace = workspace or Path.cwd()

    @property
    def name(self) -> str:
        return "list_dir"

    @property
    def description(self) -> str:
        return "List contents of a directory."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the directory (relative to workspace, default: '.')",
                }
            },
            "required": [],
        }

    async def execute(self, path: str = ".") -> str:
        """Execute list dir."""
        try:
            dir_path = self.workspace / path if path != "." else self.workspace
            if not dir_path.exists():
                return f"Error: Directory not found: {path}"
            if not dir_path.is_dir():
                return f"Error: Path is not a directory: {path}"

            items = []
            for item in sorted(dir_path.iterdir()):
                prefix = "[DIR]  " if item.is_dir() else "[FILE] "
                items.append(f"{prefix}{item.name}")

            return "\n".join(items) if items else "(empty directory)"
        except Exception as e:
            return f"Error listing directory: {str(e)}"
