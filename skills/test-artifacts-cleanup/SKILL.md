---
name: test-artifacts-cleanup
description: Purge all test artifacts for a topic (transcripts, summaries, indexes, reports, history) and delete the matching Open WebUI Knowledge collection.
---

# Test Artifacts Cleanup

Use this skill when you need to **fully reset** a test topic (e.g., `investing_test`).

## Primary action (preferred)

Run the provided purge script from repo root:

```bash
OPEN_WEBUI_API_KEY=... ./scripts/purge_topic_data.sh <topic> --force
```

Example:

```bash
OPEN_WEBUI_API_KEY=... ./scripts/purge_topic_data.sh investing_test --force
```

## What the script deletes

- `output/data/indexes/<topic>`
- `output/reports/<topic>`
- `output/history/<topic>`
- Per‑video transcripts + summaries for video_ids in the topic index
- Open WebUI Knowledge collection with **name = topic**

## Safety notes

- Requires `--force` to run.
- Requires `OPEN_WEBUI_API_KEY` to delete the Knowledge collection.
- If the index is missing, per‑video deletes are skipped.

## If you need a scheduler

Create a systemd timer that calls the script (topic + `--force`) at the desired interval.

