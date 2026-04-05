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
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize Anthropic provider."""
        super().__init__(api_key, api_base, default_model)
        headers = {
            "x-api-key": api_key or "",
            "anthropic-version": "2023-06-01",
        }
        if extra_headers:
            headers.update(extra_headers)

        self.client = httpx.AsyncClient(
            base_url=api_base or "https://api.anthropic.com",
            headers=headers,
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
        enable_think_mode: bool = False,
        enable_streaming_mode: bool = False,
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
                blocks: list[dict[str, Any]] = []
                if isinstance(content, str) and content:
                    blocks.append({"type": "text", "text": content})
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            blocks.append(item)
                        else:
                            blocks.append({"type": "text", "text": str(item)})

                for tc in msg.get("tool_calls", []) or []:
                    if not isinstance(tc, dict):
                        continue
                    func = tc.get("function", {})
                    args = func.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}

                    blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", str(uuid.uuid4())),
                        "name": func.get("name", ""),
                        "input": args if isinstance(args, dict) else {},
                    })

                anthropic_messages.append({
                    "role": "assistant",
                    "content": blocks or [{"type": "text", "text": ""}],
                })
            elif role == "tool":
                tool_result = {
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id", ""),
                    "content": content if isinstance(content, (str, list)) else str(content or ""),
                }
                if anthropic_messages and anthropic_messages[-1].get("role") == "user":
                    prev_content = anthropic_messages[-1].get("content")
                    if isinstance(prev_content, list):
                        prev_content.append(tool_result)
                        anthropic_messages[-1]["content"] = prev_content
                    else:
                        anthropic_messages[-1]["content"] = [
                            {"type": "text", "text": str(prev_content or "")},
                            tool_result,
                        ]
                else:
                    anthropic_messages.append({"role": "user", "content": [tool_result]})

        # Anthropic expects alternating roles; merge consecutive same-role messages.
        merged_messages: list[dict[str, Any]] = []
        for msg in anthropic_messages:
            if merged_messages and merged_messages[-1].get("role") == msg.get("role"):
                prev = merged_messages[-1].get("content")
                cur = msg.get("content")

                if isinstance(prev, str):
                    prev_blocks: list[dict[str, Any]] = [{"type": "text", "text": prev}]
                else:
                    prev_blocks = list(prev or [])

                if isinstance(cur, str):
                    cur_blocks: list[dict[str, Any]] = [{"type": "text", "text": cur}]
                else:
                    cur_blocks = list(cur or [])

                prev_blocks.extend(cur_blocks)
                merged_messages[-1]["content"] = prev_blocks
            else:
                merged_messages.append(msg)

        # Build request payload
        payload: dict[str, Any] = {
            "model": model_name,
            "messages": merged_messages,
            "temperature": temperature,
            "max_tokens": max(1, max_tokens),
        }

        # Keep response handling non-streaming for now.
        if enable_streaming_mode:
            payload["stream"] = False

        if enable_think_mode:
            budget = min(max(1024, max_tokens // 2), 8192)
            payload["thinking"] = {
                "type": "enabled",
                "budget_tokens": budget,
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

        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.text
            except Exception:
                detail = ""
            status = e.response.status_code if e.response is not None else "unknown"
            message = f"Error: HTTP {status} calling {e.request.url if e.request else '/messages'}"
            if detail:
                message += f" | response: {detail}"
            return LLMResponse(content=message, finish_reason="error")
        except httpx.HTTPError as e:
            return LLMResponse(content=f"Error: {e}", finish_reason="error")

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tool_choice: str | dict[str, Any] | None = None,
        enable_think_mode: bool = False,
        enable_streaming_mode: bool = True,
        on_content_delta: Any | None = None,
    ) -> LLMResponse:
        """Stream Anthropic-compatible SSE response and emit incremental content."""
        model_name = model or self.default_model

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
                blocks: list[dict[str, Any]] = []
                if isinstance(content, str) and content:
                    blocks.append({"type": "text", "text": content})
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            blocks.append(item)
                        else:
                            blocks.append({"type": "text", "text": str(item)})

                for tc in msg.get("tool_calls", []) or []:
                    if not isinstance(tc, dict):
                        continue
                    func = tc.get("function", {})
                    args = func.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}

                    blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", str(uuid.uuid4())),
                        "name": func.get("name", ""),
                        "input": args if isinstance(args, dict) else {},
                    })

                anthropic_messages.append({
                    "role": "assistant",
                    "content": blocks or [{"type": "text", "text": ""}],
                })
            elif role == "tool":
                tool_result = {
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id", ""),
                    "content": content if isinstance(content, (str, list)) else str(content or ""),
                }
                if anthropic_messages and anthropic_messages[-1].get("role") == "user":
                    prev_content = anthropic_messages[-1].get("content")
                    if isinstance(prev_content, list):
                        prev_content.append(tool_result)
                        anthropic_messages[-1]["content"] = prev_content
                    else:
                        anthropic_messages[-1]["content"] = [
                            {"type": "text", "text": str(prev_content or "")},
                            tool_result,
                        ]
                else:
                    anthropic_messages.append({"role": "user", "content": [tool_result]})

        merged_messages: list[dict[str, Any]] = []
        for msg in anthropic_messages:
            if merged_messages and merged_messages[-1].get("role") == msg.get("role"):
                prev = merged_messages[-1].get("content")
                cur = msg.get("content")

                if isinstance(prev, str):
                    prev_blocks: list[dict[str, Any]] = [{"type": "text", "text": prev}]
                else:
                    prev_blocks = list(prev or [])

                if isinstance(cur, str):
                    cur_blocks: list[dict[str, Any]] = [{"type": "text", "text": cur}]
                else:
                    cur_blocks = list(cur or [])

                prev_blocks.extend(cur_blocks)
                merged_messages[-1]["content"] = prev_blocks
            else:
                merged_messages.append(msg)

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": merged_messages,
            "temperature": temperature,
            "max_tokens": max(1, max_tokens),
            "stream": True if enable_streaming_mode else False,
        }

        if enable_think_mode:
            budget = min(max(1024, max_tokens // 2), 8192)
            payload["thinking"] = {
                "type": "enabled",
                "budget_tokens": budget,
            }

        if system:
            payload["system"] = system

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

        content_parts: list[str] = []
        finish_reason = "stop"
        usage: dict[str, int] = {}

        # Anthropic streams tool input as partial JSON fragments per block index.
        tool_stream_by_index: dict[int, dict[str, Any]] = {}

        try:
            async with self.client.stream("POST", "/messages", json=payload) as response:
                response.raise_for_status()

                async for raw_line in response.aiter_lines():
                    if not raw_line:
                        continue
                    if not raw_line.startswith("data:"):
                        continue

                    data_str = raw_line[len("data:"):].strip()
                    if not data_str:
                        continue

                    try:
                        event = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type", "")

                    if event_type == "content_block_start":
                        block = event.get("content_block", {})
                        block_index = int(event.get("index", 0))
                        if block.get("type") == "tool_use":
                            tool_stream_by_index[block_index] = {
                                "id": block.get("id", ""),
                                "name": block.get("name", ""),
                                "arguments": "",
                            }

                    elif event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        delta_type = delta.get("type", "")
                        if delta_type == "text_delta":
                            text = delta.get("text", "")
                            if isinstance(text, str) and text:
                                content_parts.append(text)
                                if on_content_delta:
                                    await on_content_delta(text)
                        elif delta_type == "input_json_delta":
                            block_index = int(event.get("index", 0))
                            partial_json = delta.get("partial_json", "")
                            if isinstance(partial_json, str):
                                tool_entry = tool_stream_by_index.setdefault(block_index, {
                                    "id": "",
                                    "name": "",
                                    "arguments": "",
                                })
                                tool_entry["arguments"] += partial_json

                    elif event_type == "message_delta":
                        delta = event.get("delta", {})
                        finish_reason = delta.get("stop_reason") or finish_reason
                        event_usage = event.get("usage", {})
                        if isinstance(event_usage, dict):
                            usage = {
                                "prompt_tokens": int(event_usage.get("input_tokens", usage.get("prompt_tokens", 0))),
                                "completion_tokens": int(event_usage.get("output_tokens", usage.get("completion_tokens", 0))),
                            }

                    elif event_type == "message_start":
                        message_obj = event.get("message", {})
                        event_usage = message_obj.get("usage", {})
                        if isinstance(event_usage, dict):
                            usage = {
                                "prompt_tokens": int(event_usage.get("input_tokens", 0)),
                                "completion_tokens": int(event_usage.get("output_tokens", 0)),
                            }

            tool_calls: list[ToolCall] = []
            for block_index in sorted(tool_stream_by_index.keys()):
                raw_tool = tool_stream_by_index[block_index]
                args_obj: dict[str, Any] = {}
                raw_args = raw_tool.get("arguments", "")
                if raw_args:
                    try:
                        parsed = json.loads(raw_args)
                        if isinstance(parsed, dict):
                            args_obj = parsed
                    except json.JSONDecodeError:
                        args_obj = {}

                tool_calls.append(
                    ToolCall(
                        id=raw_tool.get("id") or str(uuid.uuid4()),
                        name=raw_tool.get("name") or "",
                        arguments=args_obj,
                    )
                )

            return LLMResponse(
                content="".join(content_parts) or None,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage=usage,
            )

        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.text
            except Exception:
                detail = ""
            status = e.response.status_code if e.response is not None else "unknown"
            message = f"Error: HTTP {status} calling {e.request.url if e.request else '/messages'}"
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
