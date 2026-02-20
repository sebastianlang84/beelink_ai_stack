# fourier-cycles - Dockerized Fourier Cycle Extraction (Yahoo + FRED)

Ziel: Zeitreihen aus Yahoo Finance und FRED holen, Spektrum berechnen, instabile Peaks rausfiltern und Telegram-faehige Bildartefakte erzeugen.

## Start

```bash
./scripts/create_ai_stack_network.sh
cd /home/wasti/ai_stack

docker compose \
  --env-file .env \
  --env-file .config.env \
  --env-file fourier-cycles/.config.env \
  -f fourier-cycles/docker-compose.yml \
  run --rm fourier-cycles
```

## Outputs

Standardpfad (Host):
- `${FOURIER_OUTPUT_DIR_HOST}` (Default: `/home/wasti/ai_stack/fourier-cycles/output`)

Pro Lauf:
- `run_<timestamp>/summary.json` - Laufzusammenfassung
- `run_<timestamp>/<source>-<series>/price.png` - echter Preis-/Level-Chart der Zeitreihe
- `run_<timestamp>/<source>-<series>/price_cycle_overlay.png` - Preis/Level plus normalisierter Composite-Cycle-Index
- `run_<timestamp>/<source>-<series>/cycle_components.png` - normalisierte Top-Cycle-Komponenten (uebereinander)
- `run_<timestamp>/<source>-<series>/spectrum.png` - globales Spektrum
- `run_<timestamp>/<source>-<series>/stability.png` - Rolling-Power/Presence je Cycle
- `run_<timestamp>/<source>-<series>/reconstruction.png` - transformiertes Signal (Returns) vs. rekonstruiertes Cycle-Signal
- `run_<timestamp>/<source>-<series>/cycles.csv` - finale Cycle-Metriken
- `run_<timestamp>/<source>-<series>/waves.csv` - echte per-Cycle Zeitreihen-Komponenten fuer UI-Superposition

Zusatz:
- `latest` Symlink auf den zuletzt erfolgreichen Lauf (praktisch fuer OpenClaw/Telegram Versand).

## Stability-Logik

Ein Cycle gilt als stabil, wenn er in Rolling-Windows haeufig genug auftaucht:
- Window-Presence >= `FOURIER_MIN_PRESENCE_RATIO`
- Presence basiert auf Window-Power-Ratio >= `FOURIER_MIN_WINDOW_POWER_RATIO`

Damit werden Peaks verworfen, die nur in einem kleinen Bruchteil des Zeitraums auftreten.

Ausgabe-Selektion fuer Visualisierung/Reporting:
- Top `FOURIER_SELECTION_TOP_K` Cycles (Default: 3)
- Presence >= `FOURIER_SELECTION_MIN_PRESENCE_RATIO` (Default: 0.60)
- Mindest-Power via `FOURIER_SELECTION_MIN_NORM_POWER_PERCENTILE` (Default: 0.75)
- Mindestabstand der Perioden via `FOURIER_SELECTION_MIN_PERIOD_DISTANCE_RATIO` (Default: 0.20)

## Telegram-Integration (ohne neue UI)

OpenClaw kann Bilder aus `latest/<source>-<series>/` direkt verschicken.
Empfohlen: Ein einfacher OpenClaw-Command mappt Query -> Dateipfad in `latest`.

## Web App Planung

- Plan-Dokument: `fourier-cycles/PRD_webapp.md`

## Windows Debug Tunnel + MCP DevTools

Ziel: Browser auf Windows mit Debug-Port starten und den DevTools-Port per SSH Reverse-Tunnel fuer MCP auf Linux bereitstellen.

### 1) Einmalig auf Linux installieren

```bash
npm install --prefix "$HOME/.local/share/chrome-devtools-mcp" chrome-devtools-mcp@0.17.3
```

### 2) Windows-Tunnel + Browser starten

- Datei: `fourier-cycles/tools/open_fourier_debug.bat`
- Start auf Windows (PowerShell oder CMD):
  - `fourier-cycles\\tools\\open_fourier_debug.bat`
- Standardwerte:
  - Linux SSH: `wasti@192.168.0.188:22`
  - UI Forward: `127.0.0.1:13010` -> Linux `127.0.0.1:3010`
  - DevTools Reverse: Linux `127.0.0.1:9223` -> Windows Chrome `127.0.0.1:9222`

### 3) MCP DevTools Server auf Linux starten

```bash
chmod +x fourier-cycles/tools/run_chrome_devtools_mcp.sh
DEVTOOLS_REMOTE_PORT=9223 ./fourier-cycles/tools/run_chrome_devtools_mcp.sh
```

Hinweis:
- Das Batch-Fenster mit dem SSH-Tunnel muss waehrend der Session offen bleiben.
- Der DevTools-Port bleibt auf beiden Seiten auf `127.0.0.1` gebunden (kein LAN-Expose).
