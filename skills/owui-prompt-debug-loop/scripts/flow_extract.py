#!/usr/bin/env python3
"""
Extract last N valid JSONL flow entries (debug-proxy) into a small JSON array file.

Keep it simple and robust: ignore invalid/partial lines (ringbuffer cuts).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="in_path", required=True, help="Input flows.jsonl path")
    p.add_argument("--out", dest="out_path", required=True, help="Output JSON file path")
    p.add_argument("--n", type=int, default=5, help="Number of last valid flows to keep")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    in_path = Path(args.in_path)
    out_path = Path(args.out_path)
    n = max(1, args.n)

    last: deque[dict] = deque(maxlen=n)
    bad = 0

    with in_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            if isinstance(obj, dict):
                last.append(obj)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(list(last), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(f"Wrote {len(last)} flows to {out_path} (ignored {bad} invalid lines).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

