# Agent Diary

This diary tracks tasks, issues/bugs encountered, and how they were resolved.

## 2026-01-29
- Task: Add mandatory agent diary requirement and commit rules.
- Issues/Bugs: No agent diary existed and no explicit agent-level policy about diary + commit steps.
- Resolution: Moved mandatory diary + commit rules into `AGENTS.md`, removed `AGENT.md`, and updated docs references.
- Task: Fix missing `investing` Knowledge Collection by refreshing the Open WebUI Knowledge ID mapping.
- Issues/Bugs: `sync/topic/investing` targeted a stale Knowledge ID and failed to add files (HTTP 400 not found).
- Resolution: Created the `investing` collection in Open WebUI, updated `config/knowledge_ids.json`, and restarted the tm container to reload the mapping.
- Task: Make Knowledge-ID mapping resilient and re-run `investing` sync.
- Issues/Bugs: Stale Knowledge-ID mapping can break sync even when the collection exists by name.
- Resolution: Added a mapped-ID existence check with fallback to name lookup, rebuilt/restarted `tm`, and re-ran `sync/topic/investing` (success).
