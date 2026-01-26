# Report: YouTube Transcript Block (429)

Stand: 2026-01-24

## Kurzfassung
Transcript-Requests schlagen auf dem Host bereits bei einem einzelnen Video mit HTTP 429 (Too Many Requests) fehl. Damit sind Runs blockiert, bis die IP-Reputation wieder reicht oder ein alternativer Zugriff genutzt wird (Cookies/Residential Proxy/anderes Netz).

Runbook: `docs/runbook_youtube_429_mitigation.md`

## Repro (minimal)
- Tool: `transcript-miner/tools/youtube_block_probe.py`
- Ein einzelner Request (1 Video, 1 Versuch) -> Status `blocked`

Beispiel (im Container `tm`):
```
python /transcript_miner_repo/tools/youtube_block_probe.py \
  --config /transcript_miner_config/config_investing.yaml \
  --videos jNQXAC9IVRw \
  --min-delay-s 0 --jitter-s 0 --max-retries 0 --repeat 1
```

## Beobachtung
- Fehler: `HTTP 429 Too Many Requests`
- Endpoint: `https://www.youtube.com/api/timedtext?...`
- Log: `YouTube request failed` / `Could not retrieve a transcript`

## Aktuelle Umgebung
- Transcript Miner laeuft im Container `tm`
- Config: `config_investing.yaml`
- Cookies: deaktiviert
- Proxy: deaktiviert

## Wahrscheinliche Ursachen
- IP-Reputation zu niedrig (Datacenter/VPN/Cloud/WSL‑Typischer Block)
- Block betrifft den Transcript-Endpoint, nicht nur die Data API

## Optionen zur Entblockung
1) IP wechseln (anderes Netz/Hotspot)
2) Cookies nutzen (eingeloggte Session)
3) Residential Proxy (statt Datacenter Proxy)
4) Wartefenster (Reset nicht deterministisch; oft Stunden bis >24h)

## Einordnung: Warum 429 bereits beim 1. Request plausibel ist
Beim Endpoint `/api/timedtext` ist `429` in der Praxis oft kein klassisches “Rate-Limit pro Minute”,
sondern ein IP-Reputation/Anti-Bot Block (typisch bei Datacenter/VPN/low-reputation IPs).
Das wird auch in Issues/Erfahrungsberichten zur `youtube_transcript_api` so beschrieben.

Selbst Captions im Browser (DevTools) koennen bei blockierten IPs auf 429 laufen – also nicht zwingend
ein Skript-Problem, sondern ein IP-/Risk-Scoring-Thema.

## Workarounds (praktisch)
### A) Residential Proxy (rotierend)
Der stabilste Weg in der Praxis. Rotierende Residential IPs mit ausreichendem Pool und geo-naher Region
(AT/DE) reduzieren Block-Risiko.

### B) Eigene `requests.Session` + Header-Tuning
Moeglich ueber `youtube_transcript_api` (Custom Session). Hilft eher bei “soft limits”, bringt aber
wenig bei hart geblockter IP.

### C) Cookies (logged-in Session)
Aktuell sind Cookie-basierte Zugriffe in der `youtube_transcript_api` laut Doku/Issues unzuverlaessig.
Wenn Cookies notwendig sind, ist `yt-dlp` oft die robustere Route.

## Reset-Fenster / Cooldown
Kein offizielles Fenster. Praktisch:
- Soft Limit: Minuten bis Stunden
- IP-Reputation-Block: oft “bis IP-Wechsel”

Konsequenz: Wenn ein einzelner Request reproduzierbar `429` liefert, ist “warten + jitter” meist
ineffektiv. IP-Wechsel/Residential ist der Hebel.

## Alternativen zu `youtube_transcript_api`
### A) YouTube Data API v3 (Captions)
Meist owner-limitiert (nur eigene Videos). Fuer “beliebige Videos” selten nutzbar.

### B) `yt-dlp` als Fallback fuer Captions
Robust im Upstream. Oft mit frischen Browser-Cookies wirksam, aber privacy/Account-Risiko beachten.

### C) Drittanbieter APIs
Kommerziell moeglich, aber Kosten/Compliance/Abhaengigkeit beachten.

## Empfehlungen fuer Transcript Miner
- `blocked` als eigenes Failure-Mode behandeln (kein “kaputter Run”)
- Circuit Breaker: bei Block “Pause/Skip + Alert”
- Proxy-Mode als Standard-Mitigation vorsehen (off -> residential_rotating -> generic)
- Retries nur bei “soft limits”; bei single-probe 429 keine Retries

## Offene Fragen fuer Experten
- Bekannte Workarounds/Headers fuer `youtube_transcript_api` bei 429?
- Empfohlene Proxy-Settings / Cookie-Strategie mit hoher Erfolgsrate?
- Typisches Reset-Fenster fuer den Transcript-Endpoint?
