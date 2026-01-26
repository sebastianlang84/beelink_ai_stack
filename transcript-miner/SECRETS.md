# transcript-miner — Secrets (ohne Werte)

Die Pipeline („transcript-miner“) wird typischerweise indirekt über den Tool-Server (`mcp-transcript-miner`) genutzt. Falls du sie separat mit Env-Files startest:

- Secrets: `/home/wasti/ai_stack/.env` (shared)
  - `YOUTUBE_API_KEY`
  - `OPENROUTER_API_KEY`
  - `WEBSHARE_USERNAME` (optional, falls Proxy genutzt wird)
  - `WEBSHARE_PASSWORD` (optional, falls Proxy genutzt wird)
  - `YOUTUBE_PROXY_HTTP_URL` / `YOUTUBE_PROXY_HTTPS_URL` (optional, falls Generic Proxy mit Credentials)
