# mcp-sec-edgar

Runs the `mcp/sec-edgar` MCP server (SEC EDGAR filings) as **MCP Streamable HTTP** inside the shared Docker network `ai-stack`.

## Quickstart
1. Configure non-secrets: `mcp-sec-edgar/.config.env.example` -> `mcp-sec-edgar/.config.env`
   - Set `SEC_EDGAR_USER_AGENT` (required by SEC; include contact info).
2. Start:

```bash
docker compose --env-file .env --env-file .config.env --env-file mcp-sec-edgar/.config.env -f mcp-sec-edgar/docker-compose.yml up -d
```

## Open WebUI Integration
- Add as External Tool (MCP Streamable HTTP)
- URL (from inside Docker network): `http://sec-edgar:9870/mcp`

## Notes
- No host ports are exposed by default; access is internal to the Docker network.
