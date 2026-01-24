# Report: YouTube Transcript Block (429)

Stand: 2026-01-24

## Kurzfassung
Transcript-Requests schlagen auf dem Host bereits bei einem einzelnen Video mit HTTP 429 (Too Many Requests) fehl. Damit sind Runs blockiert, bis die IP-Reputation wieder reicht oder ein alternativer Zugriff genutzt wird (Cookies/Residential Proxy/anderes Netz).

## Repro (minimal)
- Tool: `transcript-miner/tools/youtube_block_probe.py`
- Ein einzelner Request (1 Video, 1 Versuch) -> Status `blocked`

Beispiel (im Container `tm`):
```
python /transcript_miner_repo/tools/youtube_block_probe.py \
  --config /transcript_miner_config/config_stocks_crypto.yaml \
  --videos jNQXAC9IVRw \
  --min-delay-s 0 --jitter-s 0 --max-retries 0 --repeat 1
```

## Beobachtung
- Fehler: `HTTP 429 Too Many Requests`
- Endpoint: `https://www.youtube.com/api/timedtext?...`
- Log: `YouTube request failed` / `Could not retrieve a transcript`

## Aktuelle Umgebung
- Transcript Miner laeuft im Container `tm`
- Config: `config_stocks_crypto.yaml`
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

## Offene Fragen fuer Experten
- Bekannte Workarounds/Headers fuer `youtube_transcript_api` bei 429?
- Empfohlene Proxy-Settings / Cookie-Strategie mit hoher Erfolgsrate?
- Typisches Reset-Fenster fuer den Transcript-Endpoint?
