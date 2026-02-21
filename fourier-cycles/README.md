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
  run --rm --build fourier-cycles
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
- `run_<timestamp>/<source>-<series>/cycles.csv` - alle als stabil markierten Cycle-Metriken (absolute Robustheit + Signifikanz + relative Rank-Metrik)
- `run_<timestamp>/<source>-<series>/waves.csv` - echte per-Cycle Zeitreihen-Komponenten fuer UI-Superposition
- optional `run_<timestamp>/<source>-<series>/windows.csv` - per-Window Audit (amp/phase/snr/presence je Cycle), aktivierbar via `FOURIER_EXPORT_WINDOWS_CSV=true`
- optional `run_<timestamp>/<source>-<series>/wavelet.png` - Wavelet-Aktivitaetskarte fuer nicht-stationaere Zeitfenster, aktivierbar via `FOURIER_ENABLE_WAVELET_VIEW=true`

Zusatz:
- `latest` Symlink auf den zuletzt erfolgreichen Lauf (praktisch fuer OpenClaw/Telegram Versand).

## Web App (UI + Controlled Trigger API)

Start (vom Repo-Root):

```bash
docker compose \
  --env-file .env \
  --env-file .config.env \
  --env-file fourier-cycles/.config.env \
  -f fourier-cycles/docker-compose.webapp.yml \
  up -d --build
```

Zugriff:
- UI: `http://127.0.0.1:${FOURIER_UI_HOST_PORT:-3010}`
- API: intern via UI-Proxy unter `/api/*` (kein zusaetzlicher Host-Port)

Manueller Trigger (optional, gleiches Ergebnis wie UI-Button):

```bash
curl -sS -X POST "http://127.0.0.1:${FOURIER_UI_HOST_PORT:-3010}/api/run" \
  -H "content-type: application/json" \
  -d '{"confirm":true}'
```

Status:

```bash
curl -sS "http://127.0.0.1:${FOURIER_UI_HOST_PORT:-3010}/api/run/status"
```

Hinweise:
- Trigger ist kontrolliert: kein freies Command-Injection-Feld, nur fester Pipeline-Aufruf.
- Parallel-Run-Guard: bei laufendem Job liefert der Trigger `409`.
- Trigger-Logs liegen unter `${FOURIER_OUTPUT_DIR_HOST}/_trigger_logs/`.

## Troubleshooting

- Wenn in der UI bei Superposition keine Kurve erscheint und ein `waves.csv` Hinweis auftaucht:
  - Pipeline neu laufen lassen: `docker compose --env-file .env --env-file .config.env --env-file fourier-cycles/.config.env -f fourier-cycles/docker-compose.yml run --rm --build fourier-cycles`
  - UI neu laden (arbeitet immer gegen `output/latest`).

## Stability-Logik

Methodik-Spezifikation:
- `fourier-cycles/METHODOLOGY.md`

Kurzfassung der jetzigen Logik:
- Analyseband der Perioden: `FOURIER_MIN_PERIOD_DAYS..FOURIER_MAX_PERIOD_DAYS` (Repo-Default: `30..300` Tage)
- Rolling-Windows (multi-scale): `FOURIER_ROLLING_WINDOWS_DAYS` mit `FOURIER_ROLLING_STEP_DAYS`
- Pro Window je Kandidat:
  - Band-Power-Ratio + SNR um die Zielfrequenz
  - Harmonic Regression (phase-invariant) fuer Amplitude/Phase/Lag/Fit
- Presence pro Window: `snr >= FOURIER_SNR_PRESENCE_THRESHOLD` und `band_power_ratio >= FOURIER_MIN_WINDOW_POWER_RATIO`
- Aggregation je Periode:
  - absolute Metriken: `amp_*`, `snr_*`, `presence_ratio`, `phase_locking_r`, `p_value_bandmax`
  - relative Metriken: `rank_score_norm`, `stability_score_norm` (nur innerhalb eines Runs/Serie vergleichbar)

Hinweis zur Kennzahl:
- `stability_score_norm` und `rank_score_norm` sind relative Rangwerte.
- Absolute Interpretationen kommen aus `presence_ratio`, `snr_*`, `phase_locking_r`, `p_value_bandmax`, `amp_*`.

Ausgabe-Selektion fuer Visualisierung/Reporting:
- Bis zu `FOURIER_SELECTION_TOP_K` Cycles (Default: 3)
- Presence >= `FOURIER_SELECTION_MIN_PRESENCE_RATIO` (Default: 0.60)
- Phase-Coherence >= `FOURIER_SELECTION_MIN_PHASE_LOCKING_R` (Default: 0.08; production-basket kalibriert)
- Signifikanz: `p_value_bandmax <= FOURIER_SELECTION_MAX_P_VALUE_BANDMAX` (Default: 1.00; fuer strengeres Filtering z. B. 0.05)
- Mindest-Amplitude: `FOURIER_SELECTION_MIN_AMP_SIGMA` (Default: 0.06; production-basket kalibriert)
- Mindest-Power via `FOURIER_SELECTION_MIN_NORM_POWER_PERCENTILE` (Default: 0.75)
- Mindestabstand der Perioden via `FOURIER_SELECTION_MIN_PERIOD_DISTANCE_RATIO` (Default: 0.20)

Hinweise zur Strenge:
- Kein regelbrechendes Backfill: Wenn Filter/Abstand weniger Kandidaten zulassen, bleiben es weniger als `FOURIER_SELECTION_TOP_K`.
- Rolling-Window-Stabilitaet nutzt lokale Band-Power um die Zielfrequenz (statt nur eines einzelnen naechsten FFT-Bins), um Leakage-Artefakte zu reduzieren.

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
- Verhalten:
  - Script startet Chrome mit Debug-Port lokal und baut den SSH-Tunnel in einer Retry-Schleife auf.
  - Die lokale Debug-Port-Pruefung erfolgt endpoint-basiert (`/json/version`) statt sprachabhaengiger `netstat`-State-Texte.
  - Wenn der Tunnel abbricht (z. B. `connect to 127.0.0.1 port 9222 failed`), startet automatisch ein neuer Versuch.
  - Wenn der Remote-Port belegt ist, rotiert das Script automatisch (`9223`, `9224`, ...).
  - Wenn der lokale UI-Port belegt ist, rotiert das Script automatisch den lokalen Forward-Port (`13010..`) und gibt die neue URL aus.
  - Falls nur der Reverse-Port (`-R`) belegt ist, wird automatisch ein UI-only Tunnel (`-L`) gestartet, damit die Web-UI stabil verfuegbar bleibt.
  - SSH läuft im Key-only Modus (`BatchMode=yes`), damit keine Passwort-Prompts in Retry-Loops erscheinen.
  - Vor dem Tunnel-Loop prueft das Script einmal SSH-Key-Auth, zeigt den Check sichtbar im Terminal an und bricht bei Fehler sofort ab.
  - Host-Key-Verhalten ist konfigurierbar (`SSH_STRICT_HOST_KEY_CHECKING`, Default `accept-new`), um stille Hangs beim ersten Connect zu vermeiden.
- Standardwerte:
  - Linux SSH: `wasti@192.168.0.188:22`
  - UI Forward: `127.0.0.1:13010` -> Linux `127.0.0.1:3010`
  - DevTools Reverse: Linux `127.0.0.1:9223` -> Windows Chrome `127.0.0.1:9222`
- Optionale Overrides:
  - `SSH_KEY_PATH` (Default: `%USERPROFILE%\.ssh\id_ed25519_fourier`)
  - `SSH_STRICT_HOST_KEY_CHECKING` (Default: `accept-new`)
  - `SSH_CONNECT_TIMEOUT_SEC` (Default: `8`)
  - `FOURIER_UI_LOCAL_PORT_SPAN` (Default: `10`, also `13010..13020`)
  - `TUNNEL_RETRY_DELAY_SEC` (Default: `5`)
  - `LOCAL_DEVTOOLS_WAIT_MAX_SEC` (Default: `20`)
  - `DEVTOOLS_REMOTE_PORT_SPAN` (Default: `10`, also `9223..9233`)
  - Der aktuell genutzte Remote-Port wird pro Versuch im Terminal ausgegeben.

### 3) MCP DevTools Server auf Linux starten

```bash
chmod +x fourier-cycles/tools/run_chrome_devtools_mcp.sh
DEVTOOLS_REMOTE_PORT=9223 ./fourier-cycles/tools/run_chrome_devtools_mcp.sh
```

Hinweis:
- Das Batch-Fenster mit dem SSH-Tunnel muss waehrend der Session offen bleiben.
- Der DevTools-Port bleibt auf beiden Seiten auf `127.0.0.1` gebunden (kein LAN-Expose).
