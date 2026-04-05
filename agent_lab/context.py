"""Agent context builder for assembling prompts."""

from pathlib import Path
from typing import Any


class ContextBuilder:
    """Builds context for agent prompts."""

    def __init__(self, workspace: Path) -> None:
        """Initialize context builder."""
        self.workspace = workspace

    def build_system_prompt(self, tool_names: list[str] | None = None) -> str:
        """Build system prompt."""
        tool_list = ""
        if tool_names:
            tool_list = "\n".join(f"- {name}" for name in tool_names)

        return f"""You are a helpful AI assistant with the ability to use tools.

Your workspace directory: {self.workspace}

Available tools:
{tool_list}

Instructions:
1. Use tools when needed to accomplish tasks
2. Be concise and direct in responses
3. Ask for clarification if needed
4. Provide clear explanations of your actions"""

    @staticmethod
    def build_user_message(text: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """Build a user message."""
        return {"role": "user", "content": text}

    @staticmethod
    def build_assistant_message(
        content: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build an assistant message."""
        msg: dict[str, Any] = {"role": "assistant", "content": content or ""}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        return msg

    @staticmethod
    def build_tool_message(
        tool_call_id: str,
        tool_name: str,
        content: str,
    ) -> dict[str, Any]:
        """Build a tool result message."""
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": content,
        }
