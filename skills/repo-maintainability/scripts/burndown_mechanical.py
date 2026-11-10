#!/usr/bin/env python3
"""Apply a `retire` burn-down target without a model (ADR 0022).

  burndown_mechanical.py --target target.json

`git rm` the candidate and its own test. The picker has already shown that
nothing else names them by path, basename or dotted import, and the work job's
gates check that again after the removal.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=Path, required=True)
    args = ap.parse_args()
    target = json.loads(args.target.read_text(encoding="utf-8"))
    if target.get("kind") != "retire":
        print("burndown_mechanical: only retire is mechanical", file=sys.stderr)
        return 2
    subprocess.run(["git", "rm", "-q", "--", *target["paths"]], check=True)
    print(f"burndown_mechanical: retire {target['key']}: {len(target['paths'])} path(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
