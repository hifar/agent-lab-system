"""FastAPI server exposing an OpenAI-compatible chat API for agent-lab."""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agent_lab.agent import Agent
from agent_lab.config import Config, load_config
from agent_lab.providers import create_provider
from agent_lab.tools import ListDirTool, ReadFileTool, ToolRegistry, WriteFileTool


class ChatMessage(BaseModel):
    """OpenAI chat message format."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class ChatCompletionRequest(BaseModel):
    """Subset of OpenAI /v1/chat/completions request fields."""

    model: str | None = None
    messages: list[ChatMessage]
    max_tokens: int | None = None
    temperature: float | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    think_mode: bool | None = None
    streaming_mode: bool | None = None
    stream: bool = False


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


def _build_registry(cfg: Config) -> ToolRegistry:
    """Create tool registry based on configured tool flags."""
    workspace_path = cfg.workspace_path
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

    history = [dict(m) for m in messages]

    for idx in range(len(history) - 1, -1, -1):
        msg = history[idx]
        if msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                return content, history[:idx]
            raise ValueError("last user message content must be a non-empty string")

    raise ValueError("at least one user message is required")


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


def create_app(config_path: str | None = None) -> FastAPI:
    """Create FastAPI app that exposes OpenAI-compatible endpoints."""
    cfg = load_config(Path(config_path)) if config_path else load_config()

    app = FastAPI(title="agent-lab OpenAI-compatible API", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/models", response_model=ModelsResponse)
    async def list_models() -> ModelsResponse:
        model_name = cfg.agents.defaults.model
        return ModelsResponse(data=[ModelCard(id=model_name)])

    @app.post("/v1/chat/completions")
    async def chat_completions(request: ChatCompletionRequest) -> dict[str, Any]:
        if request.tools:
            raise HTTPException(
                status_code=400,
                detail="request.tools is not supported yet; API uses configured built-in agent tools",
            )

        resolved_streaming = request.streaming_mode if request.streaming_mode is not None else request.stream

        provider = create_provider(cfg, request.model)
        tools = _build_registry(cfg)

        agent = Agent(
            provider=provider,
            tools=tools,
            workspace=cfg.workspace_path,
            model=request.model,
            max_iterations=cfg.agents.defaults.max_iterations,
            max_tokens=cfg.agents.defaults.max_tokens,
            temperature=cfg.agents.defaults.temperature,
            enable_think_mode=cfg.agents.defaults.enable_think_mode,
            enable_streaming_mode=cfg.agents.defaults.enable_streaming_mode,
            enable_log=cfg.log,
        )

        try:
            user_message, history = _extract_agent_input([m.model_dump(exclude_none=True) for m in request.messages])
            final_text, _ = await agent.run(
                user_message,
                history,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                tool_choice=request.tool_choice,
                enable_think_mode=request.think_mode,
                enable_streaming_mode=resolved_streaming,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"agent execution failed: {exc}") from exc

        # The provider usage is not currently propagated through Agent.run;
        # keep OpenAI-compatible usage fields with zeros for now.
        return _completion_response(
            model=request.model or cfg.agents.defaults.model,
            content=final_text,
            usage={},
        )

    return app
