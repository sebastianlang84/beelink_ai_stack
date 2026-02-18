# Open WebUI RAG Baseline Report

- generated_at_utc: `2026-02-14T23:59:54+00:00`
- base_url: `http://127.0.0.1:3000`
- model: `google/gemini-3-flash-preview`
- query_matrix: `config/owui_rag_baseline_queries.json`
- total_queries: `5`
- ok_done: `5`
- failed_or_incomplete: `0`

## Summary

| id | status | latency_ms | chunks | done | tool_calls | total_tokens | preview |
| --- | --- | --- | --- | --- | --- | --- |
| `health_ok` | `200` | `2593` | `3` | `true` | `0` | `3018` | OK |
| `day_sensitive_hot_list` | `200` | `3199` | `4` | `true` | `1` | `3127` |  |
| `stocks_topic_isolation` | `200` | `11004` | `6` | `true` | `2` | `2504` |  |
| `macro_topic_isolation` | `200` | `4369` | `6` | `true` | `3` | `2389` |  |
| `crypto_topic_isolation` | `200` | `9548` | `17` | `true` | `0` | `3271` | Die Krypto-Landschaft wird derzeit von einer Mischung aus institutioneller Adaption und technologischen Nischen-Trends dominiert. Hier sind die aktuell wichtigsten Narrative:  ### 1. Bitcoin: Die "Institutionelle Ära" & ... |

## Details

### `health_ok`
- focus: `API transport, model path, SSE parsing`
- endpoint: `/api/chat/completions`
- status: `200`
- latency_ms: `2593`
- chunks: `3`
- done: `true`
- tool_call_count: `0`
- prompt_tokens: `2937`
- completion_tokens: `81`
- total_tokens: `3018`
- query:
```text
Sag nur OK
```
- response:
```text
OK
```

### `day_sensitive_hot_list`
- focus: `same-day sufficiency gate behavior`
- endpoint: `/api/chat/completions`
- status: `200`
- latency_ms: `3199`
- chunks: `4`
- done: `true`
- tool_call_count: `1`
- tool_call_names: `get_current_timestamp`
- prompt_tokens: `2952`
- completion_tokens: `175`
- total_tokens: `3127`
- query:
```text
Nenne mir heute die 3 heißesten Aktien-Chancen aus den neuesten Videos.
```
- response:
```text

```

### `stocks_topic_isolation`
- focus: `stocks retrieval quality and drift`
- endpoint: `/api/chat/completions`
- status: `200`
- latency_ms: `11004`
- chunks: `6`
- done: `true`
- tool_call_count: `2`
- tool_call_names: `search_chats, search_knowledge_files`
- prompt_tokens: `2028`
- completion_tokens: `476`
- total_tokens: `2504`
- query:
```text
Welche 5 Aktien waren im Fokus und was ist jeweils die zentrale Thesis?
```
- response:
```text

```

### `macro_topic_isolation`
- focus: `macro retrieval quality and drift`
- endpoint: `/api/chat/completions`
- status: `200`
- latency_ms: `4369`
- chunks: `6`
- done: `true`
- tool_call_count: `3`
- tool_call_names: `query_knowledge_bases, search_chats, search_notes`
- prompt_tokens: `2027`
- completion_tokens: `362`
- total_tokens: `2389`
- query:
```text
Welche Macro-Themen dominieren aktuell laut den Zusammenfassungen?
```
- response:
```text

```

### `crypto_topic_isolation`
- focus: `crypto retrieval quality and drift`
- endpoint: `/api/chat/completions`
- status: `200`
- latency_ms: `9548`
- chunks: `17`
- done: `true`
- tool_call_count: `0`
- prompt_tokens: `2026`
- completion_tokens: `1245`
- total_tokens: `3271`
- query:
```text
Welche Bitcoin- oder Krypto-Narrative sind aktuell relevant?
```
- response:
```text
Die Krypto-Landschaft wird derzeit von einer Mischung aus institutioneller Adaption und technologischen Nischen-Trends dominiert. Hier sind die aktuell wichtigsten Narrative:

### 1. Bitcoin: Die "Institutionelle Ära" & Layer 2s
Bitcoin hat sich vom reinen "digitalen Gold" zu einer Plattform entwickelt.
*   **Spot ETFs:** Der massive Zufluss von institutionellem Kapital (BlackRock, Fidelity) legitimiert BTC als Assetklasse.
*   **BTC Layer 2 & Runes:** Projekte wie Stacks oder das Runes-Protokoll versuchen, DeFi und Smart Contracts direkt auf oder nah an Bitcoin zu bringen (ähnlich wie bei Ethereum).

### 2. Real World Assets (RWA)
Dieses Narrativ gilt als eines der stabilsten für diesen Zyklus.
*   **Tokenisierung:** Traditionelle Vermögenswerte (Staatsanleihen, Immobilien, Gold) werden auf die Blockchain gebracht. 
*   **Treiber:** BlackRocks Einstieg mit dem "BUIDL"-Fonds hat dieses Thema massiv beschleunigt. Es geht um Effizienzgewinne im klassischen Finanzwesen.

### 3. KI & DePIN
Die Verschmelzung von Künstlicher Intelligenz und Blockchain.
*   **KI-Infrastruktur:** Dezentrale Rechenleistung (z. B. Render, Akash) oder dezentrale Datenmodelle (z. B. Bittensor).
*   **DePIN (Decentralized Physical Infrastructure Networks):** Nutzer stellen physische Ressourcen (WLAN, Speicher, Sensoren) bereit und werden in Token belohnt (z. B. Helium, Hivemapper).

### 4. Solana-Ökosystem & Memecoins
Solana hat sich als die "Retail-Chain" etabliert.
*   **Geschwindigkeit & Kosten:** Durch niedrige Gebühren ist Solana der Hauptplatz für spekulatives Kapital und neue Nutzer.
*   **Memecoin-Kultur:** Auch wenn hochriskant, ziehen Memecoins (wie WIF, BONK, POPCAT) enorme Liquidität an und dienen als Marketing-Einstieg für das Netzwerk.

### 5. Restaking & Modularität
Technische Optimierungen der Infrastruktur, primär im Ethereum-Umfeld.
*   **EigenLayer (Restaking):** Bereits gestakte ETH werden genutzt, um weitere Dienste abzusichern, was zusätzliche Rendite ("Yield") verspricht.
*   **Modulare Blockchains:** Aufteilung von Aufgaben (Datenverfügbarkeit, Ausführung) auf verschiedene Ketten (z. B. Celestia), um die Skalierbarkeit massiv zu erhöhen.

### 6. Layer 2 Kriege (L2s)
Der Wettbewerb unter Ethereums Skalierungslösungen.
*   Fokus auf **Base** (Coinbase), **Arbitrum** und **Optimism**. Hier findet aktuell die meiste On-Chain-Aktivität statt, da die Gebühren durch das Dencun-Upgrade drastisch gesunken sind.

---

**Nächste Schritte:**
*   **Für Stabilität:** Fokus auf BTC/ETH und RWA-Projekte.
*   **Für Risiko/Rendite:** Fokus auf das Solana-Ökosystem oder KI-Token.
*   **Tool-Tipp:** Nutze Plattformen wie *Dune Analytics* oder *Coingecko (Categories)*, um zu sehen, in welche dieser Narrative aktuell das meiste Volumen fließt.
```
