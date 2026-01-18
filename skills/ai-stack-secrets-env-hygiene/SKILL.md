---
name: ai-stack-secrets-env-hygiene
description: Enforce ai_stack secrets/env policy (no secrets in repo, use /etc/ai_stack/*.env via --env-file, validate required keys, avoid host .env files). Use when adding env vars to services, debugging auth/indexing failures, or preparing a new host install.
---

# Secrets & env hygiene

## Golden rule

- Never commit secrets (tokens/passwords/keys).
- Prefer `docker compose --env-file /etc/ai_stack/secrets.env ...` over repo-local `.env`.

## Validate the host secrets file

- Run: `./scripts/secrets_env_doctor.sh /etc/ai_stack/secrets.env`

If it fails:
- Fix permissions (should be `600`) and required keys.
- Reference: `docs/policy_secrets_environment_variables_ai_stack.md:1`

## Safe debugging (avoid leaks)

- Prefer: `docker compose --env-file /etc/ai_stack/secrets.env config >/dev/null`
- If output must be shared: `docker compose --env-file /etc/ai_stack/secrets.env config | ./scripts/redact_secrets_output.sh`

## When adding a new env var

1) Add it to the service’s `.env.example` with a safe placeholder/default.
2) Document whether it is:
- Secret (must live only in `/etc/ai_stack/secrets.env`)
- Non-secret config (can live in `.env.example`)
3) If the var affects network exposure, update service docs and `README.md`.
