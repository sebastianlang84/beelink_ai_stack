# Runbook — Smoke Test (P0) für ai_stack

Ziel: Ein reproduzierbarer Minimal-Check, dass **Open WebUI** + das **Transcript Miner Tool** laufen, lokal erreichbar sind und die Tool→Open-WebUI-API Auth funktioniert.

Hinweis: Dieser Smoke-Test prüft **nicht** die inhaltliche Qualität der Summaries. Dafür gibt es am Ende einen optionalen End-to-End Test (1 Topic, 2–3 Videos).

## 0) Voraussetzungen

- Docker + Compose Plugin installiert
- Tailscale optional (für VPN-only Zugriff über HTTPS)
- Secrets-SSOT vorhanden: `/etc/ai-stack/secrets.env` (keine Werte im Repo)

## 1) Secrets validieren (ohne Leaks)

```bash
./scripts/secrets_env_doctor.sh /etc/ai-stack/secrets.env
```

Wenn du Output teilen musst:
```bash
docker compose --env-file /etc/ai-stack/secrets.env config | ./scripts/redact_secrets_output.sh
```

## 2) Compose-Stacks starten

Shared Docker-Netz (einmalig):
```bash
./scripts/provision_ai_stack_docker_objects.sh
```

Open WebUI:
```bash
cd /home/wasti/ai_stack/open-webui
docker compose --env-file /etc/ai-stack/secrets.env up -d
```

Transcript Miner Tool:
```bash
cd /home/wasti/ai_stack/mcp-transcript-miner
docker compose --env-file /etc/ai-stack/secrets.env up -d --build
```

## 3) Smoke-Test Script (empfohlen)

```bash
./scripts/smoke_test_ai_stack.sh --env-file /etc/ai-stack/secrets.env --up --build
```

Erwartung:
- Open WebUI: `http://127.0.0.1:3000/` → `200`
- Tool: `/healthz` ok
- Tool → Open WebUI API: `/api/v1/files/` → `200` (erfordert gültiges `OPEN_WEBUI_API_KEY`)

## 4) Tailscale Serve (VPN-only Zugriff über HTTPS)

Wenn du Open WebUI im Tailnet bereitstellen willst:
```bash
sudo tailscale serve --bg --https=443 http://127.0.0.1:3000
sudo tailscale serve status
```

Erwartung: Zugriff im VPN über `https://<node>.<tailnet>.ts.net/` lädt Open WebUI.

## 5) Optional: End-to-End (1 Topic, 2–3 Videos)

Ziel: Ein echter Indexing-Durchlauf in eine Knowledge Collection.

1. In Open WebUI eine Knowledge Collection anlegen und deren ID notieren.
2. In `/etc/ai-stack/secrets.env` setzen (Beispiel ohne Werte):
   - `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON='{"stocks_crypto":"<knowledge_id>"}'`
3. Mit dem Tool einen Topic-Sync triggern:
   - In Open WebUI als External Tool „Transcript Miner“ verwenden: `sync.topic` mit `topic=stocks_crypto`
4. Prüfen:
   - Knowledge Collection enthält neue Summary-Dokumente
   - Chat-Retrieval mit der Collection liefert passende Zitate/Referenzen
