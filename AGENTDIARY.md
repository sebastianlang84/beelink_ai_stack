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
- Task: Check run completion status and auto-sync progress for investing.
- Issues/Bugs: Auto-sync still running; manual sync attempt timed out.
- Resolution: Verified run finished (exit_code=0) and auto-sync started; will retry sync status later.
- Task: Check final run status + auto-sync outcome and document OWUI UI timestamp caveat.
- Issues/Bugs: Auto-sync failed due to OWUI duplicate-content rejection; UI “Updated” timestamp does not reflect file adds.
- Resolution: Captured auto-sync error details and documented UI timestamp caveat in smoke-test runbook.
- Task: Create prompt engineering handover report for META summary quality.
- Issues/Bugs: Per-video summary considered too short given transcript richness.
- Resolution: Assembled transcript, summary, and prompt into `enhance_prompt_engineering.md` with gap analysis and recommendations.
- Task: Capture expert prompt-engineering tips and switch workflow to investing_test for alpha.
- Issues/Bugs: Current summaries feel thin; repeated full investing runs are too heavy for alpha iteration.
- Resolution: Added expert tips to `docs/prompt_engineering_expert_notes.md` and documented investing_test focus in `TODO.md`.

## 2026-01-30
- Task: Document the investing_test alpha workflow and close the corresponding TODO.
- Issues/Bugs: Root README lacked a clear, repo-wide workflow for prompt-iteration runs.
- Resolution: Added an Investing-Test Workflow section to `README.md`, marked the TODO complete, and updated `CHANGELOG.md`.
- Task: Move the agent diary to the repo root.
- Issues/Bugs: Agent diary path needed to align with the new location and naming.
- Resolution: Copied the diary to `AGENTDIARY.md`, removed `docs/agent_diary.md`, and updated docs references.
- Task: Locate and clean up a possible typo file `AGENETDIARY.md`.
- Issues/Bugs: File not found in repo root or subdirectories.
- Resolution: Searched the workspace; no file to delete.
- Task: Create a Schema v3 prompt-engineering handover report (Meta summary).
- Issues/Bugs: Current summaries are rendered without quotes/evidence, making them hard to audit.
- Resolution: Added `enhance_prompt_engineering_v3.md` with a v3 direction (numbers completeness, verbatim vs normalized values, evidence/persistence improvements).

## 2026-01-31
- Aufgabe: Offene Punkte/Optionen zu Open WebUI Knowledge Auto-Create + Duplikate in TODO dokumentiert.
- Probleme/Bugs/Issues: Unklarheit zu unerwuenschten Knowledge-Collections (bitcoin/crypto) durch Auto-Create bei RAG-Anfragen.
- Loesung: TODO-Items mit Optionen (Request-Flag, Allowlist, Kombination) + Cleanup/Sync-Plan erfasst.

## 2026-01-31
- Aufgabe: TODO um Markdown-Linter-Wunsch ergänzt (Repo-wide, CI-Option).
- Probleme/Bugs/Issues: Keine.
- Loesung: Neuer TODO-Eintrag mit Optionen/Scope/CI-Hinweis.
