#!/usr/bin/env python3
"""Fail when a PR adds a new top-level file to a directory that is only
allowed to grow inside named family subdirectories.

This stops a flat directory from growing while the burn-down moves what is
already there. Existing files are tolerated through a committed list; only
*new* top-level files, or files in an unlisted family, fail.

Policy: `.maintainability/layout.json`
{
  "scripts": {
    "families": ["airvibe", "robustel", "mender", "headscale", "pi-bench",
                 "ai-review", "ci", "onboarding", "fixtures", "systemd"],
    "allow_top_level": ["edge-compose.sh", "org-up.sh", "org-down.sh"]
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


def write_baseline(policy: dict, allow_growth: bool) -> int:
    lines: list[str] = []
    for directory in policy:
        lines += top_level_files(directory)
    old = set(TOLERATED.read_text().split()) if TOLERATED.exists() else set()
    grown = sorted(set(lines) - old)
    if old and grown and not allow_growth:
        # A tolerated list is a record of what was there on day one. A new
        # top-level file reached HEAD past the gate; it is not tolerated.
        for path in grown:
            print(f"{path}: new top-level file; the tolerated list refuses to grow")
        return 1
    TOLERATED.parent.mkdir(parents=True, exist_ok=True)
    TOLERATED.write_text("\n".join(lines) + "\n")
    print(f"check_layout: tolerating {len(lines)} existing top-level file(s)")
    return 0


def added_since(base: str) -> list[str]:
    added: list[str] = []
    for line in git("diff", "--name-status", "-M", base, "HEAD").splitlines():
        parts = line.split("\t")
        if parts[0][0] in "AR":
            added.append(parts[-1])          # for R this is the new name
    return added


def violation(path: str, directory: str, rules: dict, tolerated: set[str]) -> str | None:
    rel = path[len(directory) + 1:]
    if "/" in rel:
        family = rel.split("/", 1)[0]
        if family not in rules.get("families", []):
            return f"'{family}' is not a listed family of {directory}/"
        return None
    if rel in rules.get("allow_top_level", []) or path in tolerated:
        return None
    return f"new top-level file in {directory}/; put it in a family subdirectory"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base")
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--allow-growth", action="store_true",
                    help="--baseline only: tolerate top-level files added since (first run)")
    args = ap.parse_args()

    if not POLICY.exists():
        print(f"check_layout: no {POLICY}; nothing to enforce")
        return 0
    policy = json.loads(POLICY.read_text())
    if args.baseline:
        return write_baseline(policy, args.allow_growth)

    tolerated = set(TOLERATED.read_text().split()) if TOLERATED.exists() else set()
    added = added_since(args.base) if args.base else []
    bad = [(path, why)
           for path in added
           for directory, rules in policy.items()
           if path.startswith(directory + "/")
           if (why := violation(path, directory, rules, tolerated))]

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
