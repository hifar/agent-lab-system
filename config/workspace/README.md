# Workspace Example

This folder is a reference workspace layout.

Copy this folder to your actual workspace path, e.g. `~/.agent-lab/workspace`, then customize values.

The agent can read:

- `prompts/agent.md`
- `identity/agent_identity.json`
- `profile/user_profile.json`
- `memories/agent_identity.md`
- `memories/user.md`
- `memories/long_term.md`
- `memories/short_term.md`
- `state/runtime_notes.md`
- `state/policies.md`
- `skills/*/SKILL.md`
- `knowledge/*.md` (metadata-first progressive disclosure)

## Memory Notes

- Memory is injected into model context as system reference materials.
- Update policy is merge-rewrite, not append.
- Typical runtime flow keeps only last 4 user turns in active context and organizes older turns asynchronously.
