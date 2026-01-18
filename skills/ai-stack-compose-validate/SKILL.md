---
name: ai-stack-compose-validate
description: Validate ai_stack docker compose stacks (run docker compose config, detect published ports not bound to localhost, catch config errors). Use when reviewing/adding docker-compose.yml changes, troubleshooting compose errors, or before deploying/starting stacks.
---

# Validate compose stacks

## Quick checks (recommended)

1) Validate all stacks:
- Run: `./scripts/compose_validate_all.sh`

2) Validate a single stack:
- Run: `docker compose -f <service>/docker-compose.yml config >/dev/null`

## Port policy check

If a stack publishes ports:
- Prefer `host_ip: 127.0.0.1` (or `::1`) binding.
- Do not add new host ports without justification and docs update (see `AGENTS.md`).

If you intentionally need a non-localhost bind:
- Use `./scripts/compose_validate_all.sh --warn-only` for the preflight,
- Document the rationale and access boundary (LAN vs VPN vs reverse proxy).

## Troubleshooting

- Missing env values: confirm `--env-file /etc/ai_stack/secrets.env` is used when starting the stack.
- Network errors: ensure the shared network exists once: `./scripts/create_ai_stack_network.sh`.

