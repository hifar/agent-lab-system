"""Lightweight web chat UI for calling agent-lab API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel, Field


INDEX_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "index.html"
DEFAULTS_PLACEHOLDER = "__DEFAULTS_JSON__"


class ChatHistoryMessage(BaseModel):
    """Chat history message in OpenAI-compatible format."""

    role: Literal["user", "assistant"]
    content: str


class ProxyChatRequest(BaseModel):
    """Payload accepted by the web UI proxy endpoint."""

    api_base: str = Field(default="http://127.0.0.1:8000")
    api_key: str | None = None
    model: str | None = None
    workspace: str | None = None
    background: str | None = None
    session: str = "default"
    session_mode: Literal["append", "stateless", "replace"] = "append"
    think_mode: bool = False
    rebuild_system_prompt: bool = False
    stream: bool = True
    max_tokens: int | None = None
    temperature: float | None = None
    history: list[ChatHistoryMessage] = Field(default_factory=list)


def _extract_delta_content(chunk: dict[str, Any]) -> str:
    """Extract assistant delta text from one OpenAI-compatible chunk."""
    try:
        choices = chunk.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""

        choice0 = choices[0]
        if not isinstance(choice0, dict):
            return ""

        delta = choice0.get("delta")
        if not isinstance(delta, dict):
            delta = {}

        content = delta.get("content")
        if isinstance(content, str):
            return content

        text = _extract_text_like(content)
        if text:
            return text

        reasoning_content = delta.get("reasoning_content")
        if isinstance(reasoning_content, str):
            return reasoning_content
        text = _extract_text_like(reasoning_content)
        if text:
            return text

        message = choice0.get("message")
        if isinstance(message, dict):
            msg_content = message.get("content")
            if isinstance(msg_content, str):
                return msg_content
            text = _extract_text_like(msg_content)
            if text:
                return text

        return ""
    except Exception:
        return ""


def _extract_text_like(content: Any) -> str:
    """Normalize text-like payloads from dict/list/string content fields."""
    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, dict):
        for key in ("text", "content", "value", "output_text", "input_text"):
            value = content.get(key)
            if isinstance(value, str) and value:
                return value
            nested = _extract_text_like(value)
            if nested:
                return nested
        return ""

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            text = _extract_text_like(item)
            if text:
                parts.append(text)
        return "".join(parts)

    return ""


def _ui_event(payload: dict[str, Any]) -> str:
    """Encode one SSE data event line for the browser."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _resolve_chat_completions_url(api_base: str) -> str:
    """Resolve chat completion URL from flexible API base inputs."""
    base = api_base.strip().rstrip("/")
    lower = base.lower()

    if lower.endswith("/chat/completions"):
        return base
    if lower.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _render_index_html(*, default_api_base: str, default_api_key: str | None, default_model: str | None) -> str:
    """Read and render HTML template with runtime defaults injected."""
    defaults = {
        "apiBase": default_api_base,
        "apiKey": default_api_key or "",
        "model": default_model or "",
        "workspace": "",
        "background": "",
        "session": "default",
        "sessionMode": "append",
        "thinkMode": False,
        "rebuildSystemPrompt": False,
        "maxTokens": "",
        "temperature": "",
    }

    template = INDEX_TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.replace(DEFAULTS_PLACEHOLDER, json.dumps(defaults, ensure_ascii=False), 1)


def create_web_app(
    default_api_base: str = "http://127.0.0.1:8000",
    default_api_key: str | None = None,
    default_model: str | None = None,
) -> FastAPI:
    """Create FastAPI app exposing a clean browser UI and chat proxy."""

    app = FastAPI(title="agent-lab web", version="0.1.0")

    @app.get("/favicon.ico")
    async def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/.well-known/appspecific/com.chrome.devtools.json")
    async def chrome_probe() -> Response:
        return Response(status_code=204)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return _render_index_html(
            default_api_base=default_api_base,
            default_api_key=default_api_key,
            default_model=default_model,
        )

    @app.post("/proxy/chat")
    async def proxy_chat(request: ProxyChatRequest) -> StreamingResponse:
        api_base = request.api_base.strip().rstrip("/")
        if not api_base:
            return StreamingResponse(
                iter([_ui_event({"type": "error", "message": "api_base is required"}), _ui_event({"type": "done"})]),
                media_type="text/event-stream",
            )

        url = _resolve_chat_completions_url(api_base)
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [m.model_dump() for m in request.history],
            "workspace": request.workspace,
            "background": request.background,
            "session": request.session,
            "session_mode": request.session_mode,
            "think_mode": request.think_mode,
            "rebuild_system_prompt": request.rebuild_system_prompt,
            "stream": request.stream,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if request.api_key and request.api_key.strip():
            headers["Authorization"] = f"Bearer {request.api_key.strip()}"

        async def event_stream():
            timeout = httpx.Timeout(timeout=None, connect=20.0)
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream("POST", url, headers=headers, json=payload) as upstream:
                        if upstream.status_code >= 400:
                            body = await upstream.aread()
                            detail = body.decode("utf-8", errors="replace").strip() or f"HTTP {upstream.status_code}"
                            yield _ui_event({"type": "error", "message": detail})
                            yield _ui_event({"type": "done"})
                            return

                        content_type = upstream.headers.get("content-type", "")
                        if "text/event-stream" in content_type.lower():
                            async for line in upstream.aiter_lines():
                                if not line or not line.startswith("data:"):
                                    continue
                                raw = line[5:].strip()
                                if not raw:
                                    continue
                                if raw == "[DONE]":
                                    yield _ui_event({"type": "done"})
                                    return

                                try:
                                    chunk = json.loads(raw)
                                except json.JSONDecodeError:
                                    continue

                                text = _extract_delta_content(chunk)
                                if text:
                                    yield _ui_event({"type": "delta", "text": text})

                            yield _ui_event({"type": "done"})
                            return

                        body = await upstream.aread()
                        result = json.loads(body.decode("utf-8", errors="replace"))

                        text = ""
                        choices = result.get("choices")
                        if isinstance(choices, list) and choices:
                            c0 = choices[0] if isinstance(choices[0], dict) else {}
                            msg = c0.get("message") if isinstance(c0, dict) else {}
                            if isinstance(msg, dict):
                                text = _extract_text_like(msg.get("content"))

                        if not text:
                            text = _extract_text_like(result.get("output_text"))

                        if text:
                            yield _ui_event({"type": "delta", "text": text})
                        yield _ui_event({"type": "done"})
                        return
            except Exception as exc:  # pragma: no cover
                yield _ui_event({"type": "error", "message": f"proxy error: {exc}"})
                yield _ui_event({"type": "done"})

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return app
