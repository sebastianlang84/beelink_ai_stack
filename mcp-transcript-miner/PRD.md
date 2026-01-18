# PRD — mcp-transcript-miner (YouTube Transcript HTTP Tool)

## Kontext
- Zweck: interner HTTP-Service, der für eine YouTube-Video-ID das beste verfügbare Transcript liefert (inkl. Language-Fallbacks) und es als Text zurückgibt.
- Ziel-Stack: Home-Server (`ai_stack`), Docker Compose, VPN-only Nutzung (keine öffentlichen Host-Ports).
- Primäre Konsumenten:
  - spätere Open-WebUI Tool-/Orchestrator-Komponenten (z. B. „hole die neuesten videos“)
  - interne Producer/Automationen (z. B. Scripts), die ein Transcript pro `video_id` benötigen

## Problem / Motivation
- YouTube Transcripts sollen automatisiert abrufbar sein, ohne dass jeder Producer direkt `youtube_transcript_api` integrieren muss.
- Einheitlicher Fehler-/Status-Contract (No transcript / Video unavailable / transient errors).
- Optionale Proxy-Unterstützung für Umgebungen mit Geoblocking/Rate-Limits.

## Ziele
1. **Einfacher Abruf**: `POST /transcript` liefert reinen Text (optional mit Timestamps) für eine `video_id`.
2. **Sprach-Fallback**: bevorzugte Sprachen (`de`, `en`, …) werden priorisiert, mit Fallback auf „best match“.
3. **Deterministische Idempotenz-Hilfe**: Response enthält `sha256` des Textes (für Downstream-Dedupe).
4. **Betriebsstabil**: Healthcheck-Endpunkt, klare Fehlercodes in JSON, saubere Logs.
5. **Sicherer Default**: keine Secrets erforderlich; keine Host-Port-Exponierung in Phase 1 (VPN-only).

## Nicht-Ziele (Phase 1)
- Kein vollständiger YouTube-Downloader (nur Transcripts, keine Medien).
- Keine User-/Auth-Schicht (Service bleibt intern im Docker-Netz).
- Keine Persistenz-DB als Muss (Caching optional, aber nicht erforderlich).
- Kein „Channel → newest videos“ (das ist Aufgabe von TranscriptMiner/Orchestrator).

## Produktumfang (Phase 1)

### API (SSOT)
- `GET /healthz`
  - `200` + `{ "status": "ok" }`
- `POST /transcript`
  - Request:
    - `video_id` (string, required)
    - `preferred_languages` (list[string], optional; Default aus Env)
    - `include_timestamps` (bool, optional; Default `false`)
  - Response (vereinheitlicht):
    - Success:
      - `{ "status": "success", "text": "...", "meta": { "language": "de", "is_generated": true|false, "sha256": "..." } }`
    - No transcript:
      - `{ "status": "no_transcript", "reason": "no_transcript_found" | "empty_transcript" }`
    - Error:
      - `{ "status": "error", "error_type": "...", "error_message": "..." }`

### Konfiguration
- `TRANSCRIPT_MINER_DEFAULT_LANGUAGES` (Default: `de,en`)
- `TRANSCRIPT_MINER_LOG_LEVEL` (Default: `info`)
- `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` (optional)

## Qualitätsanforderungen

### Reliability
- Service darf bei fehlenden Transcripts nicht crashen; er liefert `no_transcript`.
- Transiente Fehler sollen als `error` zurückkommen (Downstream entscheidet über Retry).

### Performance
- Ziel: „Single video transcript“ in Sekundenbereich.
- Keine unnötigen zusätzlichen API-Aufrufe; Language-Selection ist linear über `preferred_languages`.

### Observability
- `/healthz` für Container Healthchecks.
- Log-Level steuerbar; Fehler sollen genug Kontext enthalten (ohne Secrets).

### Security
- Keine Secrets im Container zwingend notwendig.
- Default-Deployment ohne Host-Ports (nur internal, z. B. über `ai_stack` Netz).
- Keine PII speichern; kein Persistenz-Write in Phase 1.

## Integration (ai_stack)
- Empfohlen: als interner Service im `ai_stack` Netzwerk betreiben.
- Typischer Flow:
  1) Producer ruft `mcp-transcript-miner` → erhält Transcript-Text.
  2) Producer sendet Text an **Transcript Miner** (`POST /index/transcript`) oder verarbeitet ihn weiter (Summaries via TranscriptMiner).

## Akzeptanztests (manuell / ops)
- `docker compose ps` zeigt `Up` + `healthy` (wenn Healthcheck aktiv).
- `curl http://<service>:8000/healthz` liefert `{ "status":"ok" }`.
- `POST /transcript`:
  - gültige Video-ID mit Transcript → `status=success`, `meta.sha256` gesetzt.
  - Video ohne Transcript → `status=no_transcript`.
  - nicht verfügbares Video → `status=error` mit `error_type=VideoUnavailable`.

## Offene Punkte / Follow-ups
- (Optional) Request-Timeout/Retry-Policy serverseitig (oder bewusst downstream).
- (Optional) simples In-Memory/SQLite Caching (z. B. `video_id+lang+timestamps` → text/sha256) zur Entlastung.
- (Optional) Rate-Limit/Backoff Header für Downstream-Retries.
- (Optional) zusätzlicher Endpoint für „raw segments“ (Text + Startzeiten) statt gerendertem Text.
