# SECRETS — open-webui

Policy: `docs/policy_secrets_environment_variables_ai_stack.md:1` (keine Werte im Repo).

Start empfohlen:
- `docker compose --env-file /etc/ai-stack/secrets.env up -d`

## Benötigt (empfohlen)
- `WEBUI_SECRET_KEY` — Secret/Signing-Key (stabil halten; Sessions/Auth)

## Optional (je nach Provider)
- `OPENAI_API_KEY` — falls OpenAI-kompatible Provider über Env genutzt werden
