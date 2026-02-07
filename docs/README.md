# Documentation Index

Ziel: Jedes `.md` ist von mindestens einem anderen `.md` aus verlinkt, damit ein klares Doku-Netzwerk entsteht.

## Root-Dokumente
- `README.md` — Projektüberblick, Status, Quickstart
- `AGENTS.md` — Hierarchisch oberstes Dokument (Auftrag + Agent-Regeln)
- `TODO.md` — Gemeinsames Backlog (TranscriptMiner + ai_stack Ops), living
- `CHANGELOG.md` — Änderungen / Releases (living)
- `scripts/README.md` — Scripte (Install/Backup/Restore)
- `AGENTDIARY.md` — Agent-Tagebuch (Pflicht-Log)

## Policies
- `docs/policy_secrets_environment_variables_ai_stack.md` — SSOT/Least-Privilege Policy für Secrets & Env Vars (Compose/systemd)
- `docs/policy_qdrant_indexing.md` — Was in Qdrant indexiert wird (Collections/IDs/Payload)
- `docs/runbook_secrets_env_files.md` — Schritt-für-Schritt: `.env` (secrets) + `.config.env`/`<service>/.config.env` (config) anlegen und Stacks starten
- `docs/runbook_backup_restore.md` — Backups/Restore für Volumes + Output Root
- `docs/runbook_smoke_test.md` — Smoke Test (P0): Open WebUI + Transcript Miner Tool + Tool→OWUI Auth
- `docs/runbook_openwebui_reindex_knowledge.md` — Reindex nach Embedding‑Model‑Wechsel (Knowledge Collections Recovery)
- `docs/runbook_youtube_429_mitigation.md` — Runbook für YouTube Transcript 429 (Tests + Mitigation)
- `docs/runbook_codex_ssh_auth_dns_guard.md` — Codex VS Code Remote-SSH Auth-Guard (Tailscale DNS Override verhindern)

## Reports / Incidents
- `docs/report_youtube_ip_block.md` — YouTube Transcript Block (HTTP 429) Status & Optionen

## Notes / Research
- `docs/notes_openclaw_install_sources.md` — OpenClaw install commands + Telegram setup pointers (sources)
- `docs/notes_access_tailscale_vs_lan_owui_openclaw.md` — OWUI/OpenClaw access topology: Tailscale vs LAN + /owui,/openclaw collisions

## Services
- `mcp-transcript-miner/README.md` — **Transcript Miner** MCP Server (Configs/Runs/Outputs + Knowledge Indexing)
- `mcp-transcript-miner/PRD.md` — Produkt-/Scope-Definition (YouTube Transcript HTTP Tool)
- `mcp-sec-edgar/README.md` — SEC EDGAR MCP Server (Streamable HTTP)
- `open-webui/README.md` — Open WebUI (LLM UI) Betrieb
- `openclaw/README.md` — OpenClaw Gateway (host-native Betrieb)
- `openclaw/OPERATIONS.md` — OpenClaw Operations/Recovery (Supervisor/Cron + Telegram Pairing)
- `emb-bench/README.md` — Embedding Benchmark Suite (MRL + Local vs OpenRouter)
- `mcp-context6/README.md` — context6 MCP Server (PoC, MCP Streamable HTTP)
- `qdrant/README.md` — Qdrant Vector DB (localhost-only)

## Tool Imports (Open WebUI)
- `open-webui/tool-imports/tool_import_context7.json` — Context7 (MCP)
- `open-webui/tool-imports/tool_import_transcript_miner_mcp.json` — Transcript Miner (MCP)
- `open-webui/tool-imports/tool_import_context6.json` — context6 (MCP)
- Optional: Tool Imports automatisch per Admin API setzen: `scripts/openwebui_apply_tool_imports.sh`

## Workflows (Zielbilder)
- `docs/workflow_openwebui_hole_neueste_videos.md` — Open WebUI Tool-Workflow: „hole die neuesten videos“ → TranscriptMiner → Knowledge
- `docs/prd-tool-owui-transcript-miner-sync.md` — PRD v0: TranscriptMiner Sync Tool (Runs aus Open WebUI starten + Summaries in Knowledge indexieren)

## PRDs (Research / Benchmarks)
- `docs/prd_embedding_benchmark_suite_mrl_local_vs_openrouter_qwen3.md` — Embedding Benchmark Suite (MRL/Truncation + Local CPU vs OpenRouter Qwen3)
- `docs/prd_context6_poc_working_draft.md` — context6 PRD (PoC/Prototype, MCP-first)
