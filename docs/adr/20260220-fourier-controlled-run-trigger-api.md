# ADR: Fourier Webapp Controlled Run Trigger API
Date: 2026-02-20
Status: Accepted

## Context
- `fourier-cycles` web UI was read-only and required manual CLI runs for new artifacts.
- Phase D in `fourier-cycles/PRD_webapp.md` required an optional controlled trigger from the web app.
- Security policy for this repo avoids exposing unnecessary host ports and arbitrary remote command execution.

## Decision
- Add an internal `fourier-cycles-api` service to `fourier-cycles/docker-compose.webapp.yml`.
- Expose trigger/status only via UI reverse proxy (`/api/*`) and keep API off host ports.
- Implement:
  - `POST /api/run` with explicit `{"confirm": true}` requirement.
  - `GET /api/run/status` for polling in UI.
- Trigger path executes only the fixed pipeline command (`python /app/src/fourier_cycles_pipeline.py`), adds a single-run busy guard, and writes logs to `fourier-cycles/output/_trigger_logs/`.

## Consequences
- Positive:
  - Operators can trigger and monitor runs directly from the UI without shell access.
  - No new host-port exposure; API remains internal to Compose network.
  - Run execution remains constrained to the existing pipeline entrypoint.
- Negative:
  - Trigger state is in-memory; API container restarts reset active status history.
  - API image now includes pipeline dependencies plus FastAPI runtime.

## Alternatives considered
- Keep UI read-only and run only via CLI/manual compose commands.
  - Rejected: does not satisfy Phase D trigger requirement.
- Trigger Docker from API via mounted Docker socket.
  - Rejected: increases privilege surface unnecessarily.
