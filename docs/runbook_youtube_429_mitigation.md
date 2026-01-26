# Runbook — YouTube Transcript 429 Mitigation

Ziel: Reproduzierbar testen, ob der Transcript-Endpoint geblockt ist, und eine klare
Mitigation-Strategie (Netz/Cookies/Proxy) anwenden.

Scope: Transcript Miner (`transcript-miner`) und Tool-Server (`mcp-transcript-miner`).

## Kurzfassung (Entscheidungsbaum)
1) **Single-Probe** liefert 429 → IP-/Reputation-Block wahrscheinlich.  
   → **Netzwechsel** oder **Residential Proxy** testen.
2) **Single-Probe** ok, aber Runs brechen später → Delays/Jitter erhöhen, Retries begrenzen.
3) **Cookies** nur wenn nötig (Fallback), da privacy-/Account-Risiko.

## Voraussetzungen
- Repo-Root: `/home/wasti/ai_stack`
- Tool: `transcript-miner/tools/youtube_block_probe.py`
- Config: `transcript-miner/config/config_investing.yaml` (oder `config_wsl_optimized.yaml`)
- Optional: `youtube_cookies.txt` (gitignored) unter Repo-Root
- Optional: Proxy-Secrets in `.env` (siehe `.env.example`)
- Proxy-Mode (non-secret) in `.config.env`:
  - `YOUTUBE_PROXY_MODE=none|generic|webshare`
  - `YOUTUBE_PROXY_FILTER_IP_LOCATIONS=de,at`

## Tests (reproduzierbar)

### T0 — Single-Probe (Baseline)
Ziel: Ein einzelner Request ohne Cookies/Proxy.

```bash
uv run python transcript-miner/tools/youtube_block_probe.py \
  --config transcript-miner/config/config_investing.yaml \
  --videos jNQXAC9IVRw \
  --min-delay-s 0 --jitter-s 0 --max-retries 0 --repeat 1
```

Erwartung:
- **429** → IP-/Reputation-Block sehr wahrscheinlich.
- **OK** → weiter mit T1/T2 nur bei Bedarf.

### T1 — Conservative Delays (WSL/VPN-Setup)
Ziel: Test mit konservativen Delays.

```bash
uv run python transcript-miner/tools/youtube_block_probe.py \
  --config transcript-miner/config/config_wsl_optimized.yaml \
  --videos jNQXAC9IVRw \
  --repeat 1
```

### T2 — Cookies (Fallback)
Nur wenn T0/T1 blocken.  
Lege `youtube_cookies.txt` unter Repo-Root ab (gitignored).

Erzeuge temporäre Config (lokal, nicht committen):
```bash
cp transcript-miner/config/config_investing.yaml /tmp/config_investing_cookies.yaml
```

In `/tmp/config_investing_cookies.yaml`:
```
api:
  youtube_cookies: /host_secrets/youtube_cookies.txt
```

Probe:
```bash
uv run python transcript-miner/tools/youtube_block_probe.py \
  --config /tmp/config_investing_cookies.yaml \
  --videos jNQXAC9IVRw \
  --repeat 1
```

### T3 — Proxy (empfohlen bei 429)
Setze in `.config.env`:
```
YOUTUBE_PROXY_MODE=webshare
YOUTUBE_PROXY_FILTER_IP_LOCATIONS=de,at
```

Setze in `.env` (Secrets):
```
WEBSHARE_USERNAME=...
WEBSHARE_PASSWORD=...
```

Probe (wie T0).

## Mitigation-Strategie (priorisiert)
1) **Residential Proxy (Webshare)** — funktioniert im Test  
2) **Netzwechsel** (Hotspot / anderes WAN)  
3) **Cookies** (nur wenn nötig; Account-Risiko beachten)

## Hinweise
- Bei **Single-Probe 429** sind Retries meist nutzlos → Wechsel der IP ist der Hebel.
- `config_wsl_optimized.yaml` ist das konservative Default-Profil für blockanfällige Umgebungen.
