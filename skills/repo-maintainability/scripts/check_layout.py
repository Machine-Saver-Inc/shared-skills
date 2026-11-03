#!/usr/bin/env python3
"""Fail when a PR adds a new top-level file to a directory that is only
allowed to grow inside named family subdirectories.

This stops a flat directory from growing while the burn-down moves what is
already there. Existing files are tolerated through a committed list; only
*new* top-level files, or files in an unlisted family, fail.

Policy: `.maintainability/layout.json`
{
  "scripts": {
    "families": ["airvibe", "robustel", "mender", "headscale", "pi-bench", "ai-review", "ci"],
    "allow_top_level": ["edge-compose.sh"]
  }
}

Usage:
  check_layout.py --base <git-ref>   # CI
  check_layout.py --baseline         # (re)write the tolerated list from HEAD
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

POLICY = Path(".maintainability/layout.json")
TOLERATED = Path(".maintainability/layout-tolerated.txt")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def top_level_files(directory: str) -> list[str]:
    files = git("ls-files", "--", directory).splitlines()
    return sorted(f for f in files if f.count("/") == 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base")
    ap.add_argument("--baseline", action="store_true")
    args = ap.parse_args()

    if not POLICY.exists():
        print(f"check_layout: no {POLICY}; nothing to enforce")
        return 0
    policy = json.loads(POLICY.read_text())

    if args.baseline:
        lines: list[str] = []
        for directory in policy:
            lines += top_level_files(directory)
        TOLERATED.parent.mkdir(parents=True, exist_ok=True)
        TOLERATED.write_text("\n".join(lines) + "\n")
        print(f"check_layout: tolerating {len(lines)} existing top-level file(s)")
        return 0

    tolerated = set(TOLERATED.read_text().split()) if TOLERATED.exists() else set()
    added: list[str] = []
    if args.base:
        for line in git("diff", "--name-status", "-M", args.base, "HEAD").splitlines():
            parts = line.split("\t")
            if parts[0][0] in "AR":
                added.append(parts[-1])          # for R this is the new name

    bad: list[tuple[str, str]] = []
    for path in added:
        for directory, rules in policy.items():
            if not path.startswith(directory + "/"):
                continue
            rel = path[len(directory) + 1:]
            if "/" in rel:
                family = rel.split("/", 1)[0]
                if family not in rules.get("families", []):
                    bad.append((path, f"'{family}' is not a listed family of {directory}/"))
            elif rel in rules.get("allow_top_level", []) or path in tolerated:
                continue
            else:
                bad.append((path, f"new top-level file in {directory}/; "
                                  "put it in a family subdirectory"))

    if not bad:
        print(f"check_layout: {len(added)} added/renamed path(s), layout holds")
        return 0
    for path, why in bad:
        print(f"{path}: {why}")
    families = sorted({f for r in policy.values() for f in r.get("families", [])})
    print("\nFamilies:", ", ".join(families))
    return 1


if __name__ == "__main__":
    sys.exit(main())
