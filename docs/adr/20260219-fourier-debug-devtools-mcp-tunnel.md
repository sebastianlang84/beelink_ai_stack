# ADR: Fourier Browser-Debug via SSH Tunnel + Chrome DevTools MCP
Date: 2026-02-19
Status: Accepted

## Context
- Fourier web UI debugging should work from a Windows client while Codex/MCP tooling runs on the Linux home server.
- The browser session to inspect is on Windows, but MCP tools are executed server-side.
- Exposing Chrome DevTools on LAN/public interfaces is not acceptable for this repository's security posture.

## Decision
- Use `chrome-devtools-mcp` as the DevTools MCP runtime, pinned to `0.17.3`.
- Standardize tunnel flow:
  - Windows Chrome starts with `--remote-debugging-port=9222`.
  - SSH reverse tunnel maps Linux `127.0.0.1:9223` to Windows `127.0.0.1:9222`.
  - Optional SSH local forward maps Windows `127.0.0.1:13010` to Linux Fourier UI `127.0.0.1:3010`.
- Provide operator scripts:
  - Windows: `fourier-cycles/tools/open_fourier_debug.bat`
  - Linux: `fourier-cycles/tools/run_chrome_devtools_mcp.sh`

## Consequences
- Positive:
  - Reproducible cross-host browser debugging with fixed port conventions.
  - DevTools endpoint remains localhost-bound on both hosts.
  - MCP runtime is pinned for stable behavior.
- Negative:
  - Debug session depends on a live SSH tunnel terminal.
  - Windows helper assumes Google Chrome path conventions unless overridden.

## Alternatives considered
- Expose Chrome DevTools directly on LAN.
  - Rejected due to avoidable attack surface.
- Run browser on Linux only.
  - Rejected because the target debugging workflow is explicitly Windows-browser based.
