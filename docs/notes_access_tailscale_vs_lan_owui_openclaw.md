# Notes: Access Topology (OWUI + OpenClaw) - Tailscale vs LAN

Date: 2026-02-01

## Goal
Reach both UIs reliably:
- Open WebUI (OWUI)
- OpenClaw Control UI

## Current State (as of 2026-02-01)
- OWUI runs on the server at `http://127.0.0.1:3000` (Docker).
- OpenClaw runs on the server at `http://127.0.0.1:18789` (Docker).
- Tailscale Serve is used as the external access layer.

## What Broke Today (Symptom Summary)
1) OWUI under `/owui` looked OK (HTTP 200), but after login the browser ended on a 404.
2) OpenClaw under `/openclaw` rendered a black page (HTML loads, but UI fails).

## Root Causes
### A) OWUI: no stable base-path support for `/owui`
OWUI redirects to `/` after login. If only `/owui` is served, the redirect leaves the served path and hits a 404.
Result: `/owui` path-serve is fragile even if `/owui/`, `/_app`, `/static`, `/api` return 200.

### B) OpenClaw: absolute paths collide with OWUI
OpenClaw Control UI uses absolute paths such as:
- `/api` (HTTP API)
- `/ws` (WebSocket)

If OpenClaw is served under `/openclaw` while OWUI already uses `/api` on the same hostname, the requests route to the
wrong upstream. Result: black page / UI fails.

This is a fundamental "single-hostname + multiple path apps" collision when apps assume they live at the root.

## Working Access Options
### Option 1 (recommended): keep OWUI on root, give OpenClaw its own port
Pros: simplest, reliable, keeps single Tailscale node.
Cons: URL includes a port.

Example:
- OWUI: `https://<node>.tail.../`
- OpenClaw: `https://<node>.tail...:8443/`

### Option 2 (cleanest URLs): second Tailscale node for OpenClaw (hostname split)
Pros: nice URLs, no port, avoids collisions completely.
Cons: more setup (second Tailscale node), e.g. via WSL2 or a container running tailscaled.

Example:
- OWUI: `https://owui.tail.../` (or `https://beelink.tail.../`)
- OpenClaw: `https://openclaw.tail.../`

### Option 3 (most complex): reverse proxy with path rewrites
Pros: both on one hostname with paths.
Cons: higher complexity; must rewrite OpenClaw `/openclaw/...` <-> `/...` and handle `/api` and WebSocket routing.

## Security Discussion: Keeping Tailscale vs LAN Expose
### Current (Tailscale + localhost-only)
- Services bind to `127.0.0.1` and are not reachable from other LAN/WiFi devices.
- Only devices in the Tailnet can reach the services.
- This reduces attack surface, especially with many IoT/consumer devices in the same WiFi.

### LAN expose (bind to LAN IP / 0.0.0.0)
Main change: the services become reachable by every device in the WLAN/LAN (TV, watch, scale, phone, etc.).
That increases risk because OWUI/OpenClaw are complex web apps and become additional entry points.

Possible mitigations if LAN expose is chosen:
- network segmentation (separate IoT network / VLAN / AP isolation)
- host firewall allowlist (only allow notebook/phone IPs to reach ports 3000/18789)
- do not use router port forwarding / UPnP

## Notes / Learnings
- "HTTP 200 for /owui" is not sufficient; login redirect to `/` must be considered.
- Two root-assuming apps cannot reliably share one hostname via path-prefix routing.

