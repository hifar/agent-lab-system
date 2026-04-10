# Runtime Notes

- Current mode: development
- API endpoint target: /v1/chat/completions
- Default behavior: tool-first validation for file operations
- Memory flow: keep last 4 user turns in active context; older history goes to memory service queue
- Memory service: use `agent-lab service run|once|start|stop` for background organization
- Last reviewed: 2026-04-10
