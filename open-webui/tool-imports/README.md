# Open WebUI Tool Imports (Templates)

Ziel: Alle Import-JSON Templates für **Open WebUI → External Tools** liegen zentral und versioniert an einem Ort.

## Dateien
- `open-webui/tool-imports/tool_import_context7.json` — Context7 (MCP Streamable HTTP)
- `open-webui/tool-imports/tool_import_transcript_miner_mcp.json` — Transcript Miner (MCP Streamable HTTP)
- `open-webui/tool-imports/tool_import_context6.json` — context6 (MCP Streamable HTTP)

## Hinweise
- Die URLs sind Templates und müssen ggf. auf deine tatsächlichen Host-/Tailnet-URLs angepasst werden.
- Bevorzugt: MCP Tools statt OpenAPI (bessere Tool-Ergonomie/Discovery).
- Für Open WebUI 0.7.x muss pro Eintrag `config` vorhanden sein (mindestens `{}`), sonst kann `/api/v1/configs/tool_servers` mit `500` (Response Validation Error) fehlschlagen.

### context6 URL Varianten
- Docker-zu-Docker (empfohlen): `http://context6:8816/mcp` (Open WebUI und context6 im selben `ai_stack` Netzwerk)
- Host-Port (wenn `context6` nur localhost published ist): `http://host.docker.internal:8816/mcp`
- Tailnet HTTPS (wenn du Tailscale Serve davor hast): `https://<node>.<tailnet>.ts.net/mcp`
