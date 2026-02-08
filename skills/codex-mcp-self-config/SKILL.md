---
name: codex-mcp-self-config
description: Configure OpenAI Codex MCP servers (VS Code extension/CLI) by adding/enabling entries in `.codex/config.toml` (project-scoped) or `~/.codex/config.toml` (global), ensuring the project is trusted, validating TOML, and reloading the extension. Use when asked to "add an MCP server", "enable MCP server", or when MCP servers like `context7`/`tavily` exist but a new local Streamable HTTP MCP URL should be added.
---

# Codex MCP Self-Config

## Goal

Make sure *Codex itself* (OpenAI Codex VS Code extension and CLI) can see a newly running MCP server under **MCP servers** and that it is enabled.

## Default Workflow (Streamable HTTP)

1. Verify the MCP endpoint is reachable (host-local):
```bash
curl -fsS http://127.0.0.1:8877/healthz
curl -fsS http://127.0.0.1:8877/mcp -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' >/dev/null
```

2. Upsert the server into the *project* Codex config and set it enabled:
```bash
python3 skills/codex-mcp-self-config/scripts/upsert_codex_mcp_server.py \
  --project-dir /home/wasti/ai_stack \
  --name owui-connector \
  --url http://127.0.0.1:8877/mcp \
  --enabled true \
  --ensure-trusted
```

This writes:
- project config: `/home/wasti/ai_stack/.codex/config.toml`
- optional trust entry (if missing): `~/.codex/config.toml` under `[projects."..."]`

3. Validate TOML quickly (parse + list MCP server keys):
```bash
python3 - <<'PY'
import tomllib
from pathlib import Path
p = Path("/home/wasti/ai_stack/.codex/config.toml")
obj = tomllib.loads(p.read_text(encoding="utf-8"))
print(sorted((obj.get("mcp_servers") or {}).keys()))
PY
```

4. Reload the Codex extension:
- VS Code: `Developer: Reload Window`, or on the MCP Settings page click `Restart extension`.

## Notes / Guardrails

- Prefer project-scoped config (`./.codex/config.toml`). It is local and should stay out of git.
- Use `127.0.0.1` URLs only when the MCP server is exposed localhost-only on the same machine as VS Code Remote.
- For Tailnet/HTTPS: point `url` to your `https://<node>.<tailnet>.ts.net/mcp` endpoint instead.

