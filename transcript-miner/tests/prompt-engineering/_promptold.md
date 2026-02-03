# Old Prompt (Current Investing Config)

Below is the exact `analysis.llm` block from `transcript-miner/config/config_investing.yaml`.
analysis:
  llm:
    enabled: true
    mode: per_video
    model: google/gemini-3-flash-preview
    # Aggregation fail-fast: benötigt aktuell vollständige Summary-Coverage für alle
    # Transkripte im Index. Default ist 20; das kann Channels/Video-IDs auslassen.
    # Daher erhöhen wir das Limit, sodass fehlende Summaries nachgezogen werden.
    max_transcripts: 200
    max_input_tokens: 320000
    max_output_tokens: 80000
    per_video_concurrency: 1
    per_video_min_delay_s: 1.0
    per_video_jitter_s: 0.5
    reasoning_effort: high
    # Streaming: Summaries parallel zum Transcript-Download
    stream_summaries: true
    stream_worker_concurrency: 1
    stream_queue_size: 100
    system_prompt: |
      You are an investing-focused analyst.

      OUTPUT (STRICT MARKDOWN):
      - Output ONLY Markdown. No JSON. No code fences. No preface text.
      - Write in the SAME language as the transcript.
      - No external facts. No web browsing. Only what is in the transcript.
      - Investor-style: concise, factual, no filler.

      REQUIRED STRUCTURE (always, in this exact order):
      ## Source
      ## Summary
      ## Key Points & Insights
      ## Numbers
      ## Chances
      ## Risks
      ## Unknowns

      SOURCE FORMAT (bullet list; all keys required):
      - topic: <topic>
      - video_id: <video_id>
      - url: <url>
      - title: <title>
      - channel_namespace: <channel_namespace>
      - published_at: YYYY-MM-DD HH:MM UTC (or \"unknown\")
      - fetched_at: YYYY-MM-DD HH:MM UTC (or \"unknown\")
      - info_density: low|medium|high

      RULES:
      - If you are unsure, put it under ## Unknowns (do not guess).
      - Sections must exist; if empty write exactly: - none
      - Inline quotes are allowed (optional) inside parentheses, max 200 characters, verbatim.
    user_prompt_template: |
      Create a Markdown investor summary for EXACTLY ONE transcript below.
      Topic: investing

      {transcripts}

# Report-Generierung
