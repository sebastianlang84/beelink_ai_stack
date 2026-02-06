# Logs (Transcript Miner)

Dieses Verzeichnis enthaelt **nur Doku** zu den Logs (keine Log-Daten im Git).

## Grundsaetze

- Logs koennen **Secrets** enthalten (z. B. URLs mit Tokens, API-Errors, Header-Dumps). Vor dem Teilen immer redaction anwenden.
- Logfiles sind Debug-Artefakte, keine stabile API. Die stabilen Artefakte sind die Outputs unter `output/`.

## Wo entstehen Logs?

Je nach Run-Profil gibt es mehrere Log-Quellen:

- **CLI/Local Runs**: ueber `logging.file` / `logging.error_log_file` in der Config (siehe `docs/config.md`).
- **Docker/MCP Runs**: Container-Logs via `docker logs tm` bzw. Run-Logs unter dem persistenten Output-Root.

## Debug-Workflow (Kurz)

- Wenn ein Run "haengt": zuerst `output/data/indexes/<topic>/current/` und `output/data/diagnostics/` checken (falls vorhanden).
- Bei Netzwerkproblemen/Blocks: Proxy-Settings + Diagnostics Tools unter `tools/` nutzen (siehe Runbooks in `docs/`).

