"""Agent main loop and execution logic."""

import json
from pathlib import Path
from typing import Any

from agent_lab.providers.base import LLMProvider
from agent_lab.tools.registry import ToolRegistry


class Agent:
    """Main agent loop for processing messages and tool calls."""

    def __init__(
        self,
        provider: LLMProvider,
        tools: ToolRegistry,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 20,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: str | None = None,
    ) -> None:
        """Initialize agent."""
        self.provider = provider
        self.tools = tools
        self.workspace = workspace
        self.model = model or provider.default_model
        self.max_iterations = max_iterations
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._system_prompt = system_prompt

    def _build_system_prompt(self) -> str:
        """Build system prompt for the agent."""
        if self._system_prompt:
            return self._system_prompt

        tool_names = self.tools.tool_names
        tool_list = "\n".join(f"- {name}" for name in tool_names)

        return f"""You are an AI agent with access to tools.

Available tools:
{tool_list}

When you need to use a tool, call it with the appropriate parameters.
Think step-by-step before taking action.
Be concise and direct in your responses."""

    async def run(
        self,
        message: str,
        history: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Run the agent on a message.

        Args:
            message: User message
            history: Previous conversation history
            max_tokens: Optional max tokens override
            temperature: Optional temperature override
            tool_choice: Optional tool choice override

        Returns:
            (final_response, updated_messages)
        """
        messages = list(history) if history else []

        # Add system prompt if not present
        if not messages or messages[0].get("role") != "system":
            messages.insert(0, {
                "role": "system",
                "content": self._build_system_prompt(),
            })

        # Add user message
        messages.append({"role": "user", "content": message})

        # Agentic loop
        for iteration in range(self.max_iterations):
            # Call LLM
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions() if self.tools.tool_names else None,
                model=self.model,
                max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
                temperature=temperature if temperature is not None else self.temperature,
                tool_choice=tool_choice,
            )

            # Add assistant response to messages
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": response.content,
            }
            if response.has_tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                        },
                    }
                    for tc in response.tool_calls
                ]
            messages.append(assistant_msg)

            # Check for tool calls
            if not response.has_tool_calls:
                # No tool calls, return final response
                return response.content or "", messages

            # Execute tool calls
            for tool_call in response.tool_calls:
                result = await self.tools.execute(tool_call.name, tool_call.arguments)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.name,
                    "content": str(result),
                })

        # Max iterations reached
        return "Max iterations reached without final response.", messages
