#!/usr/bin/env python3
"""Fail when a hand-written ledger, tracker or status file is committed.

Project state belongs in GitHub Issues and the organisation Project board.
The only status file a repository may hold is one a workflow generates and
marks as generated in its first lines. A hand-written ledger has no removal
rule, so every agent session leaves it longer than it found it.

Policy: `.maintainability/records.json` (optional; these are the defaults)
{
  "forbid": ["*tracker*", "*ledger*", "STATUS.md", "PROGRESS.md", "TODO.md",
             "NOTES.md", "*-log.md", "*changelog*.html"],
  "allow": ["docs/archive/*"],
  "extensions": [".md", ".html", ".htm", ".txt", ".csv", ".tsv", ".rst", ".adoc"],
  "generated_marker": "generated-by:"
}

A ledger is a document, so only document extensions are examined; a script
named `ledger_sync.py` is code and is left to the layout gate.

Usage:
  check_ledgers.py --base <git-ref>   # CI: only files added or renamed since base
  check_ledgers.py                    # every tracked file (new repo, main tier)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

POLICY = Path(".maintainability/records.json")
DEFAULTS = {
    "forbid": ["*tracker*", "*ledger*", "STATUS.md", "PROGRESS.md", "TODO.md",
               "NOTES.md", "*-log.md", "*changelog*.html"],
    "allow": ["docs/archive/*"],
    "extensions": [".md", ".html", ".htm", ".txt", ".csv", ".tsv", ".rst", ".adoc"],
    "generated_marker": "generated-by:",
}
MARKER_LINES = 5


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def candidates(base: str | None) -> list[str]:
    if base is None:
        return git("ls-files").splitlines()
    added = []
    for line in git("diff", "--name-status", "-M", base, "HEAD").splitlines():
        parts = line.split("\t")
        if parts[0][0] in "AR":
            added.append(parts[-1])
    return added


def is_generated(path: str, marker: str) -> bool:
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            head = [next(fh, "") for _ in range(MARKER_LINES)]
    except OSError:
        return False
    return any(marker in line for line in head)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base")
    args = ap.parse_args()

    policy = dict(DEFAULTS)
    if POLICY.exists():
        policy.update(json.loads(POLICY.read_text()))

    bad = []
    for path in candidates(args.base):
        name = Path(path).name.lower()
        if Path(name).suffix not in policy["extensions"]:
            continue
        if any(fnmatch(path, a) for a in policy["allow"]):
            continue
        if not any(fnmatch(name, f.lower()) for f in policy["forbid"]):
            continue
        if is_generated(path, policy["generated_marker"]):
            continue
        bad.append(path)

    if not bad:
        print("check_ledgers: no hand-written ledger or status file")
        return 0
    for path in bad:
        print(f"{path}: looks like a hand-written ledger or status file")
    print("\nRecord state in an issue on the project board instead. A generated "
          f"status file must carry '{policy['generated_marker']}' in its first "
          f"{MARKER_LINES} lines.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
