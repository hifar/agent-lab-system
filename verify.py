"""Quick verification script for agent-lab."""

import asyncio
from pathlib import Path

from agent_lab.agent import Agent
from agent_lab.config import Config
from agent_lab.providers import create_provider
from agent_lab.tools import ReadFileTool, WriteFileTool, ListDirTool, ToolRegistry


async def main():
    """Run a quick verification test."""
    print("🤖 Agent-Lab Quick Verification\n")

    # Setup
    config = Config()
    workspace = Path("/tmp/agent-lab-test")
    workspace.mkdir(exist_ok=True)

    # Create a test file
    (workspace / "test.txt").write_text("Hello, Agent!")

    # Create provider and tools
    print("1. Testing configuration...")
    print(f"   Model: {config.agents.defaults.model}")
    print(f"   Provider: {config.agents.defaults.provider}")
    print(f"   Workspace: {workspace}")

    print("\n2. Testing tools...")
    tools = ToolRegistry()
    tools.register(ReadFileTool(workspace))
    tools.register(WriteFileTool(workspace))
    tools.register(ListDirTool(workspace))
    print(f"   Registered tools: {tools.tool_names}")

    print("\n3. Testing file tools...")
    # Test read
    result = await tools.execute("read_file", {"path": "test.txt"})
    print(f"   Read test.txt: {result[:30]}...")

    # Test write
    result = await tools.execute("write_file", {"path": "output.txt", "content": "Test output"})
    print(f"   Write output.txt: {result}")

    # Test list
    result = await tools.execute("list_dir", {"path": "."})
    print(f"   List directory:\n{result}")

    print("\n4. Testing agent setup...")
    print("   Note: Agent requires valid API credentials to chat.")
    print("   Configure OPENAI_API_KEY or ANTHROPIC_API_KEY to test chat.\n")

    print("✅ All basic checks passed!")


if __name__ == "__main__":
    asyncio.run(main())
