# Open WebUI RAG Baseline Report

- generated_at_utc: `2026-02-15T00:00:30+00:00`
- base_url: `https://owui.tail027324.ts.net`
- model: `google/gemini-3-flash-preview`
- query_matrix: `config/owui_rag_baseline_queries.json`
- total_queries: `2`
- ok_done: `2`
- failed_or_incomplete: `0`

## Summary

| id | status | latency_ms | chunks | done | tool_calls | total_tokens | preview |
| --- | --- | --- | --- | --- | --- | --- |
| `health_ok` | `200` | `2352` | `3` | `true` | `0` | `3010` | OK |
| `day_sensitive_hot_list` | `200` | `2887` | `4` | `true` | `1` | `3105` |  |

## Details

### `health_ok`
- focus: `API transport, model path, SSE parsing`
- endpoint: `/api/chat/completions`
- status: `200`
- latency_ms: `2352`
- chunks: `3`
- done: `true`
- tool_call_count: `0`
- prompt_tokens: `2937`
- completion_tokens: `73`
- total_tokens: `3010`
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
- latency_ms: `2887`
- chunks: `4`
- done: `true`
- tool_call_count: `1`
- tool_call_names: `search_web`
- prompt_tokens: `2952`
- completion_tokens: `153`
- total_tokens: `3105`
- query:
```text
Nenne mir heute die 3 heißesten Aktien-Chancen aus den neuesten Videos.
```
- response:
```text

```
