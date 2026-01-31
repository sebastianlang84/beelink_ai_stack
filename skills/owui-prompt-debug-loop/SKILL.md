---
name: owui-prompt-debug-loop
description: Debug and iterate Open WebUI prompt composition (model prompt, folder prompt, and RAG template) using debug-proxy logs and safe, repeatable webui.db inspection/patching. Use for PDCA-style prompt tuning, tracing what Open WebUI actually sends to OpenRouter/OpenAI-compatible providers, and validating changes against real traffic.
---

# OWUI Prompt Debug Loop (PDCA)

## Goal

Make prompt iteration repeatable:

- **Plan**: define desired behavior + prompt changes
- **Do**: apply prompt changes (model / folder / rag template)
- **Check**: run one controlled query in OWUI and inspect `debug-proxy/flows.jsonl`
- **Act**: refine prompts based on evidence

This skill assumes:

- `owui` container exists (Open WebUI)
- `debug-proxy` is available and OWUI is configured to use it when needed

## Safety / Secrets

- Do **not** paste or commit secrets (API keys, tokens).
- Open WebUI stores provider keys inside `webui.db` by design; any scripts in this skill avoid dumping those fields.

## Files You Will Use

- `debug-proxy/flows.jsonl` (symlink into `/home/wasti/ai_stack_data/...`): source of truth for what went over the wire
- `debug-proxy/last_flows.json` (optional): small extracted subset (created by scripts)
- Open WebUI DB inside container: `/app/backend/data/webui.db`

## Workflow

### 1) Ensure logging is on

- Start `debug-proxy` and ensure OWUI uses it (HTTP(S)_PROXY env).
- Run one test prompt in OWUI (manual): e.g. in folder **Investing** ask about Bitcoin performance + outlook.

### 2) CHECK: Extract and summarize the last outgoing flows

Run:

```bash
python3 skills/owui-prompt-debug-loop/scripts/flow_extract.py --in debug-proxy/flows.jsonl --out debug-proxy/last_flows.json --n 5
python3 skills/owui-prompt-debug-loop/scripts/flow_report.py --in debug-proxy/last_flows.json
```

This tells you (per request):

- which endpoint was hit (e.g. `/chat/completions`)
- whether `stream` was used
- model id
- prompt sizes + a short preview of the system + user content
- whether `reasoning` fields appeared in streamed events

### 3) CHECK: Dump the current OWUI prompts (without secrets)

```bash
bash skills/owui-prompt-debug-loop/scripts/owui_dump_prompts.sh \\
  --model-id 'google/gemini-3-flash-preview' \\
  --folder-name 'Investing'
```

This prints:

- model prompt (system)
- folder prompt (system_prompt)
- RAG template (`rag.template`)

### 4) DO: Patch prompts safely (DB edit with backup)

Prepare local text files (edit as you like):

- `skills/owui-prompt-debug-loop/references/model_system.txt`
- `skills/owui-prompt-debug-loop/references/folder_investing_system.txt`
- `skills/owui-prompt-debug-loop/references/rag_template.txt`

Then apply:

```bash
bash skills/owui-prompt-debug-loop/scripts/owui_patch_prompts.sh \\
  --model-id 'google/gemini-3-flash-preview' \\
  --model-system-file skills/owui-prompt-debug-loop/references/model_system.txt \\
  --folder-name 'Investing' \\
  --folder-system-file skills/owui-prompt-debug-loop/references/folder_investing_system.txt \\
  --rag-template-file skills/owui-prompt-debug-loop/references/rag_template.txt
```

The script:

- creates a timestamped backup of `webui.db` inside the container volume
- patches only the requested fields (no mass rewrites)

### 5) Repeat PDCA

After patching:

1. Ask the same test question again in OWUI (fresh chat is best).
2. Re-run steps (2) and (3).
3. Compare flow diffs (system prompt length/content, presence of RAG context, `tools`, `reasoning`).

## Notes / Known Limitations

- Provider-driven `reasoning` streams are not reliably preventable via prompting alone; you need model/settings/UI filtering.
- Prefer configuring OWUI/provider to **not emit reasoning** for production; use it only for debugging.
