#!/usr/bin/env python3
"""Turn a jscpd JSON report into one stable line per duplicated pair.

  jscpd --silent --reporters json --output "$RUNNER_TEMP/jscpd" ... || true
  jscpd_findings.py "$RUNNER_TEMP/jscpd/jscpd-report.json" | ratchet.py check ...

jscpd's console reporter names the pair in traversal order, which differs
between operating systems and between runs, so a baseline built from it
reports clones that merely swapped sides as "new". This prints the two
paths sorted, with POSIX separators, and without line ranges or sizes, so a
clone is the same finding until one of its files changes or it goes away.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def posix(name: str) -> str:
    name = name.replace("\\", "/")
    return name[2:] if name.startswith("./") else name


def findings(report: dict) -> list[str]:
    lines = set()
    for dup in report.get("duplicates", []):
        a, b = sorted(posix(dup[side]["name"]) for side in ("firstFile", "secondFile"))
        lines.add(f"{dup.get('format', '?')}: {a} + {b}")
    return sorted(lines)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    if not path.exists():          # jscpd writes no report when it finds nothing
        return 0
    for line in findings(json.loads(path.read_text(encoding="utf-8"))):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
