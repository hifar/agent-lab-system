"""Anthropic-compatible LLM provider."""

import json
import uuid
from typing import Any

import httpx

from agent_lab.providers.base import LLMProvider, LLMResponse, ToolCall


class AnthropicCompatProvider(LLMProvider):
    """Provider for Anthropic Claude models."""

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "claude-3-5-sonnet-20241022",
    ) -> None:
        """Initialize Anthropic provider."""
        super().__init__(api_key, api_base, default_model)
        self.client = httpx.AsyncClient(
            base_url=api_base or "https://api.anthropic.com",
            headers={
                "x-api-key": api_key or "",
                "anthropic-version": "2023-06-01",
            },
            timeout=300.0,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Send a chat completion request to Anthropic."""
        model_name = model or self.default_model

        # Convert messages to Anthropic format
        system: str = ""
        anthropic_messages: list[dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content")

            if role == "system":
                system = content if isinstance(content, str) else str(content or "")
                continue

            if role == "user":
                anthropic_messages.append({"role": "user", "content": content or ""})
            elif role == "assistant":
                anthropic_messages.append({"role": "assistant", "content": content or ""})

        # Build request payload
        payload: dict[str, Any] = {
            "model": model_name,
            "messages": anthropic_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if system:
            payload["system"] = system

        # Convert tools to Anthropic format
        if tools:
            anthropic_tools = []
            for tool in tools:
                if "function" in tool:
                    func = tool["function"]
                else:
                    func = tool
                anthropic_tools.append({
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {"type": "object"}),
                })
            payload["tools"] = anthropic_tools
            if tool_choice == "required":
                payload["tool_choice"] = {"type": "any"}
            elif tool_choice:
                payload["tool_choice"] = {"type": "auto"}

        try:
            response = await self.client.post("/messages", json=payload)
            response.raise_for_status()
            data = response.json()

            # Parse response
            content = ""
            tool_calls: list[ToolCall] = []
            finish_reason = data.get("stop_reason", "stop")

            for block in data.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")
                elif block.get("type") == "tool_use":
                    tool_calls.append(
                        ToolCall(
                            id=block.get("id", str(uuid.uuid4())),
                            name=block.get("name", ""),
                            arguments=block.get("input", {}),
                        )
                    )

            usage = data.get("usage", {})

            return LLMResponse(
                content=content if content else None,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage={
                    "prompt_tokens": usage.get("input_tokens", 0),
                    "completion_tokens": usage.get("output_tokens", 0),
                },
            )

        except httpx.HTTPError as e:
            return LLMResponse(content=f"Error: {e}", finish_reason="error")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
