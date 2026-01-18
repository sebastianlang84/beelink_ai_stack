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
- Create shared external network for cross-stack communication (one-time):
  - `./scripts/create_ai_stack_network.sh`

## Compose Validation (Repo)
- Validate all stacks + localhost-only published ports:
  - `./scripts/compose_validate_all.sh`

## Secrets / Env (Host)
- Check `/etc/ai_stack/secrets.env` for required keys + safe validations (does not print secret values):
  - `./scripts/secrets_env_doctor.sh`
- Redact secrets from command output (safe sharing):
  - `./scripts/redact_secrets_output.sh`

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
  - Remote (needs `OPENROUTER_API_KEY`): `./scripts/run_emb_bench.sh --env-file /etc/ai_stack/secrets.env -- python -m emb_bench run --config config.example.yaml --phase mrl`
