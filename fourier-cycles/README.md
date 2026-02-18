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
- `${FOURIER_OUTPUT_DIR_HOST}`

Pro Lauf:
- `run_<timestamp>/summary.json` - Laufzusammenfassung
- `run_<timestamp>/<source>-<series>/spectrum.png` - globales Spektrum
- `run_<timestamp>/<source>-<series>/stability.png` - Rolling-Power/Presence je Cycle
- `run_<timestamp>/<source>-<series>/reconstruction.png` - Signal vs. rekonstruiertes Cycle-Signal
- `run_<timestamp>/<source>-<series>/cycles.csv` - finale Cycle-Metriken

Zusatz:
- `latest` Symlink auf den zuletzt erfolgreichen Lauf (praktisch fuer OpenClaw/Telegram Versand).

## Stability-Logik

Ein Cycle gilt als stabil, wenn er in Rolling-Windows haeufig genug auftaucht:
- Window-Presence >= `FOURIER_MIN_PRESENCE_RATIO`
- Presence basiert auf Window-Power-Ratio >= `FOURIER_MIN_WINDOW_POWER_RATIO`

Damit werden Peaks verworfen, die nur in einem kleinen Bruchteil des Zeitraums auftreten.

## Telegram-Integration (ohne neue UI)

OpenClaw kann Bilder aus `latest/<source>-<series>/` direkt verschicken.
Empfohlen: Ein einfacher OpenClaw-Command mappt Query -> Dateipfad in `latest`.
