#!/usr/bin/env python3
"""Fail when a pull request body names no issue and no ADR.

A PR that serves no issue leaves no trace on the project board once it is
merged. Accepted forms: `#123`, an issue URL, or `ADR 0019` / `ADR-0019`.

Usage:
  check_pr_links.py --body-file <file>    # the workflow writes the PR body here
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ISSUE_REF = re.compile(r"(?<![\w/])#\d+\b")
ISSUE_URL = re.compile(r"github\.com/[\w.-]+/[\w.-]+/(issues|pull)/\d+")
ADR_REF = re.compile(r"\bADR[ -]?\d{4}\b")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--body-file", required=True, type=Path)
    args = ap.parse_args()

    body = args.body_file.read_text(encoding="utf-8") if args.body_file.exists() else ""
    found = ISSUE_REF.findall(body) + ISSUE_URL.findall(body) + ADR_REF.findall(body)
    if found:
        print(f"check_pr_links: names {len(found)} issue/ADR reference(s)")
        return 0
    print("check_pr_links: the PR body names no issue and no ADR.\n"
          "Add 'Closes #N' or 'Refs #N' for the issue this PR serves, or the ADR "
          "it implements. Open the issue first if there is none.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
