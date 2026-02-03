#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/home/wasti/ai_stack"
TRANSCRIPTS_DIR="/home/wasti/ai_stack_data/transcript-miner/output/data/transcripts/by_video_id"
SUMMARIES_DIR="/home/wasti/ai_stack_data/transcript-miner/output/data/summaries/by_video_id"
OUT_DIR="$REPO_ROOT/transcript-miner/tests/prompt-engineering"
CONFIG_PATH="$REPO_ROOT/transcript-miner/config/config_investing.yaml"
N=10
MODEL="google/gemini-3-flash-preview"

mkdir -p "$OUT_DIR"

# _promptold.md (current config excerpt)
cat > "$OUT_DIR/_promptold.md" <<'MD'
# Old Prompt (Current Investing Config)

Below is the exact `analysis.llm` block from `transcript-miner/config/config_investing.yaml`.
MD
sed -n '/^analysis:/,/^# Report-Generierung/p' "$CONFIG_PATH" >> "$OUT_DIR/_promptold.md"

# _promptnew.md (topic-isolated RAG prompt)
cat > "$OUT_DIR/_promptnew.md" <<'MD'
# New Prompt (RAG Topic-Isolated)

## System Prompt
You are a financial transcript analyst creating RAG-optimized, topic-isolated summaries.

TASK
From EXACTLY ONE video transcript, produce up to 3 separate Markdown documents:
1) macro
2) stocks
3) crypto

Only create a document if the transcript contains meaningful content for that topic.
Do NOT create empty-topic documents.

GLOBAL HARD RULES
- Output ONLY Markdown.
- No JSON, no code fences, no intro text.
- Use ONLY transcript content (no external facts).
- Same language as transcript.
- Be concrete, compact, evidence-based.
- Never guess. Unknowns must be explicit.
- Do not mix topics inside one document.

OUTPUT FORMAT
Return documents in this exact wrapper format:

<<<DOC_START>>>
---
doc_type: rag_topic_summary
topic: <macro|stocks|crypto>
video_id: <video_id>
title: <title>
channel_namespace: <channel_namespace>
url: <url>
published_at: <YYYY-MM-DD HH:MM UTC or unknown>
fetched_at: <YYYY-MM-DD HH:MM UTC or unknown>
assets: [<asset1>, <asset2>]   # [] if none
keywords: [<k1>, <k2>, <k3>]   # topic-relevant retrieval hints
---
# <Topic Label>: <short title>

## Executive Summary
- 3-6 bullets, only this topic.

## Key Points
- One fact per bullet.
- Include short inline evidence quote in parentheses when possible (max 180 chars).

## Numbers
- metric: <name> | value: <value> | unit: <unit> | context: <short context>
- If none: - none

## Opportunities
- Topic-specific upside points only.
- If none: - none

## Risks
- Topic-specific downside points only.
- If none: - none

## Unknowns
- Missing / unclear points from transcript only.
- If none: - none

## IST-Stand
- Current state described in transcript (not your external knowledge).
<<<DOC_END>>>

TOPIC BOUNDARY RULES
- macro doc: rates, inflation, liquidity, central banks, fiscal/tariff/geopolitics, yield curve, DXY, growth/recession.
- stocks doc: equities, companies, earnings, valuation, guidance, sectors, positioning.
- crypto doc: BTC/ETH/altcoins, on-chain, regulation, exchange flows, crypto narratives.

CROSS-TOPIC RULE
- If a dependency exists, keep main claim in-topic and add ONE short cross-reference bullet:
  "Cross-topic note: related macro/stocks/crypto driver mentioned."
- No long mixed explanation.

QUALITY BAR
- Prefer fewer high-signal bullets over many vague bullets.
- No filler, no motivational language, no generic market commentary.

## User Prompt Template
Create up to 3 topic-isolated RAG documents for this one transcript.

Video metadata:
- topic: investing
- video_id: {video_id}
- url: {url}
- title: {title}
- channel_namespace: {channel_namespace}
- published_at: {published_at}
- fetched_at: {fetched_at}

Transcript:
{transcript}
MD

SYSTEM_PROMPT=$(awk '/^## System Prompt/{flag=1;next}/^## User Prompt Template/{flag=0}flag' "$OUT_DIR/_promptnew.md")

api_key_line=$(grep -E '^OPENROUTER_API_KEY=' "$REPO_ROOT/.env" | head -n 1 || true)
if [[ -z "$api_key_line" ]]; then
  echo "OPENROUTER_API_KEY not found in .env" >&2
  exit 1
fi
API_KEY=${api_key_line#OPENROUTER_API_KEY=}
API_KEY="${API_KEY%\"}"
API_KEY="${API_KEY#\"}"
API_KEY="${API_KEY%\'}"
API_KEY="${API_KEY#\'}"

manifest_tmp=$(mktemp)
echo "[" > "$manifest_tmp"
first=1

count=0
while IFS= read -r transcript_path; do
  video_id=$(basename "$transcript_path" .txt)
  summary_path="$SUMMARIES_DIR/$video_id.summary.md"
  meta_path="$TRANSCRIPTS_DIR/$video_id.meta.json"

  [[ -f "$summary_path" ]] || continue
  [[ -f "$meta_path" ]] || continue

  cp "$transcript_path" "$OUT_DIR/${video_id}_transcript.md"
  cp "$summary_path" "$OUT_DIR/${video_id}_sumold.md"

  title=$(jq -r '.video_title // .title // "unknown"' "$meta_path")
  channel=$(jq -r '.channel_handle // .channel_namespace // .channel_name // "unknown"' "$meta_path")
  published_at=$(jq -r '.published_at // "unknown"' "$meta_path")
  fetched_at=$(jq -r '.downloaded_at // .fetched_at // "unknown"' "$meta_path")
  url=$(jq -r '.url // ("https://www.youtube.com/watch?v=" + .video_id)' "$meta_path")

  transcript_text=$(cat "$transcript_path")
  user_prompt=$(cat <<EOF
Create up to 3 topic-isolated RAG documents for this one transcript.

Video metadata:
- topic: investing
- video_id: $video_id
- url: $url
- title: $title
- channel_namespace: $channel
- published_at: $published_at
- fetched_at: $fetched_at

Transcript:
$transcript_text
EOF
)

  payload=$(jq -n \
    --arg model "$MODEL" \
    --arg system "$SYSTEM_PROMPT" \
    --arg user "$user_prompt" \
    '{model:$model,temperature:0.2,messages:[{role:"system",content:$system},{role:"user",content:$user}]}'
  )

  response=$(curl -sS --fail-with-body https://openrouter.ai/api/v1/chat/completions \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "$payload")

  echo "$response" | jq -r '.choices[0].message.content // ""' > "$OUT_DIR/${video_id}_sumnew.md"

  if [[ $first -eq 0 ]]; then
    echo "," >> "$manifest_tmp"
  fi
  first=0
  jq -n \
    --arg video_id "$video_id" \
    --arg title "$title" \
    --arg channel_namespace "$channel" \
    --arg published_at "$published_at" \
    --arg fetched_at "$fetched_at" \
    --arg url "$url" \
    '{video_id:$video_id,title:$title,channel_namespace:$channel_namespace,published_at:$published_at,fetched_at:$fetched_at,url:$url}' >> "$manifest_tmp"

  count=$((count + 1))
  echo "done $count/$N $video_id"
  [[ $count -ge $N ]] && break

done < <(ls -1t "$TRANSCRIPTS_DIR"/*.txt)

echo "]" >> "$manifest_tmp"
mv "$manifest_tmp" "$OUT_DIR/_manifest.json"

if [[ $count -lt $N ]]; then
  echo "Only prepared $count pairs (expected $N)" >&2
  exit 1
fi

echo "Fixture ready in $OUT_DIR"
