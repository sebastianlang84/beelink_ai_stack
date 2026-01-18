# Runbook — Backup & Restore (ai_stack)

Ziel: Persistente Daten zuverlässig sichern und wiederherstellen können, ohne Secrets ins Repo zu committen.

Hinweis: Backups enthalten die Rohdaten (inkl. Tokens/DBs/Uploads). Behandle Backups wie Secrets.

## Was muss gesichert werden?

### 1) Open WebUI Daten

- Docker Volume: `open-webui_open_webui_data`
- Enthält u. a. App-Daten unter `/app/backend/data`

### 2) Transcript Miner Tool State

- Docker Volume: `tool-transcript-miner_tool_transcript_miner_data`
- Enthält u. a. SQLite für Indexing/Idempotenz + Config-Backups (`/data/...`)

### 3) TranscriptMiner Output Root (Host-Pfad, Bind-Mount)

- Host-Pfad (Default): `/home/wasti/ai_stack_data/transcript-miner/output`
- Alternative Zielpfade möglich (siehe `mcp-transcript-miner/docker-compose.yml`)

### 4) context6 (MCP) Daten (PoC)

- Docker Volume: `mcp_context6_context6_data` (SQLite + Artefakte)
- context6 Cache: `mcp_context6_context6_cache`

### 5) Qdrant Vector DB (Standalone)

- Docker Volume: `qdrant_qdrant_data`

## Backup-Verzeichnis (Host)

Empfehlung: `/srv/ai_stack/backups/` (owner: `root` oder `wasti`, aber nicht world-readable).

Beispiel:
```bash
sudo mkdir -p /srv/ai_stack/backups
sudo chown wasti:wasti /srv/ai_stack/backups
sudo chmod 700 /srv/ai_stack/backups
```

## Backup erstellen

### Docker Volume Backups

```bash
./scripts/backup_docker_volume.sh open-webui_open_webui_data /srv/ai_stack/backups
./scripts/backup_docker_volume.sh tool-transcript-miner_tool_transcript_miner_data /srv/ai_stack/backups
```

### Output Root (Bind-Mount) Backup

```bash
./scripts/backup_path.sh /home/wasti/ai_stack_data/transcript-miner/output /srv/ai_stack/backups
```

## Regelmäßige Backups (systemd Timer)

Im Repo liegen Template-Files unter `scripts/systemd/`:
- `scripts/systemd/ai_stack_backup.service`
- `scripts/systemd/ai_stack_backup.timer`

Install (Host):
```bash
sudo cp /home/wasti/ai_stack/scripts/systemd/ai_stack_backup.service /etc/systemd/system/
sudo cp /home/wasti/ai_stack/scripts/systemd/ai_stack_backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ai_stack_backup.timer
systemctl status ai_stack_backup.timer
```

Manuell triggern:
```bash
sudo systemctl start ai_stack_backup.service
```

Konfiguration (Defaults im Service-File):
- `BACKUP_DIR=/srv/ai_stack/backups`
- `OUTPUT_ROOT=/home/wasti/ai_stack_data/transcript-miner/output`
- `RETENTION_DAYS=14`

## Restore (Achtung: destruktiv)

Empfohlenes Vorgehen:
1) Stacks stoppen (damit nichts während des Restores schreibt)
2) Restore durchführen
3) Stacks starten

Stop:
```bash
cd /home/wasti/ai_stack/open-webui && docker compose --env-file /etc/ai_stack/secrets.env down
cd /home/wasti/ai_stack/mcp-transcript-miner && docker compose --env-file /etc/ai_stack/secrets.env down
```

Restore Volume (Beispiel):
```bash
./scripts/restore_docker_volume.sh open-webui_open_webui_data /srv/ai_stack/backups/open-webui_open_webui_data__<timestamp>.tar.gz --force
./scripts/restore_docker_volume.sh tool-transcript-miner_tool_transcript_miner_data /srv/ai_stack/backups/tool-transcript-miner_tool_transcript_miner_data__<timestamp>.tar.gz --force
```

Start:
```bash
cd /home/wasti/ai_stack/open-webui && docker compose --env-file /etc/ai_stack/secrets.env up -d
cd /home/wasti/ai_stack/mcp-transcript-miner && docker compose --env-file /etc/ai_stack/secrets.env up -d --build
```

## Rotation / Sicherheit

- Wenn ein `OPEN_WEBUI_API_KEY` jemals im Klartext im Repo/Chat/Logs war: in Open WebUI rotieren und `/etc/ai_stack/secrets.env` aktualisieren.
- Backups nicht unverschlüsselt extern speichern; mindestens Zugriff stark einschränken.
