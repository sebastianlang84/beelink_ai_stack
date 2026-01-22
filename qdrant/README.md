# qdrant — Vector DB (localhost-only)

Ziel: Qdrant läuft persistent und ist **nur lokal am Host** erreichbar:
- `http://127.0.0.1:6333`

Containers im `ai-stack` Docker-Netz können Qdrant unter:
- `http://qdrant:6333`

## Start

```bash
./scripts/create_ai_stack_network.sh
cd /home/wasti/ai_stack
docker compose --env-file .env --env-file .config.env --env-file qdrant/.config.env -f qdrant/docker-compose.yml up -d
```

## Check

```bash
curl -fsS http://127.0.0.1:6333/readyz
curl -fsS http://127.0.0.1:6333/ | head
```

## Persistenz / Backup
- Volume: `qdrant-data`

Runbook: `docs/runbook_backup_restore.md:1`

## Security
- Default ist localhost-only. Wenn du Qdrant jemals ins LAN/Tailnet exposen willst: `QDRANT_API_KEY` in `.env` setzen (siehe `.env.example`) und Doku/Risiko prüfen.
