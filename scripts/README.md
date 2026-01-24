# Scripts

## Docker (Debian 13)
- Install Docker Engine + Compose plugin (requires interactive `sudo`):
  - `./scripts/install_docker_debian13.sh`
- Optional: enable docker group for current user (root-equivalent power):
  - `./scripts/install_docker_debian13.sh --with-docker-group`

## Tailscale (Debian 13)
- Install Tailscale (requires interactive `sudo`):
  - `./scripts/install_tailscale_debian13.sh`

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

## Smoke Test (P0)
- Run an end-to-end-ish health/auth smoke test for Open WebUI + Transcript Miner tool:
  - `./scripts/smoke_test_ai_stack.sh --up --build`
  - Runbook: `docs/runbook_smoke_test.md:1`

## Transcript Miner Run Status
- Check a specific TM run (status, log tail, cookie availability):
  - `./scripts/check_tm_run_status.sh <run_id>`
  - Optional env: `TM_CONTAINER=tm`

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

## emb-bench (Terminal)
- Run `emb-bench/` via Docker (sets UID/GID to avoid root-owned outputs):
  - `./scripts/run_emb_bench.sh -- python -m emb_bench run --config config.local_only.yaml --phase local_vs_remote`
  - Remote (needs `OPENROUTER_API_KEY`): `./scripts/run_emb_bench.sh --env-file .env -- python -m emb_bench run --config config.example.yaml --phase mrl`
