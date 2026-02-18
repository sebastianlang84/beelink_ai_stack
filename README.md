# ai_stack — Home-Server Automation

Dieses Repository enthält die „source of truth“ für ein **privates** Home-Server Setup (kein öffentliches Produkt, kein Business-Deployment).

Purpose: Operator-Guide.  
Contains: Setup, Betrieb, Runbooks mit Kontext.  
Does not contain: Laufende Entscheidungen/Historie (siehe `HANDOFF.md`, `CHANGELOG.md`, `docs/adr/`).

Dokunetz: Einstieg über `INDEX.md:1`.

## Zielsystem (Soll-Zustand)
- Server: Home-Server / Mini-PC im LAN
- Hostname: `beelink` (FQDN: `beelink.telekom.ip`)
- Hardware: AZW MINI S
- CPU: Intel(R) N150 (4 Cores)
- RAM: 16 GiB
- Disk: ~512 GB (Root: ext4)
- OS: Debian GNU/Linux 13.2 (trixie), Kernel `6.12.57+deb13-amd64`
- User: `wasti` (kein `root`, in `sudo` Gruppe)
- Runtime: Docker + Docker Compose
- Phase 1: **kein** Reverse Proxy / keine Domain / kein öffentliches TLS-Setup (Tailnet-HTTPS via Tailscale Serve ok)
- Zugriffsziel: **VPN-only** (Tailscale), Services lauschen lokal auf `127.0.0.1:<port>` (kein LAN-Port)
- Status: Zugriff im Tailnet via Tailscale Serve (HTTPS) ist eingerichtet (siehe `TODO.md#ai_stack_todo`)
- LAN-IP (wlan0): `192.168.0.188` (für SSH im LAN; kann sich bei DHCP ändern)

## Quickstart (owui)
1. Shared Secrets setzen: `.env.example` → `.env` (nicht committen).
2. Shared Config setzen (non-secret): `.config.env.example` → `.config.env` (nicht committen).
3. Service-Config setzen (non-secret): `open-webui/.config.env.example` → `open-webui/.config.env` (nicht committen, optional).
4. Start (vom Repo-Root): `docker compose --env-file .env --env-file .config.env --env-file open-webui/.config.env -f open-webui/docker-compose.yml up -d`
5. Zugriff lokal am Server: `http://127.0.0.1:3000` (VPN-only empfohlen via Tailscale Serve)

Betrieb/Access: `open-webui/README.md:1` (default localhost-only; empfohlen via Tailscale Serve im Tailnet).
RAG Retrieval (Snapshot aus `webui.db`, 2026-02-14): `top_k=20`, `top_k_reranker=8`, `relevance_threshold=0.35`, `enable_hybrid_search=false`, `hybrid_bm25_weight=0.35` (OWUI). Reproduzierbarer Dump: `./scripts/openwebui_snapshot_rag_settings.sh docs/archive/owui-rag/owui_rag_settings_snapshot.md`.
Day-sensitive Guard (heute/des Tages/latest): Striktes Same-Day-Sufficiency-Gate im OWUI-RAG-Template aktiv; Update reproduzierbar via `./scripts/openwebui_apply_investing_rag_guard.sh`.
RAG Baseline-Probe (Phase 1): `./scripts/owui_rag_baseline_probe.sh` mit Query-Matrix aus `config/owui_rag_baseline_queries.json` (Beispielreports: `docs/archive/owui-rag/owui_rag_baseline_2026-02-15.md`, `docs/archive/owui-rag/owui_rag_baseline_remote_2026-02-15.md`).
API Keys (aktueller Stand): Default User Permissions erlauben `features.api_keys=true` (siehe `open-webui/README.md:1`).

## Open WebUI 502 Auto-Recovery (Tailscale Serve)
Wenn `owui` stoppt und die `ts.net` URL `502` liefert:
- Script: `./scripts/ensure-owui-up.sh ensure`
- Runbook: `docs/runbooks/runbook-owui-502-autorecover.md:1`
- Optional persistent: systemd Timer via `scripts/systemd/ai-stack-owui-ensure.{service,timer}`

## Quickstart (Transcript Miner Tool)
Ziel: Ein **einziges** Open WebUI Tool „Transcript Miner“ (Transcripts holen, Runs starten, Summaries indexieren).
1. Shared Docker-Objekte provisionieren (Network + Volumes, einmalig): `./scripts/provision_ai_stack_docker_objects.sh`
2. Shared Secrets setzen: `.env.example` → `.env` (nicht committen).
3. Shared Config setzen (non-secret): `.config.env.example` → `.config.env` (nicht committen).
4. Service-Config setzen (non-secret): `mcp-transcript-miner/.config.env.example` → `mcp-transcript-miner/.config.env` (nicht committen).
5. Start (vom Repo-Root): `docker compose --env-file .env --env-file .config.env --env-file mcp-transcript-miner/.config.env -f mcp-transcript-miner/docker-compose.yml up -d --build` (Compose-Service: `tm`)
6. Einmalige Gemini-Auth im Container (wenn `TM_LLM_BACKEND=gemini_cli`): `docker exec -it tm gemini` (bei `gemini-3-flash-preview` muss in `~/.gemini/settings.json` `preview=true` gesetzt sein)
7. Timeout-Knobs (global): `transcript-miner/config/config_global.yaml` nutzt `youtube.api_timeout_s`, `analysis.llm.timeout_s` und `report.llm.timeout_s` jetzt wirksam im Laufzeitpfad.

## Quickstart (SEC EDGAR MCP)
Ziel: MCP Tool fuer SEC EDGAR Filings als **MCP Streamable HTTP** im Docker-Netzwerk (keine Host-Ports).
1. Shared Secrets setzen: `.env.example` → `.env` (nicht committen).
2. Shared Config setzen (non-secret): `.config.env.example` → `.config.env` (nicht committen).
3. Service-Config setzen (non-secret): `mcp-sec-edgar/.config.env.example` → `mcp-sec-edgar/.config.env` (nicht committen).
   - Pflicht: `SEC_EDGAR_USER_AGENT` (SEC Policy: User-Agent mit Contact Info).
4. Start (vom Repo-Root): `docker compose --env-file .env --env-file .config.env --env-file mcp-sec-edgar/.config.env -f mcp-sec-edgar/docker-compose.yml up -d`
5. In Open WebUI als External Tool (MCP Streamable HTTP) eintragen: `http://sec-edgar:9870/mcp`

## Investing-Test Workflow (Alpha)
Ziel: Prompt-Tuning/Schema-Iterationen **schnell und guenstig** mit kleiner Datenmenge.

1. Standard fuer Experimente: `transcript-miner/config/config_investing_test.yaml` (Topic: `investing_test`).
2. Run: `uv run python -m transcript_miner --config config/config_investing_test.yaml`
3. Erst wenn der Prompt/Schema-Stand validiert ist: auf `config_investing.yaml` wechseln.
4. Optionaler Reset fuer das Test-Topic (z. B. vor einem Clean-Slate): `OPEN_WEBUI_API_KEY=... ./scripts/purge_topic_data.sh investing_test --force`
5. Prompt-Engineering Fixture (10 letzte Paare Transcript/Summary old/new): `transcript-miner/tests/prompt-engineering/`  
   - Generator: `transcript-miner/tests/prompt-engineering/_build_prompt_engineering_fixture.sh`  
   - Enthalten: `_goals.md`, `_promptold.md`, `_promptnew.md`, `_manifest.json` sowie `<video_id>_transcript.md`, `<video_id>_sumold.md`, `<video_id>_sumnew.md`.
   - Aktueller produktiver Summary-Prompt (investing + investing_test) ist auf `_promptnew.md` ausgerichtet.
   - Wichtig: Persistierte Summaries unter `output/data/summaries/by_video_id/*.summary.md` speichern jetzt den Prompt-Output direkt (z. B. `<<<DOC_START>>>...<<<DOC_END>>>`), ohne nachtraegliche Umschreibung.
   - Zeitkontext: Der LLM-User-Prompt enthaelt jetzt immer aktuelle Referenzzeit (`utc_now`, `vienna_now`) plus Recency-Regel, damit die Antwort das Alter der Quellen explizit einordnen kann.

## Company Dossier Agent (neu)
- Eigene Config: `transcript-miner/config/config_investing_companies.yaml`
- Zweck: company-spezifische **Dossier-Deltas** (Business Model, Risks, Numbers, Evidence) aus den neuesten Videos extrahieren.
- Laufgrenzen: aktuell `max_videos_per_channel=2`, `lookback_days=15`.
- Start via MCP-Container: `./scripts/run-tm-investing-companies.sh`
- Sync-Topic in OWUI: `company_dossiers`

## Investing Collections Lifecycle
- Ziel-Collections (Investing): `investing_new`, `investing_archive`
- Rotation: `investing_new` hält pro Channel max. 2 neueste Videos (zusätzlich optional begrenzt über `owui_collections.new_max_age_days`); Rest (bis 15 Tage alt) liegt in `investing_archive`.
- Älter als Archive-Fenster: Summary-Dateien werden automatisch nach `output/data/summaries/cold/by_video_id/` verschoben (leicht rückverschiebbar per `mv`).
- Trigger: `./scripts/sync-investing-lifecycle.sh` (reconciled beide Collections aus Source-Topic `investing`: add/move/remove ohne Delete+Recreate, damit Knowledge-IDs und OWUI-Folder-Bindings stabil bleiben).
- Download-unabhaengige Maintenance (neu): `./scripts/maintain-investing-lifecycle.sh ensure` (Lifecycle-Sweep + Freshness-Guard).
- `ensure` beinhaltet zudem einen Orphan-Prune (stale hot summaries ohne aktuellen investing-Index-Eintrag -> `cold`).
- Sync-Schutz: parallele `POST /sync/topic/investing`-Aufrufe werden serverseitig fuer dasselbe Topic geblockt (`status=busy`), um Race-Condition-Duplikate zu verhindern.
- Dedupe-Precheck vor Upload ist standardmaessig aktiv (`OPEN_WEBUI_KNOWLEDGE_DEDUP_PRECHECK=true`).
- Runbook: `docs/runbooks/runbook-tm-lifecycle-maintenance.md:1`

## Scheduled Runs (investing, alle 3h)
Systemd Timer für automatische Runs inkl. Sync (Lifecycle-Routing):
1. `scripts/run-tm-investing.sh` startet den Run und ruft danach `POST /sync/topic/investing` (-> `investing_new` + `investing_archive`).
2. Install:
   - `sudo cp /home/wasti/ai_stack/scripts/systemd/ai-stack-tm-investing.service /etc/systemd/system/`
   - `sudo cp /home/wasti/ai_stack/scripts/systemd/ai-stack-tm-investing.timer /etc/systemd/system/`
   - `sudo systemctl daemon-reload`
   - `sudo systemctl enable --now ai-stack-tm-investing.timer`
3. Status: `systemctl status ai-stack-tm-investing.timer`

## Scheduled Runs (company dossiers, taeglich)
Systemd Timer fuer den Company Dossier Agent (Run + Sync Topic `company_dossiers`):
1. `scripts/run-tm-investing-companies.sh` startet den Run (Config `config_investing_companies.yaml`) und ruft danach `POST /sync/topic/company_dossiers`.
2. Install:
   - `sudo cp /home/wasti/ai_stack/scripts/systemd/ai-stack-tm-company-dossiers.service /etc/systemd/system/`
   - `sudo cp /home/wasti/ai_stack/scripts/systemd/ai-stack-tm-company-dossiers.timer /etc/systemd/system/`
   - `sudo systemctl daemon-reload`
   - `sudo systemctl enable --now ai-stack-tm-company-dossiers.timer`
3. Status: `systemctl status ai-stack-tm-company-dossiers.timer`

## Scheduled Maintenance (investing lifecycle, taeglich)
Systemd Timer fuer Cleanup/Rotation ohne neue Downloads:
1. `scripts/maintain-investing-lifecycle.sh ensure` fuehrt Lifecycle-Sync und danach den Freshness-Guard aus.
2. Install:
   - `sudo cp /home/wasti/ai_stack/scripts/systemd/ai-stack-tm-investing-maintenance.service /etc/systemd/system/`
   - `sudo cp /home/wasti/ai_stack/scripts/systemd/ai-stack-tm-investing-maintenance.timer /etc/systemd/system/`
   - `sudo systemctl daemon-reload`
   - `sudo systemctl enable --now ai-stack-tm-investing-maintenance.timer`
3. Status: `systemctl status ai-stack-tm-investing-maintenance.timer`

## Cost Control: Schedules pausieren (ohne sudo)
Wenn API-Kosten explodieren: Kill-Switch setzen. Dann laufen Timer zwar weiter, aber die ai_stack Run-/Backup-Skripte beenden sofort (keine Runs, kein Sync, keine API-Calls).
Hinweis: Der separate Lifecycle-Maintenance-Job (`maintain-investing-lifecycle.sh`) bleibt davon absichtlich unberuehrt.

Disable:
- `mkdir -p "${XDG_STATE_HOME:-$HOME/.local/state}/ai_stack"`
- `touch "${XDG_STATE_HOME:-$HOME/.local/state}/ai_stack/schedulers.disabled"`

Enable wieder:
- `rm -f "${XDG_STATE_HOME:-$HOME/.local/state}/ai_stack/schedulers.disabled"`

Optional (mit sudo): Timer wirklich deaktivieren:
- `sudo systemctl disable --now ai-stack-tm-investing.timer ai-stack-tm-company-dossiers.timer ai_stack_backup.timer`

## Gemini CLI Backend (Summaries)
- Status: produktiv fuer Summary-Generierung in Transcript Miner (`TM_LLM_BACKEND=gemini_cli`).
- Modell-Policy: `google/gemini-3-flash-preview` (normalisiert auf `gemini-3-flash-preview`), Pro-Modelle im Runner geblockt, no-thinking per Prompt-Policy.
- Auth: bevorzugt Gemini-Account-Auth via `~/.gemini/settings.json`; fuer `gemini-3-flash-preview` muss `preview=true` gesetzt sein (`GEMINI_API_KEY` nur Fallback).
- Scheduler-Default: `scripts/run-tm-investing.sh` und `scripts/run-tm-investing-companies.sh` starten Runs ohne erzwungenes `skip_report`; Report-Backend folgt `TM_LLM_BACKEND` (z. B. `gemini_cli`).
- POC-Utility bleibt fuer Schnelltests verfuegbar: `./scripts/run-gemini-cli-summary-poc.sh` (schreibt `*.usage.json` mit Token-/API-Stats).

Diagnose-Scripts (Transcript Miner):
- Cookie-Load + Transcript-Request: `transcript-miner/tools/repro_cookie_load.py`
- IP-Block-Repro: `transcript-miner/tools/repro_ip_block.py`
- Manueller Re-Sync (Lifecycle): `docker exec tm python -c "import requests; print(requests.post('http://127.0.0.1:8000/sync/topic/investing', json={}, timeout=900).text)"`

## Quickstart (Watchdog)
Ziel: Lightweight Monitoring fuer CPU/Temperatur/Disk (Host) plus Docker-Hygiene.
Status: **reaktiviert seit 2026-02-15 im Monitoring-only Modus** (kein Auto-Stop per Default).
1. Shared Secrets setzen: `.env.example` -> `.env` (nicht noetig fuer Watchdog, aber konsistent).
2. Shared Config setzen (non-secret): `.config.env.example` -> `.config.env` (optional).
3. Service-Config setzen (non-secret): `watchdog/.config.env.example` -> `watchdog/.config.env` (gitignored).
   - Hinweis: Monitoring-only ist der Default (`WATCHDOG_TEMP_STOP_CONTAINER_NAMES=` leer). Auto-Stop ist nur aktiv, wenn Container-Namen explizit gesetzt sind (z. B. `owui`).
4. Start (vom Repo-Root): `docker compose --env-file .env --env-file .config.env --env-file watchdog/.config.env -f watchdog/docker-compose.yml up -d --build`

## Quickstart (OpenClaw)
Ziel: OpenClaw Gateway host-native betreiben (Telegram Channel) und stabil halten, ohne `sudo`/`systemd --user`.
- Einstieg: `openclaw/README.md:1`
- Ops/Recovery: `openclaw/OPERATIONS.md:1`
- Health: `openclaw gateway probe`
- Persistenz (Cron): `./scripts/install_openclaw_gateway_cron.sh`
- Update-Guard (kein kaputter systemd-user Restart nach `openclaw update`): `./scripts/install_openclaw_update_guard_bash.sh`

## Smoke Test (P0)
- Runbook: `docs/runbooks/runbook_smoke_test.md:1`
- Script: `./scripts/smoke_test_ai_stack.sh --up --build`
- Reindex (Embedding-Model-Wechsel): `docs/runbooks/runbook_openwebui_reindex_knowledge.md:1`

## Markdown Lint
- Baseline-Lint fuer Markdown: `./scripts/lint-markdown.sh`
- Tooling: `markdownlint-cli2` via `npx` (keine globale Installation noetig)
- Konfiguration: `.markdownlint-cli2.yaml` (inkl. Baseline-Ignores fuer generated/append-only Bereiche)

## Finance Fourier Analysis (POC)
- Ziel: Explorative Zyklusanalyse fuer Yahoo/FRED Zeitreihen mit reproduzierbaren Artefakten.
- Script: `./scripts/finance_fourier_analysis.py`
- Beispiele:
  - `./scripts/finance_fourier_analysis.py --source yahoo --symbol SPY --yahoo-range 5y --max-points 512 --top-k 8`
  - `./scripts/finance_fourier_analysis.py --source fred --series-id DGS10 --max-points 512 --top-k 8`
- Runbook: `docs/runbooks/runbook_finance_fourier.md:1`

## Quickstart (Fourier Cycles Docker)
Ziel: Dockerisierter Batch-Job fuer Yahoo+FRED inklusive Rolling-Stability-Checks und PNG-Artefakten fuer Telegram.
1. Shared Secrets setzen: `.env.example` -> `.env` (nur wenn weitere Provider-Keys noetig sind; fuer Yahoo/FRED selbst kein Key erforderlich).
2. Shared Config setzen (non-secret): `.config.env.example` -> `.config.env`.
3. Service-Config setzen (non-secret): `fourier-cycles/.config.env.example` -> `fourier-cycles/.config.env`.
4. Run (vom Repo-Root):
   - `docker compose --env-file .env --env-file .config.env --env-file fourier-cycles/.config.env -f fourier-cycles/docker-compose.yml run --rm fourier-cycles`
5. Ergebnis: Artefakte unter `${FOURIER_OUTPUT_DIR_HOST}` (Default: `/home/wasti/ai_stack/fourier-cycles/output`); `latest` zeigt auf den letzten Lauf.
- Ops/Details: `fourier-cycles/README.md:1`

## Codex Remote-SSH Auth Guard (DNS)
- Hintergrund: VS Code Codex Login kann scheitern, wenn Tailscale DNS Override (`accept-dns=true`) auf einen instabilen Resolver zeigt.
- Check: `./scripts/check_codex_auth_dns.sh`
- Remediation: `./scripts/remediate_codex_auth_dns.sh --reason manual`
- Persistenter Guard (`@reboot` + alle 10 Minuten): `./scripts/install_codex_auth_dns_guard_cron.sh`
- Runbook: `docs/runbooks/runbook_codex_ssh_auth_dns_guard.md:1`

## Monitoring (Plan)
- Watchdog-Ideen (CPU/Temp/Disk): `docs/plans/plan_watchdog_monitoring.md`

## Open WebUI External Tools (Import JSON)
- Context7 (MCP Streamable HTTP): `open-webui/tool-imports/tool_import_context7.json`
- Transcript Miner (MCP Streamable HTTP): `open-webui/tool-imports/tool_import_transcript_miner_mcp.json`
- context6 (MCP Streamable HTTP): `open-webui/tool-imports/tool_import_context6.json`

## Workflow-Zielbilder
- Open WebUI Tool-Workflow: „hole die neuesten videos“ → TranscriptMiner → Knowledge: `docs/plans/prd-tool-owui-transcript-miner-sync.md:1`

## Private GitHub Repos (SSH)
Wenn wir private Repos (z. B. TranscriptMiner) verwenden, muss **SSH-Zugriff** auf deinem Host für GitHub eingerichtet sein.
- SSH-Test: `ssh -T git@github.com`
- Branches listen: `git ls-remote --heads git@github.com:<owner>/<repo>.git`
- Default-Branch (HEAD): `git ls-remote --symref git@github.com:<owner>/<repo>.git HEAD`

## Repo-Struktur
- `AGENTS.md` — Arbeitsregeln für Coding Agents
- `INDEX.md` — Reiner Link-Index (Startpunkt für Navigation)
- `HANDOFF.md` — Reset-sichere Uebergabe (aktueller Stand + Schnellstart nach Context Reset)
- `docs/` — Doku-Index (Link-Netzwerk)
- `goals/build_app.md` — Ausfuellbare 5+2 Context-Engineering Vorlage fuer neue Projekte
- `skills/` — Projekt-spezifische Codex Skills (Workflows/Checks)
- `skills/codex-mcp-self-config/` — Codex MCP Server (self) in `.codex/config.toml` upserten + Projekt-Trust in `~/.codex/config.toml`
- `skills/owui-prompt-debug-loop/` — Prompt-Debug/PDCA fuer Open WebUI (Model/Folder/RAG) via debug-proxy + webui.db
- `skills/owui-prompt-api-loop/` — Prompt-Test via Open WebUI API + Flow-Report (debug-proxy)
- `emb-bench/` — Embedding Benchmark Suite (MRL + Local vs OpenRouter)
- `mcp-context6/` — context6 MCP Server (Doku-Fetch/Index/Search)
- `mcp-owui-connector/` — Open WebUI Connector (MCP Tools fuer Knowledge/Admin APIs; fuer Roo/OpenClaw)
- `openclaw/` — OpenClaw Gateway (host-native Betrieb)
- `open-webui/` — Open WebUI (Compose, Secrets, README)
- `mcp-transcript-miner/` — **Transcript Miner** MCP Server (Configs/Runs/Outputs + Knowledge Indexing)
- `transcript-miner/` — TranscriptMiner Pipeline-Engine (Python; Transcripts + Summaries)
- `debug-proxy/` — MITM Debug Proxy (JSONL Request Logs, optional)
- `qdrant/` — Qdrant (optional)
- `fourier-cycles/` — Dockerisierter Fourier-Cycle Batch-Job (Yahoo + FRED)
- `watchdog/` — Monitoring-Watchdog (CPU/Temperatur/Disk + Docker-Hygiene)

## Security (Kurz)
- Secrets liegen in `.env` (gitignored, secrets-only). Non-Secrets liegen in `.config.env` + `<service>/.config.env` (gitignored). Policy: `docs/policies/policy_secrets_environment_variables_ai_stack.md:1`.

## Nicht-Ziele (Phase 1)
- Kein Reverse Proxy / kein öffentliches TLS-Setup / keine öffentliche Exponierung ins Internet
- Kein HA/Scaling/Queue-Mode
