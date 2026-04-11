# Memory System Optimization Summary (2026-04-12)

## Problem Statement

The agent-lab memory system had three key issues:

1. **Short-term memory cross-contamination**: `short_term.md` was global, causing different sessions' conversations to mix and pollute each other
2. **Conservative user/agent updates**: `should_update_*` gates required explicit LLM confirmation, causing important user/agent profile info to be missed
3. **Unclear memory layer roles**: Ambiguous distinction between what should go into long_term vs user vs agent_identity vs short_term

## Solution Architecture

### 1. Session-Local Short-Term Memory

**Before:**
```
memories/
  short_term.md (global, all sessions mixed)
```

**After:**
```
memories/short_term/
  short_term_default.md
  short_term_session_1.md
  short_term_session_2.md
  ...
```

**Key Changes:**
- Each session gets its own isolated `short_term_{session_id}.md` file
- Session separator in filename prevents data pollution
- Completely replaced on each organization pass (not merged with other sessions)

### 2. Aggressive User/Agent Identity Updates

**Before:** Only updated if LLM returned `should_update_user=true`
```json
{
  "should_update_user": false,  // ← Conservative gate
  "user_merged": "...",
  "should_update_agent_identity": false,
  "agent_identity_merged": "..."
}
```

**After:** Direct content merge without gates
```json
{
  "user_merged": "...",          // ← Always write if non-empty
  "agent_identity_merged": "..."  // ← Always write if non-empty
}
```

**Rationale:** 
- User profiles and agent capabilities should accumulate across sessions
- Continuous incremental learning is better than selective updates
- LLM returns the merged content directly (reduces decision points)

### 3. Clear Memory Layer Responsibilities

| Layer | Scope | Update Freq | Strategy |
|-------|-------|-------------|----------|
| **Short-Term** | Current session compression | Per-task | Complete replace (session-local) |
| **User** | User profile/preferences/goals/style | High (any relevance = update) | Incremental merge |
| **Agent Identity** | Agent capabilities/boundaries/patterns | High (any relevance = update) | Incremental merge |
| **Long-Term** | Cross-session rules/architecture/constants | Medium (only universal info) | Conservative update |

## Implementation Changes

### Modified Files

#### 1. `agent_lab/memory/__init__.py`
- Added `short_term_dir` as directory (vs single file)
- Added `_get_short_term_file(session_id)` method for session-local file lookup
- Added `session_id` parameter to `MemoryTask` dataclass
- Added `session_id` to `enqueue_organization_task()` signature
- Added `session_id` to `build_memory_context()` signature
- Added `session_id` to `_organize_memory_with_llm()` signature
- Removed `should_update_*` boolean gates; now unconditionally writes merged content
- Modified `_build_workspace_context()` to pass `session_id` down

#### 2. `agent_lab/agent/__init__.py`
- Added `session_id` parameter to `Agent.run()` method (default="default")
- Added `session_id` to `_build_system_prompt()` signature
- Added `session_id` to `_build_workspace_context()` signature
- Updated both `enqueue_organization_task()` calls to pass `session_id=session_id`

#### 3. `agent_lab/cli.py`
- Updated both `agent.run()` calls to pass `session_id=sess.session_id`
- Session object already has session_id, now properly propagated

#### 4. `agent_lab/api/server.py`
- Updated both `agent.run()` calls to pass `session_id=session_id`
- Already had session_id in context, now properly propagated through to Agent

#### 5. `config/memory_organizer_prompt.md`
- Completely replaced with new prompt explaining:
  - Three-layer memory responsibilities
  - session-local short_term behavior
  - Aggressive update strategy for user/agent
  - Conservative strategy for long_term
  - Removed `should_update_*` boolean responses
  - Removed instruction to merge short_term (now complete overwrite)

#### 6. `doc/QUICKSTART.md`
- Updated section 4.1 with comprehensive explanation
- Added table showing memory layer responsibilities
- Explained key improvements and isolation benefits

## Behavioral Changes

### Before
```
Session A chat → short_term contains info from sessions A, B, C (contaminated)
Session B chat → short_term updated but mixed with A, C data
User learns Python in session A → user.md not updated (should_update_user=false)
Agent discovers capability in session B → agent_identity.md fails to update
```

### After
```
Session A chat → short_term_A.md isolated, no cross-contamination
Session B chat → short_term_B.md completely independent  
User learns Python in session A → user.md immediately updated (no gates)
Agent discovers capability in session B → agent_identity.md immediately updated
Both can read shared user/agent knowledge from all sessions
```

## Testing & Verification

Created `test_memory_isolation.py` demonstrating:
- ✅ Session-local short_term files created per session
- ✅ Different sessions have completely separate short_term content
- ✅ User and agent identity files shared across sessions
- ✅ Memory context builds correctly with session-aware short_term lookup
- ✅ Task enqueuing captures session_id for proper processing

## Migration Path

**Backward Compatibility:** 
- Old `memories/short_term.md` files are ignored (new files in `memories/short_term/` directory)
- Default session_id="default" ensures existing code keeps working
- No database migrations required; automatic directory creation

**Cleanup (Optional):**
```bash
# Remove old global short_term file
rm -rf ~/.agent-lab/workspace/memories/short_term.md
# New session-local files in short_term/ directory will be created automatically
```

## Future Enhancements

1. **Configurable session isolation**: Allow user to choose between session-local and global short_term via config
2. **Memory analytics**: Track which fields in user/agent profiles are most frequently updated
3. **Conflict detection**: Warn if conflicting info in user profile from different sessions
4. **Selective long_term updates**: Let user explicitly mark certain facts as "promote to long_term"

## Configuration

Memory organizer behavior can be customized via:
- **File:** `~/.agent-lab/config/memory_organizer_prompt.md`
- **Fallback:** Built-in default if file missing
- **Customization:** Modify prompt to adjust update aggressiveness or memory layer roles

## Performance Impact

- **Session-local files**: Minor increase in I/O (multiple small files vs single file), negligible for typical workloads
- **Aggressive updates**: Slightly more LLM tokens used for merged content, but better quality upstream
- **No performance regression**: Same memory organization frequency, just better data quality

---

**Date:** 2026-04-12  
**Status:** ✅ Tested & Verified
