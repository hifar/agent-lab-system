# Long-Term Memory

## Stable Facts

- User prefers concise, implementation-first responses.
- Primary project language is Python 3.12.
- Project is focused on agent core, tools, providers, and API compatibility.

## Reusable Decisions

- Keep Provider layer protocol-compatible with OpenAI and Anthropic.
- Preserve existing public APIs unless change is explicitly requested.
- Prefer deterministic non-streaming behavior by default.

## Important Constraints

- Avoid introducing unrelated framework complexity.
- Keep workspace operations scoped and explicit.
