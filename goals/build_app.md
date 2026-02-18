# build_app.md - Context Engineering Template (5+2)

Status: active
Owner: wasti
Date: 2026-02-18
Project: fourier-cycles

## 0. Executive Summary
- One-liner: Build a reproducible Docker job that fetches Yahoo+FRED series, extracts stable cycles, and generates Telegram-ready image artifacts.
- Why now: `fourier-cycles/` scaffold exists; next step is to harden cycle quality and close the OpenClaw delivery loop.
- Target release date: 2026-02-25 (internal alpha)

## 1) Architect (Bauplan)

### 1.1 Problem
- What exact problem are we solving?
  - We need repeatable cycle analysis from financial/macroeconomic series, with explicit stability filters to avoid one-off spectral peaks.
- Current pain/time/cost:
  - Current POC (`scripts/finance_fourier_analysis.py`) is single-run exploratory and does not enforce robust stability gates or output contract for Telegram delivery.
- Why existing solutions are insufficient:
  - Raw top-FFT ranking overweights transient frequencies and provides no persistence metric across rolling windows.

### 1.2 User
- Primary user persona: Single operator (`wasti`) running private home-server analytics.
- Secondary persona (optional): OpenClaw automation worker sending report images to Telegram.
- User jobs-to-be-done:
  - Trigger analysis over a defined timeframe.
  - See only cycles that pass stability criteria.
  - Retrieve generated visuals quickly via Telegram without a dedicated UI.

### 1.3 Success (Definition of Done)
- DoD metric 1:
  - For each configured series, produce `spectrum.png`, `stability.png`, `reconstruction.png`, `cycles.csv`, `summary.json` under one run folder.
- DoD metric 2:
  - Stable cycles must satisfy `presence_ratio >= FOURIER_MIN_PRESENCE_RATIO` where presence is based on rolling window power threshold.
- Non-functional acceptance (latency, uptime, etc.):
  - Batch run for default basket (2 Yahoo + 2 FRED) completes in under 5 minutes on host hardware.
- Demo scenario that must work end-to-end:
  - Run Docker job -> artifacts appear under `${FOURIER_OUTPUT_DIR_HOST}/latest/...` -> OpenClaw sends requested image to Telegram.

### 1.4 Constraints
- Time: Internal alpha in 1 week.
- Budget: No paid data feeds required for alpha.
- Compliance/Security:
  - No secrets in repo; env policy unchanged (`.env` secrets-only, `.config.env` non-secrets).
- Runtime/platform limits:
  - Docker Compose service pattern only; no new UI; no new host ports.

### 1.5 Non-goals
- Explicitly out of scope:
  - Trading signal generation or forecast claims.
  - Real-time streaming analytics.
  - Multi-tenant/user-facing productization.

Architect gate (must be green):
- [x] Problem is concrete and measurable.
- [x] User + DoD are explicit.
- [x] Constraints/non-goals are written.

Architect artifacts:
- PRD/Goal summary
- DoD checklist

---

## 2) Trace (Technische Blaupause)

### 2.1 Data schema
- Main entities:
  - `run_summary` (batch metadata)
  - `series_summary` (per source/series)
  - `cycle_metric` (period/power/stability stats)
  - `artifact_set` (PNG/CSV/JSON outputs)
- Key fields:
  - `run_id`, `source`, `series`, `timeframe_days`, `resample_rule`,
  - `period_days`, `norm_power`, `presence_ratio`, `median_window_power_ratio`, `stable`
- Ownership/lifecycle of each entity:
  - Produced by one batch run, stored in `run_<timestamp>/...`; `latest` symlink points to most recent successful run.

### 2.2 Integrations map
- External system 1: Yahoo Finance Chart API
  - Endpoint(s): `https://query1.finance.yahoo.com/v8/finance/chart/{symbol}`
  - Auth method: none
  - Rate limits: undocumented/public endpoint, treat as best-effort with timeout+retry policy in app roadmap
- External system 2: FRED CSV endpoint
  - Endpoint(s): `https://fred.stlouisfed.org/graph/fredgraph.csv`
  - Auth method: none
  - Rate limits: public endpoint, best-effort
- External system 3: OpenClaw (filesystem handoff)
  - Endpoint(s): none (file path contract)
  - Auth method: host-local permissions
  - Rate limits: n/a

### 2.3 Tech stack
- Frontend: none
- Backend: Python 3.12 (`requests`, `pandas`, `numpy`, `matplotlib`)
- Storage: filesystem artifacts under bind-mounted output directory
- Queue/Worker (if any): none (batch run model)
- Hosting/Deploy: Docker Compose service `fourier-cycles`

### 2.4 Planned data flow
1. Input enters via: env/CLI config (symbols, FRED series, timeframe, thresholds).
2. Validation happens in: argument parsing + minimum points/timeframe checks.
3. Processing happens in: fetch -> resample -> transform -> FFT -> rolling stability scoring -> cycle selection.
4. Persistence happens in: per-run output directory with per-series subfolders and JSON summaries.
5. Output delivered via: image/CSV/JSON artifacts, consumed by OpenClaw Telegram command.

Trace gate (must be green):
- [x] Data model documented.
- [x] Integrations/auth clear.
- [x] Stack fixed (no tool roulette).

Trace artifacts:
- Architecture note
- Data flow diagram (simple text/mermaid is enough)

---

## 3) Link (Verbindungspruefung)

### 3.1 Integration checks
- API reachability check result:
  - Verified on 2026-02-18 (UTC) via Docker smoke run; Yahoo and FRED endpoints returned data for default basket (`SPY`, `BTC-USD`, `DGS10`, `CPIAUCSL`).
- Auth check result:
  - No API auth required for Yahoo/FRED. OpenClaw handoff is local file-based.
- Minimal request/response smoke result:
  - Completed runtime smoke run:
    - `docker compose --env-file .env --env-file .config.env --env-file fourier-cycles/.config.env.example -f fourier-cycles/docker-compose.yml run --rm --build fourier-cycles`
    - Result: `run_dir=/data/output/run_20260218T231819Z`, `success=4`, `failure=0`.
  - Artifacts verified on host:
    - `/home/wasti/ai_stack_data/fourier-cycles/output/latest -> run_20260218T231819Z`
    - `summary.json` plus per-series PNG/CSV/JSON outputs present.

### 3.2 Failure notes
- Known unstable endpoints:
  - Yahoo endpoint can intermittently fail or return sparse data for some symbols.
- Required retries/timeouts:
  - Current timeout env: `FOURIER_TIMEOUT_SECONDS`.
  - Next increment: add bounded retries/backoff and classify transient fetch errors.

Link gate (must be green):
- [x] Every required endpoint responds.
- [x] Auth works with intended scopes.
- [ ] At least one successful roundtrip per integration.

Link artifacts:
- Link test log (commands + responses)

---

## 4) Assemble (Schichtweiser Zusammenbau)

### 4.1 Layer plan
1. Foundation layer (storage/connectivity): Docker service, env contracts, output mount.
2. Logic layer (domain/backend): fetch + FFT + rolling stability + artifact generation.
3. Interface layer (API/UI): no UI; filesystem contract for OpenClaw Telegram dispatch.

### 4.2 Build steps
- Step A:
  - Deliverable: `fourier-cycles/` scaffold with compose, Dockerfile, config examples.
  - Test: compose config renders cleanly.
- Step B:
  - Deliverable: pipeline emits per-series artifacts and run summary.
  - Test: python compile + one end-to-end run over starter basket.
- Step C:
  - Deliverable: OpenClaw command path mapping to `latest` artifacts.
  - Test: Telegram receives requested image for one symbol/series.

### 4.3 Change isolation
- Files/services touched per step:
  - Step A/B: `fourier-cycles/` + root docs only.
  - Step C: `openclaw/` integration files only.
- Rollback approach:
  - Revert last task commit; no DB migration/state mutation required.

Assemble gate (must be green):
- [x] Built in layers, not one-shot.
- [x] Every layer has a verification step.
- [x] Regressions are tracked per step.

Assemble artifacts:
- Incremental commits
- Verification outputs per layer

---

## 5) Stress Test (Belastungsprobe)

### 5.1 Functional tests
- Happy path tests:
  - Mixed basket run (Yahoo+FRED) with default thresholds.
  - Output folder structure + `latest` symlink correctness.
- Expected outcomes:
  - Non-empty artifacts for reachable series; failures isolated per series, not global crash.

### 5.2 Edge cases
- Empty input:
  - Empty symbol/series list should fail fast with explicit error.
- Invalid input:
  - Bad date/threshold configs should fail at parse/validation stage.
- Timeout/downstream failure:
  - One series may fail while others continue and are summarized in `summary.json` failures list.
- Concurrent requests:
  - Parallel runs may race on `latest` symlink; operational guidance should serialize scheduled runs.

### 5.3 Error handling
- User-visible error behavior:
  - Clear stderr line: `error source=... series=... msg=...`.
- Logging behavior:
  - stdout/stderr per run, plus persisted `summary.json` status.
- Retry/fallback policy:
  - Current: no retries (timeout only).
  - Planned: bounded retries with exponential backoff for fetch steps.

Stress Test gate (must be green):
- [x] Core user flow passes.
- [ ] Critical edge cases handled.
- [ ] Errors are controlled and observable.

Stress Test artifacts:
- Test matrix
- Failure examples with expected handling

---

## 6) Validate (Production gate)

### 6.1 Security/correctness
- AuthN/AuthZ checks:
  - No remote write endpoints exposed; batch job runs in Docker network only.
- Data isolation checks:
  - Output persisted to dedicated host directory (`FOURIER_OUTPUT_DIR_HOST`).
- Secret handling checks:
  - No secrets required for Yahoo/FRED by default; env policy unchanged.
- Input/output validation checks:
  - Min points, date window, and thresholds validated before compute.

### 6.2 Compliance/readiness
- Privacy requirements:
  - Public market/macroeconomic data only; no personal data involved.
- Auditability requirements:
  - Keep run summaries and selected cycle metrics per run for reproducibility.

Validate gate (must be green):
- [ ] Security checklist complete.
- [ ] No blocker-level correctness issue open.

Validate artifacts:
- Security checklist
- Sign-off notes

---

## 7) Monitor (Production operation)

### 7.1 Telemetry
- Core metrics:
  - run duration, success/failure count, stable cycles per series.
- SLO/SLA targets:
  - >=95% successful series processing per scheduled run (excluding transient data-source outages).
- Alert thresholds:
  - Alert when two consecutive scheduled runs have zero successful series.

### 7.2 Logging/tracing
- Structured logs:
  - Not yet (current logs are plain text).
- Trace IDs:
  - `run_id` acts as correlation key.
- Retention policy:
  - Keep last N runs; prune older folders via scheduled housekeeping (to be defined).

### 7.3 Product signals
- Success funnel:
  - fetch success -> cycle extraction success -> artifact generation -> Telegram delivery.
- Drop-off points:
  - endpoint failures, insufficient datapoints, no cycles passing thresholds.
- Cost per run/request:
  - compute-only local cost; no paid API dependency for core path.

Monitor gate (must be green):
- [ ] Metrics + alerts live.
- [ ] Logs are useful for incident debugging.
- [ ] Product-level signals collected.

Monitor artifacts:
- Dashboard links
- Alert runbook

---

## Final Go/No-Go
- Decision: Go for internal alpha on batch processing path; OpenClaw Telegram handoff still pending.
- Open risks:
  - Regime shifts can make cycles unstable despite passing current thresholds.
  - Yahoo endpoint intermittency may reduce reliability without retries.
  - `latest` symlink race risk under concurrent runs.
- Owner for unresolved items: wasti
- Planned revisit date: 2026-02-25

## Notes
- Deterministic outcome is a direction, not an absolute guarantee.
- If a phase is red, stop and return to the last green phase.
