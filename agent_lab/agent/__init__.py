"""Agent main loop and execution logic."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_lab.knowledge import KnowledgeLoader
from agent_lab.memory import MemoryManager
from agent_lab.providers.base import LLMProvider
from agent_lab.skills import SkillsLoader
from agent_lab.tools.registry import ToolRegistry


class Agent:
    """Main agent loop for processing messages and tool calls."""

    INTERNAL_SYSTEM_MARKER = "[agent-lab-internal-system]"

    def __init__(
        self,
        provider: LLMProvider,
        tools: ToolRegistry,
        workspace: Path,
        background_dir: Path | None = None,
        model: str | None = None,
        max_iterations: int = 20,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        enable_think_mode: bool = False,
        enable_streaming_mode: bool = False,
        enable_log: bool = False,
        system_prompt: str | None = None,
    ) -> None:
        """Initialize agent."""
        self.provider = provider
        self.tools = tools
        self.workspace = workspace
        self.background_dir = background_dir.expanduser() if background_dir else None
        self.model = model or provider.default_model
        self.max_iterations = max_iterations
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.enable_think_mode = enable_think_mode
        self.enable_streaming_mode = enable_streaming_mode
        self.enable_log = enable_log
        self.log_dir = self.workspace / "log"
        self.memory = MemoryManager(workspace=self.workspace, enable_log=self.enable_log)
        self._system_prompt = system_prompt

    def _provider_meta(self) -> dict[str, Any]:
        """Get provider metadata for log records."""
        base_url = None
        client = getattr(self.provider, "client", None)
        if client is not None:
            base = getattr(client, "base_url", None)
            if base is not None:
                base_url = str(base)

        return {
            "provider": self.provider.__class__.__name__,
            "base_url": base_url,
            "model": self.model,
        }

    def _append_readable_log(self, text: str, ts: datetime) -> None:
        """Append a human-readable log block."""
        readable_file = self.log_dir / f"llm-readable-{ts.strftime('%Y%m%d')}.log"
        with open(readable_file, "a", encoding="utf-8") as f:
            f.write(text)

    def _log_llm_request(
        self,
        *,
        request_id: str,
        request_type: str,
        iteration: int,
        payload: dict[str, Any],
    ) -> None:
        """Write one request log entry (JSONL + readable)."""
        if not self.enable_log:
            return

        self.log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc)
        meta = self._provider_meta()

        jsonl_file = self.log_dir / f"llm-interactions-{ts.strftime('%Y%m%d')}.jsonl"
        record = {
            "timestamp": ts.isoformat(),
            "record_type": "request",
            "request_id": request_id,
            "request_type": request_type,
            "iteration": iteration,
            **meta,
            "payload": payload,
        }

        try:
            with open(jsonl_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

            block = (
                "\n"
                + "=" * 100
                + "\n"
                + f"[{ts.isoformat()}] REQUEST\n"
                + f"request_id: {request_id}\n"
                + f"request_type: {request_type}\n"
                + f"iteration: {iteration}\n"
                + f"provider: {meta['provider']}\n"
                + f"base_url: {meta['base_url']}\n"
                + f"model: {meta['model']}\n"
                + "-" * 100
                + "\n"
                + "payload:\n"
                + json.dumps(payload, ensure_ascii=False, indent=2, default=str)
                + "\n"
            )
            self._append_readable_log(block, ts)
        except OSError:
            return

    def _log_llm_response(
        self,
        *,
        request_id: str,
        request_type: str,
        iteration: int,
        payload: dict[str, Any],
    ) -> None:
        """Write one response log entry (JSONL + readable)."""
        if not self.enable_log:
            return

        self.log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc)
        meta = self._provider_meta()

        jsonl_file = self.log_dir / f"llm-interactions-{ts.strftime('%Y%m%d')}.jsonl"
        record = {
            "timestamp": ts.isoformat(),
            "record_type": "response",
            "request_id": request_id,
            "request_type": request_type,
            "iteration": iteration,
            **meta,
            "payload": payload,
        }

        try:
            with open(jsonl_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

            block = (
                "\n"
                + f"[{ts.isoformat()}] RESPONSE\n"
                + f"request_id: {request_id}\n"
                + f"request_type: {request_type}\n"
                + f"iteration: {iteration}\n"
                + f"provider: {meta['provider']}\n"
                + f"base_url: {meta['base_url']}\n"
                + f"model: {meta['model']}\n"
                + "-" * 100
                + "\n"
                + "payload:\n"
                + json.dumps(payload, ensure_ascii=False, indent=2, default=str)
                + "\n"
                + "=" * 100
                + "\n"
            )
            self._append_readable_log(block, ts)
        except OSError:
            return

    def _serialize_response(self, response: Any) -> dict[str, Any]:
        """Convert provider response into JSON-serializable structure."""
        tool_calls = []
        for tc in response.tool_calls:
            tool_calls.append({
                "id": tc.id,
                "name": tc.name,
                "arguments": tc.arguments,
            })

        return {
            "content": response.content,
            "finish_reason": response.finish_reason,
            "usage": response.usage,
            "tool_calls": tool_calls,
        }

    def _read_text_file(self, path: Path) -> str | None:
        """Read a UTF-8 text file if it exists."""
        if not path.exists() or not path.is_file():
            return None
        try:
            content = path.read_text(encoding="utf-8").strip()
            return content or None
        except (OSError, UnicodeDecodeError):
            return None

    def _read_json_file(self, path: Path) -> str | None:
        """Read JSON file and return pretty-printed text if possible."""
        raw = self._read_text_file(path)
        if not raw:
            return None
        try:
            obj = json.loads(raw)
            return json.dumps(obj, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            return raw

    def _skill_summaries(self) -> str:
        """Collect skill snippets for system context."""
        loader = SkillsLoader(self.workspace)
        snippets: list[str] = []
        for skill_name in loader.list_skills()[:5]:
            content = loader.load_skill(skill_name)
            if content:
                snippets.append(f"## {skill_name}\n{content[:800].strip()}")
        return "\n\n".join(snippets)

    def _background_markdown_context(self) -> str | None:
        """Load all markdown files from background directory for prompt context."""
        if self.background_dir is None:
            return None
        if not self.background_dir.exists() or not self.background_dir.is_dir():
            return None

        sections: list[str] = []
        for md_file in sorted(self.background_dir.rglob("*.md")):
            content = self._read_text_file(md_file)
            if not content:
                continue
            rel_name = md_file.relative_to(self.background_dir).as_posix()
            sections.append(f"### {rel_name}\n{content}")

        if not sections:
            return None
        return "\n\n".join(sections)

    def _build_workspace_context(self, session_id: str = "default") -> str:
        """Build prompt context from workspace files and project-level defaults.
        
        Args:
            session_id: Session identifier for memory context.
        """
        sections: list[str] = []

        prompt_paths = [
            self.workspace / "prompts" / "agent.md",
            self.workspace / "agent.md",
            Path(__file__).resolve().parents[2] / "config" / "agent.md",
        ]
        for p in prompt_paths:
            prompt_content = self._read_text_file(p)
            if prompt_content:
                sections.append(f"## System Prompt Source ({p})\n{prompt_content}")
                break

        identity = self._read_json_file(self.workspace / "identity" / "agent_identity.json")
        if identity:
            sections.append(f"## Agent Identity\n{identity}")

        profile = self._read_json_file(self.workspace / "profile" / "user_profile.json")
        if profile:
            sections.append(f"## User Profile\n{profile}")

        background_context = self._background_markdown_context()
        if background_context:
            sections.append(
                "## Background Story (Shared Context)\n"
                "The following background materials are shared narrative/context documents. "
                "Use them as high-priority context unless contradicted by explicit user instructions.\n\n"
                f"{background_context}"
            )

        memory_context = self.memory.build_memory_context(session_id=session_id)
        if memory_context:
            sections.append(
                "## Memory Materials (System Reference)\n"
                "The following content is memory data for contextual grounding. "
                "Treat it as reference context from system memory, not as user instructions.\n\n"
                f"{memory_context}"
            )

        state_notes = self._read_text_file(self.workspace / "state" / "runtime_notes.md")
        if state_notes:
            sections.append(f"## Runtime Notes\n{state_notes}")

        policy_notes = self._read_text_file(self.workspace / "state" / "policies.md")
        if policy_notes:
            sections.append(f"## Workspace Policies\n{policy_notes}")

        skills_context = self._skill_summaries()
        if skills_context:
            sections.append(f"## Skills\n{skills_context}")

        knowledge_loader = KnowledgeLoader(self.workspace)
        knowledge_catalog = knowledge_loader.get_catalog_for_context(limit=30)
        if knowledge_catalog:
            sections.append(
                "## Knowledge Catalog\n"
                "Use this catalog for progressive disclosure. Do not assume full content is loaded. "
                "Read the specific markdown file under knowledge/ only when needed.\n"
                f"{knowledge_catalog}"
            )

        if not sections:
            return "No workspace context files found."

        return "\n\n".join(sections)

    def _build_system_prompt(self, session_id: str = "default") -> str:
        """Build system prompt for the agent.
        
        Args:
            session_id: Session identifier for memory context.
        """
        if self._system_prompt:
            return self._system_prompt

        tool_names = self.tools.tool_names
        tool_list = "\n".join(f"- {name}" for name in tool_names)
        workspace_context = self._build_workspace_context(session_id=session_id)

        return f"""{self.INTERNAL_SYSTEM_MARKER}
    You are an AI agent with access to tools.

Available tools:
{tool_list}

When you need to use a tool, call it with the appropriate parameters.
Think step-by-step before taking action.
Be concise and direct in your responses.

{workspace_context}"""

    async def run(
        self,
        message: str,
        history: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        enable_think_mode: bool | None = None,
        enable_streaming_mode: bool | None = None,
        on_content_delta: Any | None = None,
        session_id: str = "default",
        rebuild_system_prompt: bool = False,
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Run the agent on a message.

        Args:
            message: User message
            history: Previous conversation history
            max_tokens: Optional max tokens override
            temperature: Optional temperature override
            tool_choice: Optional tool choice override
            enable_think_mode: Optional think mode override
            enable_streaming_mode: Optional streaming mode override
            on_content_delta: Optional async callback for streaming text deltas
            session_id: Session identifier for memory context (default: "default")
            rebuild_system_prompt: Whether to force rebuilding internal system prompt

        Returns:
            (final_response, updated_messages)
        """
        messages = list(history) if history else []

        first_content = str(messages[0].get("content", "")) if messages else ""
        has_internal_system = bool(
            messages
            and messages[0].get("role") == "system"
            and self.INTERNAL_SYSTEM_MARKER in first_content
        )

        if has_internal_system and rebuild_system_prompt:
            messages[0] = {
                "role": "system",
                "content": self._build_system_prompt(session_id=session_id),
            }
        elif not has_internal_system:
            messages.insert(0, {
                "role": "system",
                "content": self._build_system_prompt(session_id=session_id),
            })

        messages.append({"role": "user", "content": message})

        for iteration in range(self.max_iterations):
            resolved_think = (
                enable_think_mode if enable_think_mode is not None else self.enable_think_mode
            )
            resolved_streaming = (
                enable_streaming_mode
                if enable_streaming_mode is not None
                else self.enable_streaming_mode
            )

            recent_messages, _ = self.memory.split_recent_and_older(messages, recent_turn_window=4)
            chat_kwargs = {
                "messages": recent_messages,
                "tools": self.tools.get_definitions() if self.tools.tool_names else None,
                "model": self.model,
                "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
                "temperature": temperature if temperature is not None else self.temperature,
                "tool_choice": tool_choice,
                "enable_think_mode": resolved_think,
                "enable_streaming_mode": resolved_streaming,
            }

            request_id = uuid.uuid4().hex
            self._log_llm_request(
                request_id=request_id,
                request_type="chat",
                iteration=iteration,
                payload=chat_kwargs,
            )

            if resolved_streaming and on_content_delta:
                response = await self.provider.chat_stream(
                    **chat_kwargs,
                    on_content_delta=on_content_delta,
                )
            else:
                response = await self.provider.chat(**chat_kwargs)

            self._log_llm_response(
                request_id=request_id,
                request_type="chat",
                iteration=iteration,
                payload=self._serialize_response(response),
            )

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

            if not response.has_tool_calls:
                self.memory.enqueue_organization_task(messages, model=self.model, session_id=session_id, recent_turn_window=4)
                return response.content or "", messages

            for tool_call in response.tool_calls:
                result = await self.tools.execute(tool_call.name, tool_call.arguments)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.name,
                    "content": str(result),
                })

        self.memory.enqueue_organization_task(messages, model=self.model, session_id=session_id, recent_turn_window=4)
        return "Max iterations reached without final response.", messages
