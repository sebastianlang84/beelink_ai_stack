# Scripts

## Docker (Debian 13)
- Install Docker Engine + Compose plugin (requires interactive `sudo`):
  - `./scripts/install_docker_debian13.sh`
- Optional: enable docker group for current user (root-equivalent power):
  - `./scripts/install_docker_debian13.sh --with-docker-group`

## Tailscale (Debian 13)
- Install Tailscale (requires interactive `sudo`):
  - `./scripts/install_tailscale_debian13.sh`

## Codex SSH Auth DNS Guard
- DNS/Auth check for Codex OAuth endpoint (`auth.openai.com`):
  - `./scripts/check_codex_auth_dns.sh`
- Auto-remediation (forces `tailscale --accept-dns=false` + post-check):
  - `./scripts/remediate_codex_auth_dns.sh --reason manual`
- Install persistent user-cron guard (`@reboot` + periodic check every 10 min):
  - `./scripts/install_codex_auth_dns_guard_cron.sh`
- Default log file:
  - `${XDG_STATE_HOME:-$HOME/.local/state}/ai_stack/codex-auth-dns-guard.log`

## OpenClaw Gateway (Host-native)
- Ensure the gateway is running (idempotent):
  - `./scripts/openclaw_gateway_supervise.sh ensure`
- Check status:
  - `./scripts/openclaw_gateway_supervise.sh status`
- Install persistent user-cron (`@reboot` + periodic ensure every 5 min):
  - `./scripts/install_openclaw_gateway_cron.sh`
- Uninstall the user-cron block (marked section only):
  - `./scripts/uninstall_openclaw_gateway_cron.sh`
- Default logs:
  - `${XDG_STATE_HOME:-$HOME/.local/state}/ai_stack/openclaw/openclaw-gateway.log`
  - `${XDG_STATE_HOME:-$HOME/.local/state}/ai_stack/openclaw/openclaw-gateway-cron.log`

## Docker Networking
- Provision shared network + volumes (SSOT naming, one-time):
  - `./scripts/provision_ai_stack_docker_objects.sh`
- Legacy: create only the shared external network:
  - `./scripts/create_ai_stack_network.sh`

## Compose Validation (Repo)
- Validate all stacks + localhost-only published ports:
  - `./scripts/compose_validate_all.sh`

## Secrets / Env (Host)
- Check repo-local env layout (`.env` + `.config.env` + `<service>/.config.env`) for required keys + guardrails (does not print secret values):
  - `./scripts/env_doctor.sh`
- Redact secrets from command output (safe sharing):
  - `./scripts/redact_secrets_output.sh`

## Tavily (Host)
- Run a Tavily web search using `TAVILY_API_KEY` from the environment or repo-local `.env` (gitignored):
  - `./scripts/tavily_search.sh "openclaw gateway trustedProxies"`

## Smoke Test (P0)
- Run an end-to-end-ish health/auth smoke test for Open WebUI + Transcript Miner tool:
  - `./scripts/smoke_test_ai_stack.sh --up --build`
  - Runbook: `docs/runbook_smoke_test.md:1`

## Open WebUI 502 Auto-Recovery (Tailscale Serve Upstream)
- Status only (no changes):
  - `./scripts/ensure-owui-up.sh status`
- Idempotent check + auto-recover (`docker compose up -d owui` when degraded):
  - `./scripts/ensure-owui-up.sh ensure`
- Force recovery:
  - `./scripts/ensure-owui-up.sh recover`
- systemd templates:
  - `scripts/systemd/ai-stack-owui-ensure.service`
  - `scripts/systemd/ai-stack-owui-ensure.timer`
- Runbook:
  - `docs/runbook-owui-502-autorecover.md:1`

## Gemini CLI Summary POC (headless)
- Quick test (default fixture prompt + transcript):
  - `./scripts/run-gemini-cli-summary-poc.sh`
- With custom input:
  - `./scripts/run-gemini-cli-summary-poc.sh --transcript-file <path> --model gemini-3-flash-preview`
- Model policy:
  - Pro-Modelle sind im Script geblockt (`--model ...pro...` wird abgewiesen).
  - Thinking wird per Prompt-Policy deaktiviert (kein separater CLI-Flag).
- Auth requirement:
  - bevorzugt Gemini auth in `~/.gemini/settings.json` mit `preview=true` fuer `gemini-3-flash-preview`
  - `GEMINI_API_KEY` nur als Fallback
- Runbook:
  - `docs/runbook-gemini-cli-summary-poc.md:1`

## Open WebUI RAG Guard (Investing)
- Apply stricter day-sensitive retrieval defaults in OWUI config (`webui.db`) and restart `owui`:
  - `./scripts/openwebui_apply_investing_rag_guard.sh`
- Sets:
  - `rag.relevance_threshold=0.4`
  - `rag.top_k=15`
  - `rag.top_k_reranker=5`
  - Strict `Same-day sufficiency gate` in `rag.template` for "heute/des Tages/latest" queries.

## Transcript Miner Run Status
- Check a specific TM run (status, log tail, cookie availability):
  - `./scripts/check_tm_run_status.sh <run_id>`
  - Optional env: `TM_CONTAINER=tm`

## Investing Lifecycle Sync
- Reconcile `investing_new` + `investing_archive` from source topic (`investing`) with recency rules (add/move/remove, Knowledge-IDs bleiben stabil):
  - `./scripts/sync-investing-lifecycle.sh`

## Investing Lifecycle Maintenance (ohne Downloads)
- Run cleanup/rotation + guard check (default):
  - `./scripts/maintain-investing-lifecycle.sh ensure`
- `ensure` fuehrt zusaetzlich einen lokalen Orphan-Prune aus (stale hot summaries ohne aktuellen Index-Eintrag -> `cold/`).
- Nur lifecycle sync:
  - `./scripts/maintain-investing-lifecycle.sh sync`
- Nur guard check:
  - `./scripts/maintain-investing-lifecycle.sh check`
- Dry-run (no mutations) + guard:
  - `./scripts/maintain-investing-lifecycle.sh dry-run`
- Guard direkt:
  - `./scripts/check-hot-summaries-freshness.sh`
- systemd templates:
  - `scripts/systemd/ai-stack-tm-investing-maintenance.service`
  - `scripts/systemd/ai-stack-tm-investing-maintenance.timer`
- Runbook:
  - `docs/runbook-tm-lifecycle-maintenance.md:1`

## Provision / Migration (Naming SSOT)
- Provision shared Docker objects (network + named volumes):
  - `./scripts/provision_ai_stack_docker_objects.sh`
- Migrate legacy Docker object names to SSOT:
  - `./scripts/migrate_ai_stack_naming_v1.sh --cleanup-old`

## Backup / Restore
- Backup Docker volumes (Open WebUI data, Tool state) + host output directories:
  - `./scripts/backup_docker_volume.sh <volume>`
  - `./scripts/backup_path.sh <path>`
- Restore Docker volumes (destructive; requires `--force`):
  - `./scripts/restore_docker_volume.sh <volume> <archive> --force`

## Backup Scheduling (systemd)
- One-shot backup for all critical data + retention cleanup:
  - `./scripts/backup_all.sh` (configurable via env vars `BACKUP_DIR`, `OUTPUT_ROOT`, `RETENTION_DAYS`)
- systemd templates:
  - `scripts/systemd/ai_stack_backup.service`
  - `scripts/systemd/ai_stack_backup.timer`

## Transcript Miner Scheduling (systemd)
- One-shot run (investing):
  - `./scripts/run-tm-investing.sh`
- The run script waits for completion and triggers `sync.topic` for `investing` (global lifecycle routing -> `investing_new` + `investing_archive`).
- One-shot run (Company Dossier Agent):
  - `./scripts/run-tm-investing-companies.sh`
- The company script uses `config_investing_companies.yaml` and syncs topic `company_dossiers`.
- Cost control kill-switch (no sudo; makes scheduled scripts exit immediately):
  - Disable: `touch "${XDG_STATE_HOME:-$HOME/.local/state}/ai_stack/schedulers.disabled"`
  - Enable: `rm -f "${XDG_STATE_HOME:-$HOME/.local/state}/ai_stack/schedulers.disabled"`
- systemd templates (investing every 3h):
  - `scripts/systemd/ai-stack-tm-investing.service`
  - `scripts/systemd/ai-stack-tm-investing.timer`
- systemd templates (company dossiers daily):
  - `scripts/systemd/ai-stack-tm-company-dossiers.service`
  - `scripts/systemd/ai-stack-tm-company-dossiers.timer`
- systemd templates (investing maintenance daily, download-unabhaengig):
  - `scripts/systemd/ai-stack-tm-investing-maintenance.service`
  - `scripts/systemd/ai-stack-tm-investing-maintenance.timer`

## Maintenance / Cleanup
- Purge a test topic (transcripts, summaries, reports, history + Open WebUI Knowledge):
  - `OPEN_WEBUI_API_KEY=... ./scripts/purge_topic_data.sh investing_test --force`

## emb-bench (Terminal)
- Run `emb-bench/` via Docker (sets UID/GID to avoid root-owned outputs):
  - `./scripts/run_emb_bench.sh -- python -m emb_bench run --config config.local_only.yaml --phase local_vs_remote`
  - Remote (needs `OPENROUTER_API_KEY`): `./scripts/run_emb_bench.sh --env-file .env -- python -m emb_bench run --config config.example.yaml --phase mrl`
