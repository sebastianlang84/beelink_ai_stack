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
- Task: Disable Knowledge-ID mapping and verify sync + Knowledge files for `investing`.
- Issues/Bugs: Mapping can become stale and override name-based resolution.
- Resolution: Cleared `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON_PATH`, restarted `tm`, re-ran `sync/topic/investing` (success), and verified Knowledge files via OWUI API.
- Task: Future-proof Knowledge mapping state.
- Issues/Bugs: Stale local mapping files can reintroduce ID drift if mapping is re-enabled later.
- Resolution: Removed local `config/knowledge_ids.json` to avoid accidental stale mappings; rely on name-based resolution unless mapping is explicitly reintroduced.
- Task: Start a new Transcript Miner run for `investing`.
- Issues/Bugs: None (manual trigger).
- Resolution: Triggered `POST /runs/start` with `config_investing.yaml` (auto-sync enabled).
- Task: Enable immediate per-video sync to Open WebUI after summary completion.
- Issues/Bugs: Auto-sync only ran after the full run finished.
- Resolution: Added per-summary sync hook in the TranscriptMiner LLM runner, passed new env flags via tm compose, and enabled `OPEN_WEBUI_SYNC_ON_SUMMARY` in config.
- Task: Start a new `investing` run to validate per-summary sync.
- Issues/Bugs: None (manual trigger).
- Resolution: Triggered `POST /runs/start` with `config_investing.yaml` (run_id=e25029b7c98d401089ab4dc3f21912d8).
- Task: Ensure per-summary sync also triggers for existing summaries and streaming workers.
- Issues/Bugs: No per-summary sync logs; streaming path and “summary exists” short-circuit bypassed sync.
- Resolution: Added sync for valid-existing summaries and streaming LLM summary writes.
- Task: Restart tm to load per-summary sync changes and start a new investing run.
- Issues/Bugs: Previous run used old code without streaming/skip sync hooks.
- Resolution: Restarted `tm` and started `config_investing.yaml` (run_id=e66ad93907e24e338ffbea492cd120f7).
- Task: Fix crash in per-summary sync for existing summaries.
- Issues/Bugs: Run crashed with `UnboundLocalError` (fallback_title not initialized when summary already exists).
- Resolution: Initialized default metadata before early return and re-enabled per-summary sync path.
- Task: Start a new `investing` run after the per-summary sync fix.
- Issues/Bugs: None (manual trigger).
- Resolution: Triggered `POST /runs/start` with `config_investing.yaml` (run_id=9967297b4959455fb07b9536a8caed7d).
