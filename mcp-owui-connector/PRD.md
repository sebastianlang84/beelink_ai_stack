# PRD — mcp-owui-connector (v0)

## Problem
Andere Clients (z. B. RooCode/OpenClaw) sollen Open WebUI Funktionen als MCP Tools nutzen koennen, ohne direkt selbst die Open WebUI APIs/Endpoints nachbauen zu muessen.

## Goals (v0)
- MCP Tools fuer:
  - Knowledge Collections: listen, files listen
  - Optionales Write: Markdown upload + in Knowledge add (gated via Env)
  - Admin External Tools config: GET + optional apply aus Repo Templates (gated via Env)
- Keine neuen Host-Ports ausser localhost-only Mapping (default).
- Secrets-handling nach Repo-Policy: Token nur in `.env` (gitignored, secrets-only).

## Non-Goals (v0)
- Vollstaendige Abdeckung aller Open WebUI APIs.
- "RAG Query" / Chat-Completion Wrapping (noch unspezifiziert).

## Constraints
- Muss auf dem externen Docker-Netz `ai-stack` laufen, damit `OPEN_WEBUI_BASE_URL=http://owui:8080` funktioniert.
- Write-Operationen muessen explizit aktiviert werden.

