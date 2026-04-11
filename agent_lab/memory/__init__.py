"""Memory module: queueing, organization, compression, and retrieval."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_lab.providers.base import LLMProvider


@dataclass
class MemoryTask:
    """Memory processing task payload."""

    task_id: str
    task_type: str
    created_at: str
    model: str
    older_messages: list[dict[str, Any]]
    recent_turn_window: int
    session_id: str = "default"


class MemoryManager:
    """Manages 3-layer memory and background organization tasks."""

    def __init__(self, workspace: Path, enable_log: bool = False) -> None:
        self.workspace = workspace
        self.enable_log = enable_log
        self.control_root = Path.home() / ".agent-lab"

        self.memories_dir = self.workspace / "memories"
        self.state_dir = self.workspace / "state"
        self.log_dir = self.workspace / "log"
        self.global_state_dir = self.control_root / "state"
        self.workspace_registry_file = self.global_state_dir / "memory_workspaces.json"

        self.long_term_file = self.memories_dir / "long_term.md"
        self.short_term_dir = self.memories_dir / "short_term"  # Session-local dir
        self.user_file = self.memories_dir / "user.md"
        self.agent_identity_file = self.memories_dir / "agent_identity.md"

        self.tasks_dir = self.state_dir / "memory_tasks"
        self.done_dir = self.state_dir / "memory_tasks_done"
        self.failed_dir = self.state_dir / "memory_tasks_failed"
        self.memory_prompt_file = Path(__file__).resolve().parents[2] / "config" / "memory_organizer_prompt.md"

        self.ensure_structure()

    def ensure_structure(self) -> None:
        """Ensure all memory-related dirs and files exist."""
        self.memories_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.global_state_dir.mkdir(parents=True, exist_ok=True)

        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.done_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)
        self.short_term_dir.mkdir(parents=True, exist_ok=True)

        for file_path, title in (
            (self.agent_identity_file, "# Agent Identity\n"),
            (self.user_file, "# User Profile Memory\n"),
            (self.long_term_file, "# Long-Term Memory\n"),
        ):
            if not file_path.exists():
                file_path.write_text(title, encoding="utf-8")

    def _register_workspace(self) -> None:
        """Register workspace in a global registry for memory service discovery."""
        self.global_state_dir.mkdir(parents=True, exist_ok=True)
        normalized = str(self.workspace.expanduser().resolve())

        workspaces: list[str] = []
        if self.workspace_registry_file.exists():
            try:
                raw = json.loads(self.workspace_registry_file.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    workspaces = [str(item) for item in raw if isinstance(item, str)]
            except (json.JSONDecodeError, OSError):
                workspaces = []

        if normalized not in workspaces:
            workspaces.append(normalized)
            self.workspace_registry_file.write_text(
                json.dumps(sorted(workspaces), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    @staticmethod
    def list_registered_workspaces() -> list[Path]:
        """List workspaces discovered from global memory activity."""
        registry_file = Path.home() / ".agent-lab" / "state" / "memory_workspaces.json"
        if not registry_file.exists():
            return []

        try:
            raw = json.loads(registry_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

        if not isinstance(raw, list):
            return []

        paths: list[Path] = []
        for item in raw:
            if isinstance(item, str) and item.strip():
                paths.append(Path(item).expanduser())
        return paths

    def _get_short_term_file(self, session_id: str = "default") -> Path:
        """Get session-local short-term memory file."""
        # Sanitize session_id for safe filename
        safe_session = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
        return self.short_term_dir / f"short_term_{safe_session}.md"

    def split_recent_and_older(
        self,
        messages: list[dict[str, Any]],
        recent_turn_window: int = 4,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Keep only last N user turns for LLM, return (recent, older)."""
        user_indices = [i for i, msg in enumerate(messages) if msg.get("role") == "user"]
        if len(user_indices) <= recent_turn_window:
            return list(messages), []

        start_idx = user_indices[-recent_turn_window]
        has_system = bool(messages and messages[0].get("role") == "system")

        recent = list(messages[start_idx:])
        if has_system:
            recent = [messages[0]] + recent
            older = list(messages[1:start_idx])
        else:
            older = list(messages[:start_idx])

        return recent, older

    def enqueue_organization_task(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        session_id: str = "default",
        recent_turn_window: int = 4,
    ) -> bool:
        """Enqueue memory organization task from older context.
        
        Args:
            messages: Full conversation history.
            model: Model name for the organization task.
            session_id: Session identifier for session-local memory tracking.
            recent_turn_window: Number of recent user turns to keep in context window.
        """
        _, older = self.split_recent_and_older(messages, recent_turn_window=recent_turn_window)
        if not older:
            return False

        self._register_workspace()

        task = MemoryTask(
            task_id=uuid.uuid4().hex,
            task_type="organize_memory",
            created_at=datetime.now(timezone.utc).isoformat(),
            model=model,
            older_messages=older,
            recent_turn_window=recent_turn_window,
        )
        task_path = self.tasks_dir / f"{task.task_id}.json"

        payload = {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "created_at": task.created_at,
            "model": task.model,
            "older_messages": task.older_messages,
            "recent_turn_window": task.recent_turn_window,
            "session_id": session_id,
        }
        task_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return True

    def build_memory_context(self, session_id: str = "default") -> str:
        """Build memory context for system prompt from 3 layers.
        
        Args:
            session_id: Session identifier for retrieving session-local short-term memory.
        """
        sections: list[str] = []

        short_term_file = self._get_short_term_file(session_id)
        
        for title, path in (
            ("Agent Identity Memory", self.agent_identity_file),
            ("User Memory", self.user_file),
            ("Long-Term Memory", self.long_term_file),
            ("Short-Term Memory", short_term_file),
        ):
            if path.exists() and path.is_file():
                text = path.read_text(encoding="utf-8").strip()
                if text:
                    sections.append(f"## {title}\n{text}")

        return "\n\n".join(sections)

    def _messages_to_text(self, messages: list[dict[str, Any]], limit_chars: int = 30000) -> str:
        parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content")
            if isinstance(content, str):
                content_text = content
            else:
                content_text = json.dumps(content, ensure_ascii=False, default=str)
            parts.append(f"[{role}] {content_text}")
        return "\n".join(parts)[:limit_chars]

    @staticmethod
    def _extract_json_object_text(text: str) -> str | None:
        """Best-effort extraction of a JSON object from raw model text."""
        stripped = text.strip()
        if not stripped:
            return None

        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 3 and lines[-1].strip() == "```":
                stripped = "\n".join(lines[1:-1]).strip()
                if stripped.lower().startswith("json"):
                    stripped = stripped[4:].strip()

        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            return stripped[start : end + 1]

        return None

    @staticmethod
    def _extract_body(text: str) -> str:
        """Extract markdown body after first heading line if present."""
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("#"):
            return "\n".join(lines[1:]).strip()
        return text.strip()

    def _read_memory_body(self, path: Path) -> str:
        """Read memory file body content without heading."""
        if not path.exists() or not path.is_file():
            return ""
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return ""
        return self._extract_body(text)

    def _write_memory_file(self, path: Path, title: str, body: str) -> None:
        """Rewrite memory file with heading and merged body."""
        normalized = body.strip()
        content = f"{title}\n\n{normalized}\n" if normalized else f"{title}\n"
        path.write_text(content, encoding="utf-8")

    def _load_memory_organizer_prompt(self) -> str:
        """Load memory organizer prompt from config file with safe fallback."""
        default_prompt = (
            "你是记忆整理器。请基于【现有记忆】和【历史对话】输出 JSON，且只输出 JSON。"
            "\n必须包含以下键:"
            "\nshort_term_merged: string"
            "\nshould_update_user: boolean"
            "\nuser_merged: string"
            "\nshould_update_agent_identity: boolean"
            "\nagent_identity_merged: string"
            "\nshould_update_long_term: boolean"
            "\nlong_term_merged: string"
            "\n规则:"
            "\n1) short_term_merged 需要把现有 short_term 与本次新增信息合并压缩，简洁可复用。"
            "\n2) 只要历史对话涉及用户偏好/背景/身份/目标/约束中的任一相关信息，就更新 user（should_update_user=true）。"
            "\n3) 只要历史对话涉及 agent 的角色、能力、边界、工作方式中的任一相关信息，就更新 agent_identity（should_update_agent_identity=true）。"
            "\n4) 只要出现可复用的事实、规则、长期约束、稳定目标、稳定偏好等长期价值信息，即可更新 long_term（should_update_long_term=true）。"
            "\n5) merged 字段应表示“合并后的完整内容”，用于覆盖写回，不是增量追加。"
            "\n6) 更新策略应偏积极：有相关就更新；仅在信息明显冲突或无法判断真实性时才保持不更新。"
        )

        try:
            text = self.memory_prompt_file.read_text(encoding="utf-8").strip()
            return text or default_prompt
        except OSError:
            return default_prompt

    def _provider_meta(self, provider: LLMProvider, model: str) -> dict[str, Any]:
        base_url = None
        client = getattr(provider, "client", None)
        if client is not None:
            base = getattr(client, "base_url", None)
            if base is not None:
                base_url = str(base)
        return {
            "provider": provider.__class__.__name__,
            "base_url": base_url,
            "model": model,
        }

    def _append_readable_log(self, text: str, ts: datetime) -> None:
        readable_file = self.log_dir / f"llm-readable-{ts.strftime('%Y%m%d')}.log"
        with open(readable_file, "a", encoding="utf-8") as f:
            f.write(text)

    def _log_llm_request(
        self,
        *,
        provider: LLMProvider,
        request_id: str,
        request_type: str,
        model: str,
        payload: dict[str, Any],
    ) -> None:
        if not self.enable_log:
            return

        ts = datetime.now(timezone.utc)
        meta = self._provider_meta(provider, model)
        jsonl_file = self.log_dir / f"llm-interactions-{ts.strftime('%Y%m%d')}.jsonl"

        record = {
            "timestamp": ts.isoformat(),
            "record_type": "request",
            "request_id": request_id,
            "request_type": request_type,
            "iteration": -1,
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
        provider: LLMProvider,
        request_id: str,
        request_type: str,
        model: str,
        payload: dict[str, Any],
    ) -> None:
        if not self.enable_log:
            return

        ts = datetime.now(timezone.utc)
        meta = self._provider_meta(provider, model)
        jsonl_file = self.log_dir / f"llm-interactions-{ts.strftime('%Y%m%d')}.jsonl"

        record = {
            "timestamp": ts.isoformat(),
            "record_type": "response",
            "request_id": request_id,
            "request_type": request_type,
            "iteration": -1,
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

    async def _organize_memory_with_llm(
        self,
        provider: LLMProvider,
        *,
        model: str,
        older_messages: list[dict[str, Any]],
        session_id: str = "default",
    ) -> None:
        """Use LLM to merge and rewrite memory layers with aggressive update strategy.
        
        Key strategy changes:
        - short_term: Session-local, completely replaced (not merged with other sessions)
        - user/agent_identity: Always updated (no should_update gates)
        - long_term: Updated if LLM returns non-empty content
        """
        history_text = self._messages_to_text(older_messages)

        current_agent_identity = self._read_memory_body(self.agent_identity_file)
        current_user = self._read_memory_body(self.user_file)
        current_long_term = self._read_memory_body(self.long_term_file)
        
        # Get session-local short-term memory
        short_term_file = self._get_short_term_file(session_id)
        current_short_term = self._read_memory_body(short_term_file)

        prompt = self._load_memory_organizer_prompt()

        messages = [
            {
                "role": "system",
                "content": "你是严格的 JSON 输出助手。",
            },
            {
                "role": "user",
                "content": (
                    f"{prompt}\n\n"
                    f"【现有 agent_identity】\n{current_agent_identity}\n\n"
                    f"【现有 user】\n{current_user}\n\n"
                    f"【现有 long_term】\n{current_long_term}\n\n"
                    f"【本会话 short_term】\n{current_short_term}\n\n"
                    f"【历史对话】\n{history_text}"
                ),
            },
        ]

        req = {
            "messages": messages,
            "tools": None,
            "model": model,
            "max_tokens": 1200,
            "temperature": 0.2,
            "tool_choice": None,
            "enable_think_mode": False,
            "enable_streaming_mode": False,
        }

        request_id = uuid.uuid4().hex
        self._log_llm_request(
            provider=provider,
            request_id=request_id,
            request_type="memory_organize",
            model=model,
            payload=req,
        )

        resp = await provider.chat(**req)
        response_payload = {
            "content": resp.content,
            "finish_reason": resp.finish_reason,
            "usage": resp.usage,
            "tool_calls": [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                for tc in resp.tool_calls
            ],
        }
        self._log_llm_response(
            provider=provider,
            request_id=request_id,
            request_type="memory_organize",
            model=model,
            payload=response_payload,
        )

        if not resp.content:
            return

        # Fallback: if JSON parse fails, append response to short_term
        fallback_data: dict[str, Any] = {
            "short_term_merged": (current_short_term + "\n" + resp.content).strip(),
            "user_merged": current_user,
            "agent_identity_merged": current_agent_identity,
            "long_term_merged": current_long_term,
        }

        data: dict[str, Any] = fallback_data
        candidate_text = self._extract_json_object_text(resp.content)
        if candidate_text is not None:
            try:
                parsed = json.loads(candidate_text)
                if isinstance(parsed, dict):
                    data = parsed
            except json.JSONDecodeError:
                pass

        short_term_merged = str(data.get("short_term_merged", current_short_term)).strip()
        user_merged = str(data.get("user_merged", current_user)).strip()
        agent_identity_merged = str(
            data.get("agent_identity_merged", current_agent_identity)
        ).strip()
        long_term_merged = str(data.get("long_term_merged", current_long_term)).strip()

        # Session-local short-term: completely replaced (not merged with past sessions)
        self._write_memory_file(short_term_file, f"# Short-Term Memory [{session_id}]", short_term_merged)

        # User memory: aggressive update (always merged, no gates)
        if user_merged:
            self._write_memory_file(self.user_file, "# User Profile Memory", user_merged)

        # Agent identity: aggressive update (always merged, no gates)
        if agent_identity_merged:
            self._write_memory_file(
                self.agent_identity_file,
                "# Agent Identity",
                agent_identity_merged,
            )

        # Long-term memory: conditional update (only if meaningful content)
        if long_term_merged and long_term_merged != current_long_term:
            self._write_memory_file(self.long_term_file, "# Long-Term Memory", long_term_merged)

    async def process_pending_tasks(
        self,
        provider: LLMProvider,
        *,
        default_model: str,
        once: bool = False,
        poll_interval_seconds: float = 2.0,
    ) -> None:
        """Process pending memory tasks in queue."""
        self.ensure_structure()

        while True:
            task_files = sorted(self.tasks_dir.glob("*.json"))

            for task_file in task_files:
                try:
                    raw = task_file.read_text(encoding="utf-8")
                    task_data = json.loads(raw)
                    task = MemoryTask(
                        task_id=str(task_data.get("task_id", task_file.stem)),
                        task_type=str(task_data.get("task_type", "organize_memory")),
                        created_at=str(task_data.get("created_at", "")),
                        model=str(task_data.get("model") or default_model),
                        older_messages=list(task_data.get("older_messages") or []),
                        recent_turn_window=int(task_data.get("recent_turn_window", 4)),
                        session_id=str(task_data.get("session_id", "default")),
                    )

                    if task.task_type == "organize_memory":
                        await self._organize_memory_with_llm(
                            provider,
                            model=task.model,
                            older_messages=task.older_messages,
                            session_id=task.session_id,
                        )

                    target = self.done_dir / f"{task_file.stem}.done.json"
                    task_file.replace(target)
                except Exception as exc:
                    failed_target = self.failed_dir / f"{task_file.stem}.failed.json"
                    try:
                        payload = {
                            "error": str(exc),
                            "task": task_file.read_text(encoding="utf-8"),
                        }
                        failed_target.write_text(
                            json.dumps(payload, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                        task_file.unlink(missing_ok=True)
                    except OSError:
                        pass

            if once:
                return

            await asyncio.sleep(max(0.2, poll_interval_seconds))


def stop_service_by_pid(pid_file: Path) -> bool:
    """Stop service process from pid file if possible."""
    if not pid_file.exists():
        return False

    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False

    try:
        os.kill(pid, 15)
    except OSError:
        return False

    try:
        pid_file.unlink(missing_ok=True)
    except OSError:
        pass
    return True


__all__ = ["MemoryManager", "MemoryTask", "stop_service_by_pid"]
