---
name: ai-stack-secrets-env-hygiene
description: Enforce ai_stack env policy (repo-local `.env` = secrets-only; `.config.env`/`<service>/.config.env` = non-secrets; all gitignored; validate required keys; avoid leaking config output). Use when adding env vars to services, debugging auth/indexing failures, or preparing a new install.
---

# Secrets & env hygiene

## Golden rule

- Never commit secrets (tokens/passwords/keys).
- Use the repo-local layout: `.env` (secrets-only) + `.config.env`/`<service>/.config.env` (non-secrets), all gitignored.

## Validate the env files

- Run: `./scripts/env_doctor.sh`

If it fails:
- Fix permissions (should be `600`) and required keys.
- Reference: `docs/policies/policy_secrets_env.md:1`

## Safe debugging (avoid leaks)

- Prefer: `docker compose --env-file .env --env-file .config.env --env-file <service>/.config.env -f <service>/docker-compose.yml config >/dev/null`
- If output must be shared: `docker compose --env-file .env --env-file .config.env --env-file <service>/.config.env -f <service>/docker-compose.yml config | ./scripts/redact_secrets_output.sh`

## When adding a new env var

1) Add it to the service’s `.env.example` with a safe placeholder/default.
2) Document whether it is:
- Secret (shared: `.env`)
- Non-secret config (`.config.env` / `<service>/.config.env`)
3) If the var affects network exposure, update service docs and `README.md`.
