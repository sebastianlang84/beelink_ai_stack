# qdrant — Vector DB (localhost-only)

Ziel: Qdrant läuft persistent und ist **nur lokal am Host** erreichbar:
- `http://127.0.0.1:6333`

Containers im `ai_stack` Docker-Netz können Qdrant unter:
- `http://qdrant:6333`

## Start

```bash
./scripts/create_ai_stack_network.sh
cd /home/wasti/ai_stack/qdrant
docker compose --env-file /etc/ai_stack/secrets.env up -d
```

## Check

```bash
curl -fsS http://127.0.0.1:6333/readyz
curl -fsS http://127.0.0.1:6333/ | head
```

## Persistenz / Backup
- Volume: `qdrant_qdrant_data`

Runbook: `docs/runbook_backup_restore.md:1`

## Security
- Default ist localhost-only. Wenn du Qdrant jemals ins LAN/Tailnet exposen willst: `QDRANT_API_KEY` setzen (siehe `.env.example`) und Doku/Risiko prüfen.
