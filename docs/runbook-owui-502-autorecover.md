# Runbook — OWUI 502 Auto-Recovery (Tailscale Serve Upstream)

Ziel: Wenn `https://<owui>.ts.net/` wegen gestopptem/ungesundem `owui` auf `502` faellt, soll OWUI automatisch wieder starten.

Umsetzung:
- Script: `scripts/ensure-owui-up.sh`
- systemd Templates:
  - `scripts/systemd/ai-stack-owui-ensure.service`
  - `scripts/systemd/ai-stack-owui-ensure.timer`

## 1) Voraussetzungen

- Docker Engine + Compose Plugin laufen.
- Open WebUI Stack ist im Repo vorhanden (`open-webui/docker-compose.yml`).
- Tailscale Serve zeigt auf `http://127.0.0.1:3000`.

## 2) Manueller Check/Recovery

Status (nur lesen):
```bash
./scripts/ensure-owui-up.sh status
```

Idempotenter Check mit Auto-Recovery:
```bash
./scripts/ensure-owui-up.sh ensure
```

Erzwinge Recovery:
```bash
./scripts/ensure-owui-up.sh recover
```

## 3) systemd Timer installieren

```bash
sudo cp /home/wasti/ai_stack/scripts/systemd/ai-stack-owui-ensure.service /etc/systemd/system/
sudo cp /home/wasti/ai_stack/scripts/systemd/ai-stack-owui-ensure.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ai-stack-owui-ensure.timer
```

Status:
```bash
systemctl status ai-stack-owui-ensure.timer
systemctl list-timers --all | rg 'ai-stack-owui-ensure'
```

## 4) Verifikation (DoD)

1. `owui` absichtlich stoppen:
```bash
docker stop owui
```
2. Entweder auf den Timer warten (max. ~2 Minuten) oder manuell triggern:
```bash
sudo systemctl start ai-stack-owui-ensure.service
```
3. Pruefen:
```bash
docker ps --format '{{.Names}} {{.Status}}' | rg '^owui '
curl -I http://127.0.0.1:3000/
curl -I https://<node>.<tailnet>.ts.net/
```

Erwartung: `owui` laeuft wieder, localhost liefert HTTP 200/302, Tailscale-URL liefert kein 502 mehr.

## 5) Troubleshooting

- Letzte Service-Logs:
```bash
journalctl -u ai-stack-owui-ensure.service -n 100 --no-pager
```
- Wenn `docker compose` fehlschlaegt:
  - Rechte pruefen (`wasti` in Docker-Gruppe).
  - Env-Files pruefen (`.env`, optional `.config.env`, `open-webui/.config.env`).
- Wenn Tailscale weiterhin 502 liefert, obwohl localhost OK ist:
  - `sudo tailscale serve status` pruefen.
  - Serve-Mapping auf `http://127.0.0.1:3000` zuruecksetzen.
