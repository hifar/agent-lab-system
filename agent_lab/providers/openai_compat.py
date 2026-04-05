"""OpenAI-compatible LLM provider."""

import json
from typing import Any

import httpx

from agent_lab.providers.base import LLMProvider, LLMResponse, ToolCall


class OpenAICompatProvider(LLMProvider):
    """Provider for OpenAI-compatible APIs."""

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "gpt-4o",
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize OpenAI-compatible provider."""
        super().__init__(api_key, api_base, default_model)
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if extra_headers:
            headers.update(extra_headers)

        self.client = httpx.AsyncClient(
            base_url=api_base or "https://api.openai.com/v1",
            headers=headers,
            timeout=300.0,
        )

    @staticmethod
    def _normalize_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize tool definitions to OpenAI-compatible format."""
        normalized: list[dict[str, Any]] = []
        for tool in tools:
            # Already OpenAI shape: {"type": "function", "function": {...}}
            if isinstance(tool.get("function"), dict):
                normalized.append({
                    "type": tool.get("type", "function"),
                    "function": tool["function"],
                })
                continue

            # Bare function schema shape: {"name": ..., "description": ..., "parameters": ...}
            normalized.append({"type": "function", "function": tool})
        return normalized

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Send a chat completion request to OpenAI-compatible endpoint."""
        model_name = model or self.default_model

        # Build request payload
        payload: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max(1, max_tokens),
        }

        if tools:
            payload["tools"] = self._normalize_tools(tools)
            if tool_choice != "none":
                payload["tool_choice"] = tool_choice or "auto"

        try:
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

            # Parse response
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content")
            finish_reason = choice.get("finish_reason", "stop")

            tool_calls: list[ToolCall] = []
            if "tool_calls" in message:
                for tc in message["tool_calls"]:
                    if tc.get("type") == "function":
                        func = tc.get("function", {})
                        args = func.get("arguments", "{}")
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                args = {}
                        tool_calls.append(
                            ToolCall(
                                id=tc.get("id", ""),
                                name=func.get("name", ""),
                                arguments=args,
                            )
                        )

            usage = data.get("usage", {})

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                },
            )

        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.text
            except Exception:
                detail = ""
            status = e.response.status_code if e.response is not None else "unknown"
            message = f"Error: HTTP {status} calling {e.request.url if e.request else '/chat/completions'}"
            if detail:
                message += f" | response: {detail}"
            return LLMResponse(content=message, finish_reason="error")
        except httpx.HTTPError as e:
            return LLMResponse(content=f"Error: {e}", finish_reason="error")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
