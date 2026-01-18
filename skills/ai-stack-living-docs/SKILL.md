---
name: ai-stack-living-docs
description: Keep ai_stack living docs in sync (README.md, TODO.md, CHANGELOG.md) whenever code/compose/process changes. Use when making any repo change that affects installation, operation, ports, volumes, or workflows.
---

# Maintain living docs

## Update rules (repo policy)

- `README.md`, `TODO.md`, `CHANGELOG.md` must match the repo state (no stale docs).
- If you change compose, scripts, or operational workflows, update docs in the same change.

## Checklist per change

1) Identify what changed:
- Service folders, ports, URLs, volumes, env vars, startup commands, backup/restore steps.

2) Update docs accordingly:
- `README.md`: quickstarts, repo structure, security/access assumptions.
- `CHANGELOG.md`: add an Unreleased bullet describing the change.
- `TODO.md`: add follow-up tasks only if there’s remaining work.

3) Validate doc links quickly:
- Prefer file paths that exist in this repo and point to the correct entry section.

