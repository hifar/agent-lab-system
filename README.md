# agent-lab 🤖

Minimal agent system for Python 3.12, optimized for simplicity and extensibility.

## Features

- **Agent Core**: Main loop with tool call support
- **LLM Providers**: OpenAI-compatible and Anthropic-compatible APIs
- **Tool System**: Easy-to-extend tool registration and execution
- **Configuration**: Pydantic-based config with environment variable support
- **Workspace Management**: Organized workspace with skills, memories, sessions
- **CLI**: Basic command-line interface

## Quick Start

### Installation

```bash
pip install -e .
```

### Initialize workspace

```bash
agent-lab init --workspace ~/.agent-lab/workspace
```

### Configure API keys

Edit `~/.agent-lab/config.json`:

```json
{
  "providers": {
    "openai": {
      "api_key": "sk-..."
    }
  }
}
```

### Chat with agent

```bash
agent-lab chat "What's in the current directory?"
```

## Architecture

```
agent-lab/
├── config/           # Configuration (schema, loader)
├── providers/        # LLM providers (base, OpenAI, Anthropic)
├── tools/           # Tool system (base, registry, built-ins)
├── agent/           # Agent main loop
├── workspace/       # Workspace management
├── skills/          # Skills loader
└── cli.py           # CLI entry point
```

## Supported Providers

- **OpenAI**: gpt-4o, gpt-4-turbo, etc.
- **Anthropic**: Claude 3.5 Sonnet, etc.
- **Custom**: Any OpenAI-compatible API

## Built-in Tools

- `read_file` - Read file contents
- `write_file` - Write content to file
- `list_dir` - List directory contents

## Environment Variables

- `AGENT_LAB_WORKSPACE` - Override workspace path
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key

## Development

```bash
pip install -e ".[dev]"
pytest
```
