---
name: owui-prompt-api-loop
description: Automate Open WebUI prompt testing via API and debug-proxy. Use when running a repeatable prompt-test loop for Open WebUI (model/folder/RAG) that should: (1) send a single test prompt to an existing chat/folder via /api/v1/chat/completions, (2) capture debug-proxy flows, and (3) report the last N flows. Triggers include "run the prompt via API", "automate the loop", "send test prompt to OWUI", "check flows after prompt", or any complex OWUI prompt PDCA workflow.
---

# OWUI Prompt API Loop

## Goal
Run a single prompt against Open WebUI via API and immediately extract/report the latest debug-proxy flows to validate the effective prompt stack.

## Preconditions
- `owui` container running
- debug-proxy enabled in OWUI env (if you want flow capture)
- `OPEN_WEBUI_API_KEY` is set in repo `.env` (secrets-only)

## Primary Script
Use:

```bash
bash skills/owui-prompt-api-loop/scripts/owui_prompt_api_loop.sh \
  --model-id 'google/gemini-3-flash-preview' \
  --folder-name 'Investing' \
  --prompt-file skills/owui-prompt-api-loop/references/prompt_bitcoin_2026.txt
```

### Options
- `--chat-id <id>`: Skip folder lookup and target a specific chat.
- `--prompt-text <text>`: Inline prompt instead of file.
- `--stream true|false`: Pass stream flag (default: false).
- `--no-flows`: Skip flow extraction/report.
- `--flows-n <n>`: How many flows to report (default: 5).

## What the Script Does
1. Resolves the latest chat in a folder (by name) if `--chat-id` is not provided.
2. Sends one user message via `/api/v1/chat/completions` with the selected model.
3. Extracts and reports the last N debug-proxy flows using:
   - `skills/owui-prompt-debug-loop/scripts/flow_extract.py`
   - `skills/owui-prompt-debug-loop/scripts/flow_report.py`

## Safety / Secrets
- Never print or commit `OPEN_WEBUI_API_KEY`.
- The script only reads `.env` and uses the key in an Authorization header.

## Troubleshooting
- If the script errors with "Folder not found" or "No chats in folder": create a chat in that folder via UI once.
- If no flows appear: verify debug-proxy env in `open-webui/.config.env` and restart OWUI.
