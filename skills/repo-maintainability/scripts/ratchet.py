#!/usr/bin/env python3
"""A baseline ratchet for any line-oriented finding report.

Any tool that prints one finding per line (vulture, shellcheck -f gcc,
PSScriptAnalyzer, jscpd, ...) can be ratcheted:

  tool ... | ratchet.py check  --baseline .maintainability/<tool>.baseline
  tool ... | ratchet.py update --baseline .maintainability/<tool>.baseline

`check` fails only on findings NOT already in the baseline, so existing debt
never blocks a PR. `update` rewrites the baseline from the current findings
but refuses to add any finding not already in it -- a baseline only ratchets
down. The main-tier workflow runs `update` after each merge; nobody edits a
baseline by hand.

Findings are normalised before comparison: line and column numbers are
stripped, so a finding that merely shifts lines is not "new", and path
separators are made POSIX, so a Windows runner and a Linux runner agree.
With `--base <git-ref>`, baselined findings follow the files git sees moved
since <ref> (three-dot, like the other gates), so a move is not a regression
and the main-tier `update` accepts the new paths (issue #181). A move that
leaves a shim at the old path (ADR 0022) is a copy to git, so copies count
too, and a copy keeps its source's findings tolerated at the source as well
(a split file never fails falsely); findings the edit itself added are still
new. `--base baseline` means the commit that last wrote the baseline file.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

LINE_NO = re.compile(r":\d+(:\d+)?(?=[:\s]|$)")
PAIR = re.compile(r"(\S+): (\S+) \+ (\S+)")


def normalise(line: str) -> str:
    # The same finding whichever OS reported it: Windows runners print
    # backslashes and a leading ".\".
    line = line.strip().replace("\\", "/")
    if line.startswith("./"):
        line = line[2:]
    return LINE_NO.sub("", line)


def moves_since(base: str, baseline: Path) -> tuple[dict[str, str], set[str]]:
    """Old path -> new path for files git sees moved since `base`, and the old
    paths that still exist (copies). `base` may be the word "baseline": the
    commit that last wrote the baseline, so a run that coalesced several
    merges still sees every move since the bot last looked."""
    if base == "baseline":
        base = subprocess.run(["git", "log", "-1", "--format=%H", "--", str(baseline)],
                              check=False, capture_output=True, text=True).stdout.strip()
        if not base:
            return {}, set()
    # -C: with a shim left at the old path, git reports a copy, not a rename.
    cmd = ["git", "diff", "--name-status", "-z", "-M", "-C", "--diff-filter=RC", f"{base}...HEAD"]
    try:
        out = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    except subprocess.CalledProcessError:
        # Stricter, never looser: nothing is followed, so a move shows as new.
        print(f"ratchet: cannot diff against {base}; moves are not followed "
              "(shallow checkout?)", file=sys.stderr)
        return {}, set()
    parts = out.split("\0")        # R<score> or C<score>, old, new, repeated
    records = [(parts[i][0], normalise(parts[i + 1]), normalise(parts[i + 2]))
               for i in range(0, len(parts) - 2, 3)]
    return {old: new for _, old, new in records}, {old for kind, old, _ in records if kind == "C"}


def follow(line: str, moved: dict[str, str]) -> str:
    # A whole path only: at the start or after a space (jscpd's "a + b") and
    # before ":" or a space, so scripts/a.sh leaves scripts/a.sh.bak alone.
    if not moved:
        return line
    pat = "|".join(re.escape(p) for p in moved)
    line = re.sub(rf"(?:^|(?<=\s))(?:{pat})(?=[:\s]|$)", lambda m: moved[m.group(0)], line)
    # jscpd_findings.py prints a pair sorted; a followed member may sort differently.
    pair = PAIR.fullmatch(line)
    if pair:
        line = f"{pair[1]}: {' + '.join(sorted(pair.group(2, 3)))}"
    return line


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["check", "update"])
    ap.add_argument("--baseline", required=True, type=Path)
    ap.add_argument("--allow-growth", action="store_true",
                    help="update only: permit findings not already in the baseline (first run)")
    ap.add_argument("--base", help="git ref, or 'baseline' for the commit that last wrote the "
                    "baseline; baselined findings follow files moved since it")
    args = ap.parse_args()
    moved, copied = moves_since(args.base, args.baseline) if args.base else ({}, set())

    current = {normalise(l) for l in sys.stdin if l.strip()}
    old: set[str] = set()
    if args.baseline.exists():
        for raw in args.baseline.read_text().splitlines():
            if not raw.strip():
                continue
            line = normalise(raw)
            old.add(follow(line, moved))
            # A copy's source still exists (a shim, or a file that was split),
            # so what was tolerated there stays tolerated there.
            if copied and follow(line, dict.fromkeys(copied, "")) != line:
                old.add(line)

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

    # Compare findings, not counts: a fixed finding must not pay for a new
    # one, and an empty baseline must stay empty.
    new = sorted(current - old)
    if new and not args.allow_growth:
        for line in new:
            print("NEW:", line)
        print(f"ratchet: refusing to add {len(new)} finding(s) to {args.baseline}; "
              "fix them, or pass --allow-growth deliberately")
        return 1
    args.baseline.parent.mkdir(parents=True, exist_ok=True)
    # POSIX line endings whichever runner wrote it, so the file is identical
    # from Linux and Windows and git never sees a whole-file CRLF diff.
    args.baseline.write_text("\n".join(sorted(current)) + ("\n" if current else ""), newline="\n")
    print(f"ratchet: {args.baseline} now {len(current)} (was {len(old)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
