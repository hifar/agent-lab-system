"""Agent main loop and execution logic."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_lab.knowledge import KnowledgeLoader
from agent_lab.providers.base import LLMProvider
from agent_lab.skills import SkillsLoader
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
        enable_think_mode: bool = False,
        enable_streaming_mode: bool = False,
        enable_log: bool = False,
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
        self.enable_think_mode = enable_think_mode
        self.enable_streaming_mode = enable_streaming_mode
        self.enable_log = enable_log
        self.log_dir = self.workspace / "log"
        self._system_prompt = system_prompt

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

    def _log_llm_interaction(
        self,
        *,
        iteration: int,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any],
    ) -> None:
        """Append one LLM interaction record to workspace log file."""
        if not self.enable_log:
            return

        self.log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc)
        day = ts.strftime('%Y%m%d')
        jsonl_file = self.log_dir / f"llm-interactions-{day}.jsonl"
        readable_file = self.log_dir / f"llm-interactions-{day}.log"

        provider_name = self.provider.__class__.__name__
        base_url = self.provider.api_base or "<default>"

        record = {
            "timestamp": ts.isoformat(),
            "iteration": iteration,
            "request_type": "llm_request",
            "response_type": "llm_response",
            "provider": provider_name,
            "base_url": base_url,
            "model": self.model,
            "request": request_payload,
            "response": response_payload,
        }

        try:
            with open(jsonl_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

            separator = "=" * 88
            request_line = (
                f"[REQUEST ] ts={ts.isoformat()} | iteration={iteration} | provider={provider_name} "
                f"| model={self.model} | base_url={base_url}"
            )
            response_line = (
                f"[RESPONSE] ts={ts.isoformat()} | iteration={iteration} | provider={provider_name} "
                f"| model={self.model} | base_url={base_url}"
            )

            with open(readable_file, "a", encoding="utf-8") as f:
                f.write(separator + "\n")
                f.write(request_line + "\n")
                f.write("-" * 88 + "\n")
                f.write(json.dumps(request_payload, ensure_ascii=False, indent=2, default=str) + "\n")
                f.write("\n")
                f.write(response_line + "\n")
                f.write("-" * 88 + "\n")
                f.write(json.dumps(response_payload, ensure_ascii=False, indent=2, default=str) + "\n")
                f.write(separator + "\n\n")
        except OSError:
            # Logging must never break the agent main flow.
            return

    def _build_system_prompt(self) -> str:
        """Build system prompt for the agent."""
        if self._system_prompt:
            return self._system_prompt

        tool_names = self.tools.tool_names
        tool_list = "\n".join(f"- {name}" for name in tool_names)
        workspace_context = self._build_workspace_context()

        return f"""You are an AI agent with access to tools.

Available tools:
{tool_list}

When you need to use a tool, call it with the appropriate parameters.
Think step-by-step before taking action.
Be concise and direct in your responses.

{workspace_context}"""

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

    def _build_workspace_context(self) -> str:
        """Build prompt context from workspace files and project-level defaults."""
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

        memory = self._read_text_file(self.workspace / "memories" / "long_term.md")
        if memory:
            sections.append(f"## Long-term Memory\n{memory}")

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
            resolved_think = (
                enable_think_mode if enable_think_mode is not None else self.enable_think_mode
            )
            resolved_streaming = (
                enable_streaming_mode
                if enable_streaming_mode is not None
                else self.enable_streaming_mode
            )

            # Call LLM
            chat_kwargs = {
                "messages": messages,
                "tools": self.tools.get_definitions() if self.tools.tool_names else None,
                "model": self.model,
                "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
                "temperature": temperature if temperature is not None else self.temperature,
                "tool_choice": tool_choice,
                "enable_think_mode": resolved_think,
                "enable_streaming_mode": resolved_streaming,
            }

            if resolved_streaming and on_content_delta:
                response = await self.provider.chat_stream(
                    **chat_kwargs,
                    on_content_delta=on_content_delta,
                )
            else:
                response = await self.provider.chat(**chat_kwargs)

            self._log_llm_interaction(
                iteration=iteration,
                request_payload=chat_kwargs,
                response_payload=self._serialize_response(response),
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
