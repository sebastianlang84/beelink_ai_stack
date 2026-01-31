# Watchdog (CPU/Temp/Disk Monitoring)

Leichter Host-Watchdog, der CPU-Last, Temperatur, Disk-Usage und Docker-Hygiene beobachtet.
Ausloeser erzeugen Burst-Diagnosen (Top-Prozesse + Container-Stats).

## Setup
1) Shared Secrets setzen: `.env.example` -> `.env` (nicht noetig fuer Watchdog).
2) Shared Config setzen: `.config.env.example` -> `.config.env` (optional).
3) Service-Config setzen: `watchdog/.config.env.example` -> `watchdog/.config.env` (non-secret, gitignored).
4) Start: `docker compose --env-file .env --env-file .config.env --env-file watchdog/.config.env -f watchdog/docker-compose.yml up -d --build`

## Volumes
- `watchdog-data`: Logs/Artefakte unter `/data`

## Output
- Baseline: `/data/watchdog.log.jsonl`
- Burst: `/data/watchdog.alert.jsonl`

## Temp-Schutz (Auto-Stop)
- Wenn `temperature.max_c` >= `WATCHDOG_TEMP_STOP_THRESHOLD_C` fuer `WATCHDOG_TEMP_STOP_CONSEC` Messungen hintereinander gilt, werden die Container in `WATCHDOG_TEMP_STOP_CONTAINER_NAMES` gestoppt.
- Deaktivieren: `WATCHDOG_TEMP_STOP_CONTAINER_NAMES=` (leer).
- Log-Check: `/data/watchdog.alert.jsonl` (Action: `stop_containers_temp_threshold`).

## One-shot Status (stdout)
- `docker exec watchdog python -m app.main --once`

## Notes
- Fuehrt lesenden Zugriff auf Host `/proc`, `/sys`, `/` und Docker Socket.
- Keine Notifications in v0 (nur Logs).
- Container-Name ist fix auf `watchdog` gesetzt (abweichend von der Standard-Policy, auf Wunsch).
