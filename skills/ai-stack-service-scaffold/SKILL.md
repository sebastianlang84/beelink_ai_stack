---
name: ai-stack-service-scaffold
description: Scaffold a new ai_stack service folder (kebab-case) with docker-compose.yml, .env.example, and minimal service docs aligned with repo conventions (no secrets in repo, localhost-only ports, external ai_stack network, volumes named for backup). Use when adding a new service (e.g. qdrant, MCP server, proxy) or splitting stacks into new folders.
---

# Scaffold a new service

## Create the folder layout

1) Create a new folder `<service>/` (kebab-case).
2) Add:
- `<service>/docker-compose.yml`
- `<service>/.env.example` (safe defaults, no secrets)
- Optional: `<service>/README.md` and/or `<service>/OPERATIONS.md` (ports, volumes, restore steps)

## Compose conventions (ai_stack)

- Use the external docker network `ai_stack` (shared between stacks).
- Prefer no published ports; if needed, bind localhost only (`127.0.0.1:<port>`).
- Name volumes clearly and list them in the service docs for backup/restore.
- Add healthchecks when the image supports it.
- Keep secrets out of git; rely on `docker compose --env-file /etc/ai_stack/secrets.env ...`.

## Update living docs (required)

After adding a service folder:
- Update `README.md` (Repo-Struktur + quickstart if relevant).
- Update `CHANGELOG.md` (Unreleased).
- Update `TODO.md` if there are follow-up ops tasks.

## Validate

- Run: `./scripts/compose_validate_all.sh`
- Run (service-only): `docker compose -f <service>/docker-compose.yml config >/dev/null`

