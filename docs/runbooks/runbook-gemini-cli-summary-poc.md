# Runbook — Gemini CLI Summary POC (statt OpenRouter API)

Ziel: Schnell testen, ob Summary-Generierung per Gemini CLI headless stabil funktioniert.
Modell-Policy: Gemini-3-Flash-Familie als `gemini-3-flash-preview`, keine Pro-Modelle, kein Thinking.

Scope:
- Kein produktiver Pipeline-Umbau.
- Nur POC-Runner fuer einen Transcript-Input.

## 1) Voraussetzungen

- `gemini` CLI ist installiert.
- Auth fuer Gemini CLI ist gesetzt:
  - bevorzugt Account-Auth in `~/.gemini/settings.json`
  - fuer `gemini-3-flash-preview` muss in den Settings `preview=true` gesetzt sein
  - alternativ (Fallback) via `GEMINI_API_KEY`

## 2) Default POC ausfuehren

```bash
cd /home/wasti/ai_stack
./scripts/run-gemini-cli-summary-poc.sh
```

Default-Input:
- Prompt: `transcript-miner/tests/prompt-engineering/_promptnew.md`
- Transcript: `transcript-miner/tests/prompt-engineering/1TD3WHTg3gQ_transcript.md`

Output:
- `transcript-miner/tests/prompt-engineering/_out_gemini_cli_poc/<video_id>.gemini_cli.<timestamp>.summary.md`
- `transcript-miner/tests/prompt-engineering/_out_gemini_cli_poc/<video_id>.gemini_cli.<timestamp>.usage.json`

## 3) Mit eigenen Parametern

```bash
./scripts/run-gemini-cli-summary-poc.sh \
  --prompt-file transcript-miner/tests/prompt-engineering/_promptnew.md \
  --transcript-file transcript-miner/tests/prompt-engineering/JkQn9MoFlHk_transcript.md \
  --model gemini-3-flash-preview \
  --topic investing_test \
  --channel poc_channel
```

Wichtig:
- Pro-Modelle sind im Script geblockt (`--model ...pro...` -> Exit-Code `5`).
- Thinking wird per Prompt-Policy deaktiviert (CLI bietet aktuell keinen separaten Thinking-Flag).

## 4) Erfolgskriterium

- Script endet mit Exit-Code `0`.
- Output-Datei existiert.
- Usage-Datei existiert und enthaelt Token-Stats (`tokens.input`, `tokens.total`, `tokens.thoughts`).
- Ausgabe enthaelt idealerweise Wrapper-Dokumente:
  - `<<<DOC_START>>>`
  - `<<<DOC_END>>>`

Token-Usage schnell lesen:

```bash
latest_usage="$(ls -1t transcript-miner/tests/prompt-engineering/_out_gemini_cli_poc/*.usage.json | head -n1)"
jq '.model_effective, .tokens' "${latest_usage}"
```

Typischer Fehler vor Auth-Setup:
- Exit-Code `41` mit Hinweis auf fehlende Auth (`GEMINI_API_KEY` oder `~/.gemini/settings.json`).
