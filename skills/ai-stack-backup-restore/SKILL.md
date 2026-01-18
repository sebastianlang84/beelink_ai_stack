---
name: ai-stack-backup-restore
description: Perform and document backup/restore for ai_stack (docker volumes and host bind-mounted data) using the repo scripts and runbooks. Use when preparing upgrades, migrating hosts, or recovering from data loss.
---

# Backup & restore

## Source of truth

- Runbook: `docs/runbook_backup_restore.md:1`
- Scripts: `scripts/backup_*` and `scripts/restore_docker_volume.sh`

## Common backups (examples)

Docker volumes:
- Open WebUI data: `open-webui_open_webui_data`
- Transcript Miner tool state: `tool-transcript-miner_tool_transcript_miner_data`
- context6 data/cache: `mcp_context6_context6_data`, `mcp_context6_context6_cache`
- standalone qdrant: `qdrant_qdrant_data`

Commands:
- Backup a volume: `./scripts/backup_docker_volume.sh <volume>`
- Restore (destructive): `./scripts/restore_docker_volume.sh <volume> <archive> --force`

Host paths (bind mounts) that should be backed up:
- `ai_stack_data/transcript-miner/output` (TranscriptMiner outputs)
