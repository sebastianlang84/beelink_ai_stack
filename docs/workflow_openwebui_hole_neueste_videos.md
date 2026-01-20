# Workflow-Ziel: Open WebUI Tool „hole die neuesten videos“

Ziel: In Open WebUI soll ich in natürlicher Sprache schreiben können:

- „hole die neuesten videos“

…und Open WebUI soll via **Tool-Zugriff** automatisch den **TranscriptMiner** anstoßen, danach **Summaries erzeugen** und diese in die **Open WebUI Knowledge Base** ablegen.

Diese Datei ist die Spezifikation für den gewünschten End-to-End Workflow (noch nicht zwingend vollständig implementiert).

PRD v0 (Zusammenfassung/Nächste Schritte): `docs/prd-tool-owui-transcript-miner-sync.md:1`

## Scope

**Input (User in Open WebUI):**
- Freitext wie „hole die neuesten videos“ (optional mit Parametern: „x=…“, „max=…“, „letzte … tage“, „topic …“).

**Output (System):**
- Transcripts werden geladen (YouTube).
- Summaries (pro Video, Markdown) werden durch TranscriptMiner erzeugt (LLM).
- Summaries werden in Open WebUI Knowledge Collections indexiert (RAG).

## Datenquellen (Single Source of Truth)

- Kanal-Liste und Standard-Parameter kommen aus TranscriptMiner Configs, z. B. `transcript-miner/config/config_ai_knowledge.yaml:1`.
- Defaults aus dem TranscriptMiner Schema:
  - `youtube.num_videos` Default: `10` (pro Channel) (`transcript-miner/src/common/config_models.py:39`)
  - `youtube.lookback_days` Default: `null` (optional) (`transcript-miner/src/common/config_models.py:45`)
  - `youtube.max_videos_per_channel` Default: `null` (Fallback: `num_videos`) (`transcript-miner/src/common/config_models.py:52`)
- Hinweis: TranscriptMiner verarbeitet `num_videos` **pro Channel** (`transcript-miner/src/transcript_miner/main.py:250`).
- Open WebUI Knowledge Target (Topic → Knowledge Collection):
  - `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON` (siehe `mcp-transcript-miner/.env.example:1`)

## Tool-Verhalten (LLM-Interaction Contract)

### 1) Parameter-Auflösung + Defaults

Wenn User keine Parameter angibt, verwendet das Tool Defaults und das LLM fragt **immer** kurz nach Bestätigung:

- `topic` (default: aus Tool-Konfiguration; empfohlen: `ai_knowledge`)
- `x = num_videos_per_channel` (default: `youtube.num_videos` aus der Topic-Config)
- `y = max_total_videos` (default: Tool-Default, z. B. `25` als Sicherheitslimit)
- `lookback_days` (default: aus Topic-Config oder Global-Config)
- `force_redownload_transcripts` (default: `false`)

**LLM muss nachfragen**, z. B.:
> „Ich würde `topic=ai_knowledge`, `x=5` Videos/Kanal, `lookback=30 Tage` und maximal `y=25` Videos insgesamt holen und dann synchronisieren. Passt das so?“

Wenn User abweichende Werte nennt, werden diese übernommen und erneut bestätigt, falls dadurch Kosten/Umfang deutlich steigen (z. B. `y>100` oder `lookback_days` sehr groß).

### 2) Ausführung (bestätigt)

Nach Bestätigung wird in dieser Reihenfolge gearbeitet:

1. TranscriptMiner Run für die Topic-Config starten (Kanäle aus `youtube.channels`).
2. Dabei gilt:
   - Pro Channel werden bis zu `x` Videos ausgewählt (oder `max_videos_per_channel` wenn gesetzt).
   - Zusätzlich begrenzt `y` den **Gesamtumfang** über alle Channels (Tool-Orchestrator stoppt, sobald `y` erreicht ist).
3. Wenn TranscriptMiner Summaries erzeugt hat, wird genau ein Sync-Zyklus in Richtung Open WebUI Knowledge ausgelöst:
   - direkt via `mcp-transcript-miner` (`POST /sync/topic/{topic}` oder `POST /index/transcript`)

### 3) Ergebnis-Reporting

Das Tool liefert eine kompakte Zusammenfassung zurück:

- Wie viele Channels gefunden wurden
- Wie viele Videos insgesamt verarbeitet wurden (und ob durch `y` gekappt wurde)
- Wie viele Summaries gefunden/erzeugt wurden
- Wie viele Knowledge-Uploads `indexed` vs. `skipped` waren
- Verweise auf Logs/Output-Root (ohne Secrets)

## Nicht-Ziele / Guardrails

- Kein direktes Exposing neuer Host-Ports: Tool-Service bleibt im Docker-Netz (`ai-stack`).
- Keine Secrets im Repo: API Keys ausschließlich via `/etc/ai-stack/*.env` (Policy: `docs/policy_secrets_environment_variables_ai_stack.md:1`).
- Fail-fast bei fehlenden Mappings (`topic` ohne Knowledge-ID) oder fehlendem Output-Root.

## Implementierungs-Hinweise (Folgearbeit)

- Tool kann als interner HTTP-Service (FastAPI) implementiert werden, den Open WebUI als „Tool“ nutzt.
- Orchestrator muss `y=max_total_videos` als zusätzliche Logik ergänzen (TranscriptMiner selbst limitiert aktuell nur pro Channel).
