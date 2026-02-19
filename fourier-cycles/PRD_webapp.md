# PRD - Fourier Cycles Web App (Frontend/Backend, Docker, Tailscale)

Status: draft
Owner: wasti
Date: 2026-02-18
Service: fourier-cycles

## 1) Ziel

Aus dem aktuellen Batch-Output (`fourier-cycles/output`) soll eine browserbasierte App werden:
- sauber getrennt in Frontend und Backend
- dockerized deploybar
- VPN-only via Tailscale erreichbar
- mit reproduzierbarem Debug-Zugang fuer Browser-Debugging via SSH-Tunnel + DevTools

## 2) Scope

In Scope:
- Web UI fuer Browse/Filter/Compare der vorhandenen Fourier-Artefakte
- API fuer Runs/Series/Cycles/Charts-Metadaten
- optionaler Trigger fuer neue Fourier-Runs aus der UI (Phase 2)
- Windows `.bat` fuer One-Click Tunnel + Browser-Start im Debug-Modus

Out of Scope (Phase 1):
- Public Internet Expose
- User-Management/RBAC
- OpenClaw-Integration (bewusst separat)

## 3) Architektur

### 3.1 Frontend
- Stack: React + TypeScript + Vite
- Aufgaben:
  - Run-Liste
  - Serienansicht (price, overlay, components, spectrum, stability, reconstruction)
  - Cycle-Tabelle (selected cycles + stability metrics)
- Build-Output statisch, via Nginx ausgeliefert

### 3.2 Backend
- Stack: Python FastAPI
- Aufgaben:
  - Filesystem-Index auf `fourier-cycles/output`
  - REST-API fuer Runs/Series/Charts/Cycles
  - optional Run-Trigger Endpoint (Phase 2)
- Keine direkte Host-Port-Freigabe notwendig (internes Docker-Netz)

### 3.3 Datenfluss
1. Pipeline schreibt Artefakte in `fourier-cycles/output/run_*`.
2. Backend indexiert diese Artefakte.
3. Frontend konsumiert API und rendert Charts/Bilder.
4. Zugriff extern nur ueber Tailscale (Serve -> localhost UI-Port).

## 4) Docker Topologie

Geplante Service-Struktur in `fourier-cycles/docker-compose.yml` (oder `docker-compose.webapp.yml`):
- `fourier-cycles` (bestehender batch job)
- `fourier-cycles-api` (FastAPI)
- `fourier-cycles-ui` (Nginx + static SPA)

Netzwerk:
- alle Dienste im bestehenden `ai-stack` Docker-Netz

Volumes:
- shared read-only mount fuer API/UI auf `fourier-cycles/output`

Host Binding (empfohlen):
- nur UI auf `127.0.0.1:<FOURIER_UI_HOST_PORT>`
- API nicht direkt auf Host publizieren

## 5) Tailscale Zugriff

Zielbild:
- VPN-only Zugriff via `tailscale serve`
- bevorzugt eigener Pfad oder eigenes Hostname-Mapping fuer Fourier-UI

Empfohlene Reihenfolge:
1. UI lokal host-only erreichbar machen (`127.0.0.1:<port>`).
2. `tailscale serve` Mapping auf diesen Port setzen.
3. Kein LAN-Bind, kein Public Expose.

Open Decision:
- Pfadbasiert (`/fourier`) vs. eigenes Hostname-Mapping (`fourier.<tailnet>.ts.net`).

## 6) API Entwurf (Phase 1)

Minimal Endpoints:
- `GET /healthz`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/series`
- `GET /api/runs/{run_id}/series/{series_id}`
- `GET /api/runs/{run_id}/series/{series_id}/cycles`
- `GET /api/runs/{run_id}/series/{series_id}/artifacts`

Phase 2:
- `POST /api/run` (trigger batch)

## 7) UI Screens (Phase 1)

1. Runs Overview
- run id, timestamp, success/failure counts

2. Series Detail
- image cards: `price.png`, `price_cycle_overlay.png`, `cycle_components.png`, `spectrum.png`, `stability.png`, `reconstruction.png`
- cycle table: period, presence, norm_power, stability_score

3. Compare View
- side-by-side 2-3 series from same run

## 8) Windows Debug Script (.bat) - Plan

Datei (geplant):
- `fourier-cycles/tools/open_fourier_debug.bat`

Zweck:
- One-click fuer Windows:
  - SSH Tunnel auf Home-Server fuer UI/API
  - optional Reverse Tunnel fuer Browser DevTools Port
  - Browserstart mit remote debugging enabled

Geplante Variablen:
- `SSH_USER`
- `SSH_HOST`
- `FOURIER_UI_REMOTE_PORT`
- `FOURIER_UI_LOCAL_PORT`
- `DEVTOOLS_LOCAL_PORT` (Windows Chrome)
- `DEVTOOLS_REMOTE_PORT` (Server-seitiger Tunnel-Endpunkt)

Geplanter Ablauf:
1. Start Chrome mit `--remote-debugging-port` und separatem `--user-data-dir`.
2. Starte SSH mit
   - Local forward: `L <local_ui>:127.0.0.1:<remote_ui>`
   - Reverse forward: `R 127.0.0.1:<remote_devtools>:127.0.0.1:<local_devtools>`
3. Oeffne Browser auf `http://127.0.0.1:<local_ui>`.
4. MCP DevTools Server kann ueber den Reverse-Tunnel auf den Browser-Debug-Port zugreifen.

Wichtige Entscheidung vor Umsetzung:
- Welcher MCP-DevTools-Server wird konkret verwendet (Name/Launch-Mode), damit Tunnel-Ports exakt passen.

## 9) Sicherheits- und Betriebsregeln

- `.env` bleibt secrets-only.
- Non-secrets in `.config.env` + `fourier-cycles/.config.env`.
- Keine neuen LAN/public host binds ohne explizite Freigabe.
- Logs/telemetry minimal in Phase 1, spaeter ausbauen.

## 10) Delivery Plan

Phase A - Foundations
- API/Frontend Skeleton, Docker build/run, health checks

Phase B - Read-only UI
- Artefakte listen/rendern, cycle table, compare view

Phase C - Tunnel + Debug
- `.bat` script bereitstellen und dokumentieren
- Debug smoke test mit MCP DevTools Tunnel

Phase D - Optional Run Trigger
- backend endpoint fuer controlled batch trigger

## 11) Akzeptanzkriterien

- Frontend und Backend laufen getrennt in Docker Containern.
- UI ist nur lokal gebunden und via Tailscale erreichbar.
- App zeigt vorhandene Fourier-Artefakte korrekt an.
- Windows `.bat` startet Tunnel + Browser reproduzierbar.
- Debug-Zugriff ueber Tunnel fuer MCP DevTools ist nachweisbar.

## 12) Offene Entscheidungen

1. Frontend Framework final: React/Vite (vorgeschlagen) bestaetigen.
2. API Framework final: FastAPI (vorgeschlagen) bestaetigen.
3. Tailscale Mapping: Pfad vs eigener Hostname.
4. MCP DevTools konkrete Runtime/Port-Konvention.
   - Resolved 2026-02-19: `chrome-devtools-mcp` (pinned `0.17.3`), Windows `9222` -> Linux reverse tunnel `9223` (ADR: `docs/adr/20260219-fourier-debug-devtools-mcp-tunnel.md`).
