#!/usr/bin/env python3
"""A baseline ratchet for any line-oriented finding report.

Any tool that prints one finding per line (vulture, shellcheck -f gcc,
PSScriptAnalyzer, jscpd, ...) can be ratcheted:

  tool ... | ratchet.py check  --baseline .maintainability/<tool>.baseline
  tool ... | ratchet.py update --baseline .maintainability/<tool>.baseline

`check` fails only on findings NOT already in the baseline, so existing debt
never blocks a PR. `update` rewrites the baseline from the current findings
but refuses to let it grow -- a baseline only ratchets down. The burn-down
workflow runs `update` on main after each merge; nobody edits a baseline by
hand.

Findings are normalised before comparison: line and column numbers are
stripped, so a finding that merely shifts lines is not "new".
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

LINE_NO = re.compile(r":\d+(:\d+)?(?=[:\s]|$)")


def normalise(line: str) -> str:
    return LINE_NO.sub("", line.strip())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["check", "update"])
    ap.add_argument("--baseline", required=True, type=Path)
    ap.add_argument("--allow-growth", action="store_true",
                    help="update only: permit a larger baseline (first run)")
    args = ap.parse_args()

    current = {normalise(l) for l in sys.stdin if l.strip()}
    old: set[str] = set()
    if args.baseline.exists():
        old = {l.strip() for l in args.baseline.read_text().splitlines() if l.strip()}

    if args.mode == "check":
        new = sorted(current - old)
        cleared = len(old - current)
        if new:
            for line in new:
                print("NEW:", line)
            print(f"\n{len(new)} new finding(s) not in {args.baseline} "
                  f"({len(current)} total, {len(old)} tolerated, {cleared} cleared since).")
            return 1
        print(f"ratchet: no new findings ({len(current)} total, {len(old)} tolerated, "
              f"{cleared} cleared since)")
        return 0

    if old and len(current) > len(old) and not args.allow_growth:
        print(f"ratchet: refusing to grow {args.baseline} {len(old)} -> {len(current)}; "
              "fix the new findings, or pass --allow-growth deliberately")
        return 1
    args.baseline.parent.mkdir(parents=True, exist_ok=True)
    args.baseline.write_text("\n".join(sorted(current)) + ("\n" if current else ""))
    print(f"ratchet: {args.baseline} now {len(current)} (was {len(old)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
