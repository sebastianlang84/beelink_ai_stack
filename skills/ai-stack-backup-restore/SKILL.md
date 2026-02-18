---
name: ai-stack-backup-restore
description: Perform and document backup/restore for ai_stack (docker volumes and host bind-mounted data) using the repo scripts and runbooks. Use when preparing upgrades, migrating hosts, or recovering from data loss.
---

# Backup & restore

## Source of truth

- Runbook: `docs/runbooks/runbook_backup_restore.md:1`
- Scripts: `scripts/backup_*` and `scripts/restore_docker_volume.sh`

## Common backups (examples)

Docker volumes:
- Open WebUI data: `owui-data`
- Transcript Miner tool state: `tm-data`
- context6 data/cache: `context6-data`, `context6-cache`
- standalone qdrant: `qdrant-data`

Commands:
- Backup a volume: `./scripts/backup_docker_volume.sh <volume>`
- Restore (destructive): `./scripts/restore_docker_volume.sh <volume> <archive> --force`

Host paths (bind mounts) that should be backed up:
- `ai_stack_data/transcript-miner/output` (TranscriptMiner outputs)
