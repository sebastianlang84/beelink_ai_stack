#!/usr/bin/env bash
set -euo pipefail

MEM="MEMORY.md"
MAX_LINES="${MAX_LINES:-200}"

fail() { echo "FAIL: $*" >&2; exit 1; }
warn() { echo "WARN: $*" >&2; }

[[ -f "$MEM" ]] || fail "Missing $MEM"

lines=$(wc -l < "$MEM" | tr -d ' ')
if (( lines > MAX_LINES )); then
  warn "$MEM has $lines lines (limit $MAX_LINES)"
fi

# Required headings (exact)
req=(
  "## 1) Current State"
  "## 2) Long-Term Memory"
  "## 3) Open Decisions"
  "## 4) Next Steps"
  "## 5) Known Risks / Blockers"
)

for h in "${req[@]}"; do
  grep -Fq "$h" "$MEM" || fail "Missing heading: $h"
done

# Flag possible episodic drift inside Current State
cs_start=$(grep -nF "## 1) Current State" "$MEM" | head -n1 | cut -d: -f1)
lt_start=$(grep -nF "## 2) Long-Term Memory" "$MEM" | head -n1 | cut -d: -f1)
cs_block=$(sed -n "${cs_start},$((lt_start-1))p" "$MEM")

if echo "$cs_block" | grep -Eq "[0-9]{4}-[0-9]{2}-[0-9]{2}"; then
  warn "Current State contains date patterns (possible episodic history). Consider moving details to docs/archive/memory-daily/*"
fi

# Warn if Next Steps > 5 items
ns_start=$(grep -nF "## 4) Next Steps" "$MEM" | head -n1 | cut -d: -f1)
kr_start=$(grep -nF "## 5) Known Risks / Blockers" "$MEM" | head -n1 | cut -d: -f1)
ns_block=$(sed -n "${ns_start},$((kr_start-1))p" "$MEM")
ns_items=$(echo "$ns_block" | grep -Ec '^[0-9]+\.' || true)
if (( ns_items > 5 )); then
  warn "Next Steps has $ns_items items (>5). Keep it 3-5."
fi

echo "OK: memory hygiene check completed"
