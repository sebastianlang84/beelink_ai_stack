# Documentation Index

Ziel: Jedes `.md` ist von mindestens einem anderen `.md` aus verlinkt, damit ein klares Doku-Netzwerk entsteht.

## Root-Dokumente
- `README.md` — Projektüberblick, Status, Quickstart
- `AGENTS.md` — Hierarchisch oberstes Dokument (Auftrag + Agent-Regeln)
- `TODO.md` — Gemeinsames Backlog (TranscriptMiner + ai_stack Ops), living
- `CHANGELOG.md` — Änderungen / Releases (living)
- `scripts/README.md` — Scripte (Install/Backup/Restore)

## Policies
- `docs/policy_secrets_environment_variables_ai_stack.md` — SSOT/Least-Privilege Policy für Secrets & Env Vars (Compose/systemd)
- `docs/policy_qdrant_indexing.md` — Was in Qdrant indexiert wird (Collections/IDs/Payload)
- `docs/runbook_secrets_env_files.md` — Schritt-für-Schritt: Env-Files unter `/etc/ai_stack/` anlegen und Stacks starten
- `docs/runbook_backup_restore.md` — Backups/Restore für Volumes + Output Root

## Services
- `mcp-transcript-miner/README.md` — **Transcript Miner** MCP Server (Configs/Runs/Outputs + Knowledge Indexing)
- `mcp-transcript-miner/PRD.md` — Produkt-/Scope-Definition (YouTube Transcript HTTP Tool)
- `open-webui/README.md` — Open WebUI (LLM UI) Betrieb
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
