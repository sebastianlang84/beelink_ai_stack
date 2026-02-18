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

## Implementation: Hostname Split (No Path/Port Collisions)
Goal URLs (example Tailnet `tail027324.ts.net`):
- OWUI: `https://owui.tail027324.ts.net/`
- OpenClaw: `https://openclaw.tail027324.ts.net/`

Key idea: keep OWUI on one Tailscale node (hostname `owui`) and run a *second* Tailscale node on the same machine
as a Docker container (hostname `openclaw`). Each node gets its own MagicDNS hostname, so `/api` and `/ws` do not
collide.

### A) Rename the existing host node to `owui` and serve OWUI on root
NOTE: renaming changes bookmarks (the old `beelink.tail...` name changes).

```bash
# Rename this machine's Tailscale node
sudo tailscale up --hostname=owui --operator=wasti

# Make OWUI reachable at https://owui.tail027324.ts.net/
sudo tailscale serve reset
sudo tailscale serve --bg --https=443 http://127.0.0.1:3000

# Verify
tailscale status
tailscale serve status
```

### B) Run a second Tailscale node in Docker for OpenClaw (`openclaw`)
This keeps OpenClaw host-native (loopback) and does not require LAN expose.

Prereq: create a Tailscale auth key in the admin console (recommended: preauthorized + ephemeral; optionally tagged).
Treat it as a secret and do not commit it anywhere.

```bash
# Set once in your shell (do NOT commit)
export TS_AUTHKEY="tskey-REPLACE_ME"

# Start a separate tailscaled with its own state dir.
# IMPORTANT: do NOT use --network=host. Two tailscaled instances in the same network namespace will conflict:
# - they both try to create a TUN interface named "tailscale0"
# - they both would want to bind HTTPS on 443
#
# Instead, run the second node in its own container network namespace and proxy to a host bridge.
docker run -d --name tailscaled-openclaw --restart=unless-stopped \
  --network=ai-stack \
  --cap-add=NET_ADMIN --cap-add=NET_RAW \
  -v /dev/net/tun:/dev/net/tun \
  -v /var/lib/tailscale-openclaw:/var/lib/tailscale \
  tailscale/tailscale:latest tailscaled

# Join Tailnet as its own node
docker exec tailscaled-openclaw tailscale up \
  --auth-key="${TS_AUTHKEY}" \
  --hostname=openclaw

# Native gateway: loopback-only
nohup openclaw gateway --bind loopback --port 18789 > /tmp/openclaw-native.log 2>&1 &

# Bridge 172.21.0.1:18790 -> 127.0.0.1:18789 (host)
HOST_GATEWAY_IP=$(docker network inspect ai-stack -f '{{(index .IPAM.Config 0).Gateway}}')
nohup socat TCP-LISTEN:18790,bind=${HOST_GATEWAY_IP},fork,reuseaddr TCP:127.0.0.1:18789 > /tmp/openclaw-socat.log 2>&1 &

# Serve OpenClaw at https://openclaw.tail027324.ts.net/ via bridge
docker exec tailscaled-openclaw tailscale serve reset
docker exec tailscaled-openclaw tailscale serve --bg --https=443 "http://${HOST_GATEWAY_IP}:18790"

# Verify
docker exec tailscaled-openclaw tailscale status
docker exec tailscaled-openclaw tailscale serve status
```

### C) Smoke checks
```bash
curl -I https://owui.tail027324.ts.net/
curl -I https://openclaw.tail027324.ts.net/
```

Expected:
- OWUI login does not end on 404 because it is served at `/`.
- OpenClaw can keep absolute `/api` and `/ws` because it has its own hostname.

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
