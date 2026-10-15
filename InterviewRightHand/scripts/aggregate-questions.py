#!/usr/bin/env python3
"""Aggregate question-bank inbox into a simple frequency report (questions only)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "question-bank" / "inbox"
OUT = ROOT / "question-bank" / "frequent.md"


def main() -> int:
    counter: Counter[str] = Counter()
    samples: dict[str, str] = {}
    for path in sorted(INBOX.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = obj.get("normalized") or obj.get("hash") or ""
            text = obj.get("text") or ""
            if not key or not text:
                continue
            counter[key] += 1
            samples.setdefault(key, text)

    lines = ["# Frequent interview questions", ""]
    for key, count in counter.most_common(100):
        lines.append(f"- ({count}) {samples[key]}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} ({len(counter)} unique)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
