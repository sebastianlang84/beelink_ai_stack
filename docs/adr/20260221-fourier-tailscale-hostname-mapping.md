# ADR: Fourier Tailscale Mapping Uses Dedicated Hostname
Date: 2026-02-21
Status: Accepted

## Context
- `fourier-cycles/PRD_webapp.md` kept an open decision between path-based access (`/fourier`) and dedicated hostname access.
- The current UI is a root-based SPA (static assets + `/api/*` proxy at root).
- Path-prefix publishing would require additional base-path/rewrite hardening and increases routing complexity/risk on shared endpoints.

## Decision
- Use dedicated hostname-style mapping for Fourier UI in Tailscale Serve.
- Serve Fourier UI as root (`/`) of its Tailnet HTTPS endpoint that forwards to `http://127.0.0.1:${FOURIER_UI_HOST_PORT}`.
- Do not standardize `/fourier` path-prefix publishing for this service.

## Consequences
- Positive:
  - Works with current UI/API routing without extra path-prefix rewrites.
  - Lower operator complexity and fewer SPA asset-path edge cases.
  - Clear separation from other services exposed in Tailnet.
- Negative:
  - Requires a dedicated Tailnet endpoint strategy (separate node/serve target) instead of one shared path tree.
  - If operators insist on shared path-prefix hosting later, UI/base-path work is required.

## Alternatives considered
- Path-based mapping (`/fourier`) on shared Tailnet endpoint.
  - Rejected for now due to higher routing/base-path complexity and avoidable operational risk with current SPA layout.
