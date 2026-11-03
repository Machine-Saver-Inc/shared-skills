#!/usr/bin/env python3
"""Render STATUS.md from the organisation Project board.

  gh project item-list <N> --owner <org> --format json --limit 500 \\
    | render_status.py > STATUS.md

The output is the only status file a repository holds. It is written by the
main-tier workflow and never by hand; its first line says so, which is what
`check_ledgers.py` looks for. No timestamp: the commit that writes it is the
timestamp, and a file that changes only its date is noise.
"""
from __future__ import annotations

import json
import sys

MARKER = "<!-- generated-by: scripts/ci/render_status.py from the project board; do not edit -->"
STATUS_ORDER = ["In Progress", "Blocked", "Todo", "Done"]


def field(item: dict, *names: str) -> str:
    for name in names:
        value = item.get(name)
        if isinstance(value, dict):
            value = value.get("name") or value.get("title")
        if value:
            return str(value)
    return ""


def line(item: dict) -> str:
    content = item.get("content") or {}
    number = content.get("number")
    title = content.get("title") or item.get("title") or "(untitled)"
    url = content.get("url", "")
    repo = (content.get("repository") or item.get("repository") or "").split("/")[-1]
    label = f"#{number} {title}" if number else title
    text = f"[{label}]({url})" if url else label
    tags = [t for t in (repo, field(item, "area"), field(item, "horizon")) if t]
    labels = item.get("labels") or []
    tags += [f"`{lb}`" for lb in labels]
    return f"- {text}" + (f" · {' · '.join(tags)}" if tags else "")


def main() -> int:
    data = json.load(sys.stdin)
    items = data.get("items", data if isinstance(data, list) else [])
    groups: dict[str, list[dict]] = {}
    for item in items:
        groups.setdefault(field(item, "status") or "No status", []).append(item)

    out = [MARKER, "", "# Status", ""]
    ordered = [s for s in STATUS_ORDER if s in groups] + sorted(
        s for s in groups if s not in STATUS_ORDER)
    for status in ordered:
        rows = sorted(groups[status], key=lambda i: (field(i, "horizon"), line(i)))
        out += [f"## {status} ({len(rows)})", ""] + [line(i) for i in rows] + [""]
    if not items:
        out += ["Nothing on the board.", ""]
    sys.stdout.write("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
