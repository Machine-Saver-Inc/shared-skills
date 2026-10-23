#!/usr/bin/env python3
"""registry/report-form.json is the one Report a problem form; the kits carry
copies of it so a frozen program needs no network to draw the dialog. This
checks the file's shape and that every copy is byte-for-byte the registry's.

    python tools/check_report_form.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "registry" / "report-form.json"
COPIES = (
    ROOT / "packages" / "ms-appkit" / "src" / "ms_appkit" / "resources" / "report_form.json",
    ROOT / "packages" / "ms-mobilekit" / "src" / "report_form.json",
)
KEYS = {"schema", "about", "intake_url", "kinds", "fields", "attachments", "wording"}
FIELDS = {"kind", "app_version", "title", "body_markdown", "email", "files"}
WORDING = {"heading", "intro", "details_note", "send", "copy", "cancel", "sending",
           "received_private", "received_public", "failed", "refused_prefix"}


def faults() -> list[str]:
    found: list[str] = []
    try:
        form = json.loads(SOURCE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"{SOURCE.name}: {error}"]
    if set(form) != KEYS:
        found.append(f"top-level keys must be {sorted(KEYS)}, got {sorted(form)}")
    if not form.get("intake_url", "").startswith("https://"):
        found.append("intake_url must be an https address")
    kinds = form.get("kinds") or []
    if [k.get("value") for k in kinds] != ["bug", "improvement"]:
        found.append("kinds must be bug then improvement; the intake labels issues by them")
    if set(form.get("fields", {})) != FIELDS:
        found.append(f"fields must be {sorted(FIELDS)}")
    limits = form.get("attachments", {})
    for key in ("max_files", "max_file_mb", "max_total_mb"):
        if not isinstance(limits.get(key), int) or limits[key] <= 0:
            found.append(f"attachments.{key} must be a positive whole number")
    if limits.get("max_file_mb", 0) > limits.get("max_total_mb", 0):
        found.append("one file may not be larger than all files together")
    if "png" not in limits.get("extensions", []):
        found.append("attachments.extensions must allow png, or no screenshot can be pasted")
    if set(form.get("wording", {})) != WORDING:
        found.append(f"wording must have exactly {sorted(WORDING)}")
    source = SOURCE.read_bytes()
    for copy in COPIES:
        if not copy.is_file():
            found.append(f"{copy.relative_to(ROOT)} is missing; copy registry/report-form.json there")
        elif copy.read_bytes() != source:
            found.append(f"{copy.relative_to(ROOT)} differs from registry/report-form.json; copy it again")
    return found


def main() -> int:
    found = faults()
    for line in found:
        print(f"  {line}")
    print(f"report form: {len(found)} faults")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
