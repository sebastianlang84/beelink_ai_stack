# Runbook — Backup & Restore (ai_stack)

Ziel: Persistente Daten zuverlässig sichern und wiederherstellen können, ohne Secrets ins Repo zu committen.

Hinweis: Backups enthalten die Rohdaten (inkl. Tokens/DBs/Uploads). Behandle Backups wie Secrets.

## Was muss gesichert werden?

### 1) Open WebUI Daten

- Docker Volume: `owui-data`
- Enthält u. a. App-Daten unter `/app/backend/data`

### 2) Transcript Miner Tool State

- Docker Volume: `tm-data`
- Enthält u. a. SQLite für Indexing/Idempotenz + Config-Backups (`/data/...`)

### 3) TranscriptMiner Output Root (Host-Pfad, Bind-Mount)

- Host-Pfad (Default): `/home/wasti/ai_stack_data/transcript-miner/output`
- Alternative Zielpfade möglich (siehe `mcp-transcript-miner/docker-compose.yml`)

### 4) context6 (MCP) Daten (PoC)

- Docker Volume: `context6-data` (SQLite + Artefakte)
- context6 Cache: `context6-cache`

### 5) Qdrant Vector DB (Standalone)

- Docker Volume: `qdrant-data`

## Backup-Verzeichnis (Host)

Empfehlung: `/srv/ai-stack/backups/` (owner: `root` oder `wasti`, aber nicht world-readable).

Beispiel:
```bash
sudo mkdir -p /srv/ai-stack/backups
sudo chown wasti:wasti /srv/ai-stack/backups
sudo chmod 700 /srv/ai-stack/backups
```

## Backup erstellen

### Docker Volume Backups

```bash
./scripts/backup_docker_volume.sh owui-data /srv/ai-stack/backups
./scripts/backup_docker_volume.sh tm-data /srv/ai-stack/backups
```

Hinweis: Volume-Backups laufen über Docker und werden typischerweise als `root:root` geschrieben.
Das ist erwartetes Verhalten. Falls du einheitliche Ownership willst, kannst du die Dateien nachträglich
auf `wasti:wasti` umstellen (z. B. `sudo chown wasti:wasti /srv/ai-stack/backups/*.tar.gz`).

### Output Root (Bind-Mount) Backup

```bash
./scripts/backup_path.sh /home/wasti/ai_stack_data/transcript-miner/output /srv/ai-stack/backups
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
- `BACKUP_DIR=/srv/ai-stack/backups`
- `OUTPUT_ROOT=/home/wasti/ai_stack_data/transcript-miner/output`
- `RETENTION_DAYS=14`

## Restore (Achtung: destruktiv)

Empfohlenes Vorgehen:
1) Stacks stoppen (damit nichts während des Restores schreibt)
2) Restore durchführen
3) Stacks starten

Stop:
```bash
cd /home/wasti/ai_stack && docker compose --env-file .env --env-file .config.env --env-file open-webui/.config.env -f open-webui/docker-compose.yml down
cd /home/wasti/ai_stack && docker compose --env-file .env --env-file .config.env --env-file mcp-transcript-miner/.config.env -f mcp-transcript-miner/docker-compose.yml down
```

Restore Volume (Beispiel):
```bash
./scripts/restore_docker_volume.sh owui-data /srv/ai-stack/backups/owui-data__<timestamp>.tar.gz --force
./scripts/restore_docker_volume.sh tm-data /srv/ai-stack/backups/tm-data__<timestamp>.tar.gz --force
```

Start:
```bash
cd /home/wasti/ai_stack && docker compose --env-file .env --env-file .config.env --env-file open-webui/.config.env -f open-webui/docker-compose.yml up -d
cd /home/wasti/ai_stack && docker compose --env-file .env --env-file .config.env --env-file mcp-transcript-miner/.config.env -f mcp-transcript-miner/docker-compose.yml up -d --build
```

## Rotation / Sicherheit

- Wenn ein `OPEN_WEBUI_API_KEY` jemals im Klartext im Repo/Chat/Logs war: in Open WebUI rotieren und `.env` aktualisieren.
- Backups nicht unverschlüsselt extern speichern; mindestens Zugriff stark einschränken.
