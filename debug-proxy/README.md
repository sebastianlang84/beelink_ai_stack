# debug-proxy — MITM Logging Proxy (JSONL)

Ziel: HTTP(S)-Traffic (z. B. OpenRouter) mitschneiden und als JSONL loggen.
**Achtung:** Logs enthalten Prompts/Responses (sensitiv). Nur lokal verwenden.

## Quickstart
1. Config setzen: `debug-proxy/.config.env.example` -> `debug-proxy/.config.env` (non-secret, optional).
2. Start (vom Repo-Root):
   `docker compose --env-file .env --env-file .config.env --env-file debug-proxy/.config.env -f debug-proxy/docker-compose.yml up -d`

## OWUI anschließen (optional)
- In `open-webui/.config.env`:
  - `OWUI_HTTP_PROXY=http://debug-proxy:8080`
  - `OWUI_HTTPS_PROXY=http://debug-proxy:8080`
  - `OWUI_NO_PROXY=owui,tm,context6,qdrant,localhost,127.0.0.1`
  - `OWUI_CA_BUNDLE_PATH=/debug-proxy/mitmproxy/mitmproxy-ca-cert.pem`
  - `DEBUG_PROXY_DATA_DIR_HOST=/home/wasti/ai_stack_data/debug-proxy`
- OWUI neu starten.

## Logs
- JSONL: `${PROXY_LOG_PATH:-/data/flows.jsonl}` (bind-mount unter `DEBUG_PROXY_DATA_DIR_HOST`)
- Truncation: `${PROXY_LOG_MAX_CHARS:-0}` (0 = kein per-request truncation)
- Gesamtlimit (Datei): `${PROXY_LOG_MAX_TOTAL_CHARS:-100000}` (haelt die Datei klein)
 - Gzip-Responses werden automatisch entpackt fuer Lesbarkeit.

## Zertifikat (TLS MITM)
- Der Proxy erzeugt ein CA-Zertifikat unter:
  - `/data/mitmproxy/mitmproxy-ca-cert.pem`
- OWUI vertraut dem Zertifikat via `OWUI_CA_BUNDLE_PATH`.
Hinweis: Der Proxy erzwingt `confdir=/data/mitmproxy`, damit OWUI und Proxy dasselbe CA verwenden.

## On/Off
- Proxy starten/stoppen via Compose.
- Zusätzlich: OWUI Proxy-Env leer lassen, wenn der Proxy aus sein soll.
