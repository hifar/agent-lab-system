"""Basic tests for agent-lab components."""

import asyncio
import json
from pathlib import Path
import tempfile

import pytest

from agent_lab.agent import Agent
from agent_lab.config import Config, load_config, save_config
from agent_lab.providers import LLMResponse, ToolCall
from agent_lab.tools import ReadFileTool, WriteFileTool, ListDirTool, ToolRegistry


# ============================================================================
# Config Tests
# ============================================================================


def test_config_defaults():
    """Test that config has sensible defaults."""
    cfg = Config()
    assert cfg.agents.defaults.model == "gpt-4o"
    assert cfg.agents.defaults.provider == "auto"
    assert cfg.agents.defaults.max_iterations == 20


def test_config_save_load():
    """Test config save and load."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"

        # Save
        cfg = Config()
        cfg.agents.defaults.model = "claude-opus"
        save_config(cfg, config_path)

        # Load
        loaded = load_config(config_path)
        assert loaded.agents.defaults.model == "claude-opus"


# ============================================================================
# Tool Tests
# ============================================================================


@pytest.mark.asyncio
async def test_read_file_tool():
    """Test read file tool."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        (workspace / "test.txt").write_text("Hello!")

        tool = ReadFileTool(workspace)
        result = await tool.execute(path="test.txt")

        assert result == "Hello!"


@pytest.mark.asyncio
async def test_write_file_tool():
    """Test write file tool."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        tool = WriteFileTool(workspace)

        result = await tool.execute(path="output.txt", content="Test")

        assert (workspace / "output.txt").read_text() == "Test"
        assert "File written" in result


@pytest.mark.asyncio
async def test_list_dir_tool():
    """Test list directory tool."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        (workspace / "file1.txt").write_text("a")
        (workspace / "file2.txt").write_text("b")
        (workspace / "subdir").mkdir()

        tool = ListDirTool(workspace)
        result = await tool.execute(path=".")

        assert "[FILE]" in result
        assert "[DIR]" in result
        assert "file1.txt" in result


# ============================================================================
# Tool Registry Tests
# ============================================================================


def test_tool_registry():
    """Test tool registry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        registry = ToolRegistry()
        registry.register(ReadFileTool(workspace))

        assert registry.has("read_file")
        assert len(registry) == 1
        assert registry.get("read_file") is not None
        assert "read_file" in registry.tool_names


@pytest.mark.asyncio
async def test_tool_registry_execute():
    """Test tool execution through registry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        (workspace / "test.txt").write_text("content")

        registry = ToolRegistry()
        registry.register(ReadFileTool(workspace))

        result = await registry.execute("read_file", {"path": "test.txt"})
        assert result == "content"


@pytest.mark.asyncio
async def test_tool_registry_error():
    """Test tool execution error handling."""
    registry = ToolRegistry()

    result = await registry.execute("nonexistent", {})
    assert "Error" in result
    assert "not found" in result


# ============================================================================
# Agent Tests
# ============================================================================


def test_agent_initialization():
    """Test agent initialization."""
    from unittest.mock import MagicMock

    provider = MagicMock()
    provider.default_model = "gpt-4"

    tools = ToolRegistry()
    agent = Agent(
        provider=provider,
        tools=tools,
        workspace=Path("/tmp"),
    )

    assert agent.model == "gpt-4"
    assert agent.max_iterations == 20


def test_agent_system_prompt():
    """Test system prompt generation."""
    from unittest.mock import MagicMock

    provider = MagicMock()
    provider.default_model = "gpt-4"

    tools = ToolRegistry()
    tools.register(ReadFileTool(Path("/tmp")))

    agent = Agent(provider=provider, tools=tools, workspace=Path("/tmp"))

    prompt = agent._build_system_prompt()
    assert "tools" in prompt.lower()
    assert "read_file" in prompt


def test_agent_custom_system_prompt():
    """Test custom system prompt."""
    from unittest.mock import MagicMock

    provider = MagicMock()
    provider.default_model = "gpt-4"

    agent = Agent(
        provider=provider,
        tools=ToolRegistry(),
        workspace=Path("/tmp"),
        system_prompt="Custom prompt",
    )

    prompt = agent._build_system_prompt()
    assert prompt == "Custom prompt"


# ============================================================================
# LLMResponse Tests
# ============================================================================


def test_llm_response():
    """Test LLM response creation."""
    response = LLMResponse(
        content="Hello",
        tool_calls=[
            ToolCall(id="1", name="read_file", arguments={"path": "test.txt"})
        ],
    )

    assert response.content == "Hello"
    assert response.has_tool_calls is True
    assert len(response.tool_calls) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
