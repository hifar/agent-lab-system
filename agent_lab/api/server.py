"""FastAPI server exposing an OpenAI-compatible chat API for agent-lab."""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent_lab.agent import Agent
from agent_lab.config import Config, load_config
from agent_lab.providers import create_provider
from agent_lab.session import Session
from agent_lab.tools import ListDirTool, ReadFileTool, ToolRegistry, WriteFileTool


SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class ChatMessage(BaseModel):
    """OpenAI chat message format."""

    role: Literal["system", "developer", "user", "assistant", "tool", "function"]
    content: Any | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class ChatCompletionRequest(BaseModel):
    """Subset of OpenAI /v1/chat/completions request fields."""

    model: str | None = None
    messages: list[ChatMessage]
    max_tokens: int | None = None
    max_completion_tokens: int | None = None
    temperature: float | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    think_mode: bool | None = None
    streaming_mode: bool | None = None
    stream: bool = False
    workspace: str | None = None
    session: str | None = None
    session_mode: Literal["append", "stateless", "replace"] | None = None


class ModelCard(BaseModel):
    """OpenAI-compatible model card."""

    id: str
    object: str = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "agent-lab"


class ModelsResponse(BaseModel):
    """OpenAI-compatible models response."""

    object: str = "list"
    data: list[ModelCard]


def _build_registry(cfg: Config, workspace_path: Path) -> ToolRegistry:
    """Create tool registry based on configured tool flags."""
    workspace_path.mkdir(parents=True, exist_ok=True)

    tools = ToolRegistry()
    if cfg.tools.enable_read_file:
        tools.register(ReadFileTool(workspace_path))
    if cfg.tools.enable_write_file:
        tools.register(WriteFileTool(workspace_path))
    if cfg.tools.enable_list_dir:
        tools.register(ListDirTool(workspace_path))
    return tools


def _extract_agent_input(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Split OpenAI-style messages into (last user input, prior history)."""
    if not messages:
        raise ValueError("messages cannot be empty")

    history = [_normalize_message(dict(m)) for m in messages]

    for idx in range(len(history) - 1, -1, -1):
        msg = history[idx]
        if msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                return content, history[:idx]
            raise ValueError("last user message content must be a non-empty string")

    raise ValueError("at least one user message is required")


def _normalize_content(content: Any) -> str | None:
    """Normalize OpenAI multimodal message content into plain text."""
    if content is None:
        return None

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text") or item.get("input_text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        joined = "\n".join(p.strip() for p in parts if p and p.strip())
        return joined or json.dumps(content, ensure_ascii=False)

    if isinstance(content, dict):
        text = content.get("text") or content.get("input_text") or content.get("content")
        if isinstance(text, str):
            return text
        return json.dumps(content, ensure_ascii=False)

    return str(content)


def _normalize_message(message: dict[str, Any]) -> dict[str, Any]:
    """Normalize message role/content for provider compatibility."""
    normalized = dict(message)

    role = str(normalized.get("role", "user"))
    if role == "developer":
        role = "system"
    elif role == "function":
        role = "tool"
    normalized["role"] = role

    normalized["content"] = _normalize_content(normalized.get("content"))
    return normalized


def _completion_response(
    *,
    model: str,
    content: str,
    usage: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Build OpenAI-compatible chat completion response payload."""
    usage = usage or {}
    prompt_tokens = int(usage.get("prompt_tokens", 0))
    completion_tokens = int(usage.get("completion_tokens", 0))

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def _completion_chunk(
    *,
    model: str,
    delta: dict[str, Any],
    finish_reason: str | None,
) -> dict[str, Any]:
    """Build OpenAI-compatible streaming chunk payload."""
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }
        ],
    }


def _sse_line(payload: dict[str, Any]) -> str:
    """Encode one SSE data line."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _resolve_override(
    *,
    body_value: str | None,
    query_value: str | None,
    header_value: str | None,
    default: str,
) -> str:
    """Resolve body/query/header override by precedence."""
    if body_value:
        return body_value
    if query_value:
        return query_value
    if header_value:
        return header_value
    return default


def _validate_session_id(session_id: str) -> str:
    """Validate session id to prevent invalid file names and path traversal."""
    if not SESSION_ID_PATTERN.fullmatch(session_id):
        raise ValueError(
            "session must match ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
        )
    return session_id


def _resolve_runtime_context(
    body: ChatCompletionRequest,
    raw_request: Request,
    cfg: Config,
) -> tuple[Path, str, str]:
    """Resolve workspace/session/session_mode from body, query, headers, and defaults."""
    workspace_value = _resolve_override(
        body_value=body.workspace,
        query_value=raw_request.query_params.get("workspace"),
        header_value=raw_request.headers.get("X-AgentLab-Workspace"),
        default=cfg.agents.defaults.workspace,
    )
    session_value = _resolve_override(
        body_value=body.session,
        query_value=raw_request.query_params.get("session"),
        header_value=raw_request.headers.get("X-AgentLab-Session"),
        default="default",
    )
    session_mode = _resolve_override(
        body_value=body.session_mode,
        query_value=raw_request.query_params.get("session_mode"),
        header_value=raw_request.headers.get("X-AgentLab-Session-Mode"),
        default="append",
    )

    if session_mode not in {"append", "stateless", "replace"}:
        raise ValueError("session_mode must be one of: append, stateless, replace")

    workspace_path = Path(workspace_value).expanduser()
    session_id = _validate_session_id(session_value)
    return workspace_path, session_id, session_mode


def _extract_request_api_key(raw_request: Request) -> str | None:
    """Extract API key from standard auth headers."""
    authorization = raw_request.headers.get("Authorization")
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value.strip():
            return value.strip()
        if authorization.strip():
            return authorization.strip()

    x_api_key = raw_request.headers.get("X-API-Key")
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()

    return None


def _enforce_api_auth(cfg: Config, raw_request: Request) -> None:
    """Validate incoming API key when API auth is enabled."""
    if not cfg.api_auth:
        return

    if not cfg.api_keys:
        raise HTTPException(status_code=500, detail="api_auth is enabled but api_keys is empty")

    request_api_key = _extract_request_api_key(raw_request)
    if not request_api_key or request_api_key not in cfg.api_keys:
        raise HTTPException(status_code=401, detail="invalid or missing API key")


def create_app(config_path: str | None = None) -> FastAPI:
    """Create FastAPI app that exposes OpenAI-compatible endpoints."""
    cfg = load_config(Path(config_path)) if config_path else load_config()

    app = FastAPI(title="agent-lab OpenAI-compatible API", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/models", response_model=ModelsResponse)
    async def list_models(raw_request: Request) -> ModelsResponse:
        _enforce_api_auth(cfg, raw_request)
        model_name = cfg.agents.defaults.model
        return ModelsResponse(data=[ModelCard(id=model_name)])

    @app.post("/v1/chat/completions")
    async def chat_completions(request: ChatCompletionRequest, raw_request: Request) -> Any:
        _enforce_api_auth(cfg, raw_request)

        if request.tools:
            raise HTTPException(
                status_code=400,
                detail="request.tools is not supported yet; API uses configured built-in agent tools",
            )

        resolved_streaming = request.streaming_mode if request.streaming_mode is not None else request.stream

        try:
            workspace_path, session_id, session_mode = _resolve_runtime_context(request, raw_request, cfg)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        workspace_path.mkdir(parents=True, exist_ok=True)

        provider = create_provider(cfg, request.model)
        tools = _build_registry(cfg, workspace_path)
        session = Session(session_id, workspace_path)

        agent = Agent(
            provider=provider,
            tools=tools,
            workspace=workspace_path,
            model=request.model,
            max_iterations=cfg.agents.defaults.max_iterations,
            max_tokens=cfg.agents.defaults.max_tokens,
            temperature=cfg.agents.defaults.temperature,
            enable_think_mode=cfg.agents.defaults.enable_think_mode,
            enable_streaming_mode=cfg.agents.defaults.enable_streaming_mode,
            enable_log=cfg.log,
        )

        response_model_name = request.model or cfg.agents.defaults.model

        try:
            user_message, explicit_history = _extract_agent_input([m.model_dump(exclude_none=True) for m in request.messages])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if session_mode == "stateless":
            history = explicit_history
        elif session_mode == "replace":
            history = explicit_history
        else:
            history = explicit_history if explicit_history else session.load_history()

        if request.stream:
            async def event_stream():
                queue: asyncio.Queue[str | None] = asyncio.Queue()
                emitted_any_content = False

                await queue.put(_sse_line(
                    _completion_chunk(
                        model=response_model_name,
                        delta={"role": "assistant"},
                        finish_reason=None,
                    )
                ))

                async def on_delta(chunk: str) -> None:
                    nonlocal emitted_any_content
                    if not chunk:
                        return
                    emitted_any_content = True
                    await queue.put(_sse_line(
                        _completion_chunk(
                            model=response_model_name,
                            delta={"content": chunk},
                            finish_reason=None,
                        )
                    ))

                async def run_agent_task() -> None:
                    try:
                        final_text, messages = await agent.run(
                            user_message,
                            history,
                            max_tokens=request.max_tokens or request.max_completion_tokens,
                            temperature=request.temperature,
                            tool_choice=request.tool_choice,
                            enable_think_mode=request.think_mode,
                            enable_streaming_mode=resolved_streaming,
                            on_content_delta=on_delta,
                        )

                        if session_mode != "stateless":
                            session.save_history(messages)

                        if final_text and not emitted_any_content:
                            await queue.put(_sse_line(
                                _completion_chunk(
                                    model=response_model_name,
                                    delta={"content": final_text},
                                    finish_reason=None,
                                )
                            ))

                        await queue.put(_sse_line(
                            _completion_chunk(
                                model=response_model_name,
                                delta={},
                                finish_reason="stop",
                            )
                        ))
                    except ValueError as exc:
                        await queue.put(_sse_line(
                            _completion_chunk(
                                model=response_model_name,
                                delta={"content": f"Error: {exc}"},
                                finish_reason="stop",
                            )
                        ))
                    except Exception as exc:
                        await queue.put(_sse_line(
                            _completion_chunk(
                                model=response_model_name,
                                delta={"content": f"Error: agent execution failed: {exc}"},
                                finish_reason="stop",
                            )
                        ))
                    finally:
                        await queue.put("data: [DONE]\n\n")
                        await queue.put(None)

                producer = asyncio.create_task(run_agent_task())
                try:
                    while True:
                        item = await queue.get()
                        if item is None:
                            break
                        yield item
                finally:
                    if not producer.done():
                        producer.cancel()

            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        try:
            final_text, messages = await agent.run(
                user_message,
                history,
                max_tokens=request.max_tokens or request.max_completion_tokens,
                temperature=request.temperature,
                tool_choice=request.tool_choice,
                enable_think_mode=request.think_mode,
                enable_streaming_mode=resolved_streaming,
            )
            if session_mode != "stateless":
                session.save_history(messages)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"agent execution failed: {exc}") from exc

        # The provider usage is not currently propagated through Agent.run;
        # keep OpenAI-compatible usage fields with zeros for now.
        return _completion_response(
            model=response_model_name,
            content=final_text,
            usage={},
        )

    return app
