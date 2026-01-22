# ai_stack — Home-Server Automation

Dieses Repository enthält die „source of truth“ für ein **privates** Home-Server Setup (kein öffentliches Produkt, kein Business-Deployment).

Dokunetz: Einstieg über `docs/README.md:1`.

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

## Quickstart (Transcript Miner Tool)
Ziel: Ein **einziges** Open WebUI Tool „Transcript Miner“ (Transcripts holen, Runs starten, Summaries indexieren).
1. Shared Docker-Objekte provisionieren (Network + Volumes, einmalig): `./scripts/provision_ai_stack_docker_objects.sh`
2. Shared Secrets setzen: `.env.example` → `.env` (nicht committen).
3. Shared Config setzen (non-secret): `.config.env.example` → `.config.env` (nicht committen).
4. Service-Config setzen (non-secret): `mcp-transcript-miner/.config.env.example` → `mcp-transcript-miner/.config.env` (nicht committen).
5. Start (vom Repo-Root): `docker compose --env-file .env --env-file .config.env --env-file mcp-transcript-miner/.config.env -f mcp-transcript-miner/docker-compose.yml up -d --build` (Compose-Service: `tm`)

## Smoke Test (P0)
- Runbook: `docs/runbook_smoke_test.md:1`
- Script: `./scripts/smoke_test_ai_stack.sh --up --build`

## Open WebUI External Tools (Import JSON)
- Context7 (MCP Streamable HTTP): `open-webui/tool-imports/tool_import_context7.json`
- Transcript Miner (MCP Streamable HTTP): `open-webui/tool-imports/tool_import_transcript_miner_mcp.json`
- context6 (MCP Streamable HTTP): `open-webui/tool-imports/tool_import_context6.json`

## Workflow-Zielbilder
- Open WebUI Tool-Workflow: „hole die neuesten videos“ → TranscriptMiner → Knowledge: `docs/workflow_openwebui_hole_neueste_videos.md:1`

## Private GitHub Repos (SSH)
Wenn wir private Repos (z. B. TranscriptMiner) verwenden, muss **SSH-Zugriff** auf deinem Host für GitHub eingerichtet sein.
- SSH-Test: `ssh -T git@github.com`
- Branches listen: `git ls-remote --heads git@github.com:<owner>/<repo>.git`
- Default-Branch (HEAD): `git ls-remote --symref git@github.com:<owner>/<repo>.git HEAD`

## Repo-Struktur
- `AGENTS.md` — Arbeitsregeln für Coding Agents
- `docs/` — Doku-Index (Link-Netzwerk)
- `skills/` — Projekt-spezifische Codex Skills (Workflows/Checks)
- `emb-bench/` — Embedding Benchmark Suite (MRL + Local vs OpenRouter)
- `mcp-context6/` — context6 MCP Server (Doku-Fetch/Index/Search)
- `mcp-owui-roo-connector/` — MCP Connector (Open WebUI)
- `open-webui/` — Open WebUI (Compose, Secrets, README)
- `mcp-transcript-miner/` — **Transcript Miner** MCP Server (Configs/Runs/Outputs + Knowledge Indexing)
- `transcript-miner/` — TranscriptMiner Pipeline-Engine (Python; Transcripts + Summaries)
- `qdrant/` — Qdrant (optional)

## Security (Kurz)
- Secrets liegen in `.env` (gitignored, secrets-only). Non-Secrets liegen in `.config.env` + `<service>/.config.env` (gitignored). Policy: `docs/policy_secrets_environment_variables_ai_stack.md:1`.

## Nicht-Ziele (Phase 1)
- Kein Reverse Proxy / kein öffentliches TLS-Setup / keine öffentliche Exponierung ins Internet
- Kein HA/Scaling/Queue-Mode
