# agent-lab 🤖

Minimal agent system for Python 3.12, optimized for simplicity and extensibility.

**Status**: ✅ Production Ready (MVP) | [See Complete Summary](FINAL_SUMMARY.md)

## Recent Updates (2026-04-07)

- Added dedicated memory module for layered memory management and background organization.
- Added CLI service command for memory worker lifecycle: `run`, `once`, `start`, `stop`.
- Added 3-layer memory policy with merge-rewrite updates (not append).
- Added robust memory output parsing (supports fenced JSON and safe fallback).
- Added full LLM request/response logging (including memory service) into workspace `log/`.

## Recent Updates (2026-04-05)

- Added OpenAI-compatible API server and CLI command `agent-lab api`.
- Added think/streaming switches end-to-end (Config, CLI, API, Agent, Provider).
- Added workspace semantic context loading from prompts, identity, profile, memories, state, and skills.
- Added config/workspace templates under `config/` for fast bootstrap.

## Quick Links

- 🚀 [Quick Start](QUICKSTART.md) - Get started in 5 minutes
- 📖 [Architecture](ARCHITECTURE.md) - System design and concepts
- 📋 [Structure](PROJECT_STRUCTURE.md) - Complete file reference
- ✅ [Final Summary](FINAL_SUMMARY.md) - Complete project overview

## Features

- **Agent Core**: Main loop with tool call support
- **LLM Providers**: OpenAI-compatible and Anthropic-compatible APIs
- **Tool System**: Easy-to-extend tool registration and execution
- **Configuration**: Pydantic-based config with environment variable support
- **Workspace Management**: Organized workspace with skills, memories, sessions
- **CLI**: Command-line interface for all operations

## Quick Start

### Installation

```bash
pip install -e .
```

### Initialize workspace

```bash
agent-lab init
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

## Commands

```bash
agent-lab init                    # Initialize
agent-lab config show             # Show configuration
agent-lab chat "message"          # Single chat
agent-lab chat -s session_id      # Multi-turn chat
agent-lab tools-list              # List tools
agent-lab skills-list             # List skills
agent-lab service once            # Process memory tasks once
agent-lab service start           # Start memory service in background
```

## Environment Variables

- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key
- `AGENT_LAB_WORKSPACE` - Override workspace path

## Project Stats

- **Code**: ~2500 lines (15 modules)
- **Docs**: ~3000 lines (6 documents)
- **Tests**: 10+ cases
- **Python**: 3.12
- **Status**: ✅ Production Ready

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Next Steps

1. Read [QUICKSTART.md](QUICKSTART.md) for detailed guide
2. Check [ARCHITECTURE.md](ARCHITECTURE.md) to understand the design
3. See [FINAL_SUMMARY.md](FINAL_SUMMARY.md) for complete project overview
4. Add custom tools to extend functionality
5. Create skills in `~/.agent-lab/workspace/skills/`

## License

MIT
