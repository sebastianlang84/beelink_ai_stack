# Plan: Lösung des IP-Block Problems (v2 - Refined) - IMPLEMENTIERT

## Status: Implementiert (2025-12-28)

Die in diesem Plan beschriebenen Maßnahmen wurden erfolgreich umgesetzt und durch zusätzliche Features (Sticky Sessions) erweitert.

### A) Global Rate Limiting (Pre-Request) - [x]
- Implementiert in [`src/transcript_miner/transcript_downloader.py`](../../src/transcript_miner/transcript_downloader.py:1).
- Konfigurierbar via YAML.

### B) Backoff & Circuit Breaker - [x]
- Exponentieller Backoff bei 429 Fehlern implementiert.
- Circuit Breaker bricht bei `IpBlocked` sofort ab, um die IP-Reputation zu schützen.

### C) Native Proxy-Unterstützung - [x]
- Unterstützung für `generic` und `webshare` Modi.
- **Neu:** Sticky Sessions für Webshare (IP-Stabilität pro Video).
- **Neu:** Länder-Filter (`filter_ip_locations`).

### D) Cookie-freier Betrieb (Default) - [x]
- Status: Default-Profil nutzt keine Cookies (`youtube_cookies: null`).
- Empfehlung: konservative Delays über [`config/config_wsl_optimized.yaml`](../../config/config_wsl_optimized.yaml:1).

### E) User-Agent - [x]
- Moderner Chrome User-Agent wird standardmäßig verwendet.

## 4. Mermaid Diagramm (Workflow) - Aktualisiert

```mermaid
graph TD
  A[Start Video] --> B{Already processed?}
  B -- Yes --> C[Skip]
  B -- No --> D[Global Rate Limit + Jitter (pre-request)]
  D --> E[Fetch transcript (proxy_config + optional headers)]
  E --> F{Result}
  F -- Success --> G[Save + Mark processed]
  F -- 429 Too Many Requests --> H[Backoff (Retry-After else exp) + retry]
  H --> E
  F -- IpBlocked/RequestBlocked --> I[Cooldown + Abort run / Pause queue]
  G --> J[Next video]
```
