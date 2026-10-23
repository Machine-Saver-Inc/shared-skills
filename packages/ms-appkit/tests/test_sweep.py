"""The family sweep changes an application only when something is behind.

A sweep that touched ms-app.json on every run (bumping ``last_sweep``) opened a
date-only pull request for every current application every Monday; the first
run as the GitHub App did exactly that. Proved red on that version.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SWEEP = ROOT / "tools" / "sweep.py"
TEMPLATE = ROOT / "packages" / "ms-appkit" / "template"


def _sweep(app: Path, tag: str) -> str:
    done = subprocess.run([sys.executable, str(SWEEP), str(app), "--kind", "desktop", "--tag", tag,
                           "--kit-checkout", str(ROOT), "--no-rules"],
                          check=True, capture_output=True, text=True)
    return done.stdout


def _snapshot(app: Path) -> dict[str, bytes]:
    return {str(p.relative_to(app)): p.read_bytes()
            for p in app.rglob("*") if p.is_file()}


def test_sweep_leaves_a_current_application_untouched(tmp_path: Path) -> None:
    app = tmp_path / "app"
    shutil.copytree(TEMPLATE, app)
    manifest = json.loads((app / "ms-app.json").read_text(encoding="utf-8"))
    tag = f"ms-appkit/v{manifest['kit']['version']}"

    first = _sweep(app, tag)              # brings the copy fully current (last_sweep, pins)
    before = _snapshot(app)
    second = _sweep(app, tag)             # nothing is behind now
    assert _snapshot(app) == before, "a second sweep at the same tag changed files"
    assert "already current" in second
    assert "refreshed" not in second or "refreshed" in first


def test_sweep_moves_a_stale_pin_and_dates_it(tmp_path: Path) -> None:
    app = tmp_path / "app"
    shutil.copytree(TEMPLATE, app)
    manifest = json.loads((app / "ms-app.json").read_text(encoding="utf-8"))
    current = manifest["kit"]["version"]
    out = _sweep(app, "ms-appkit/v9.9.9")
    after = json.loads((app / "ms-app.json").read_text(encoding="utf-8"))
    assert after["kit"]["version"] == "9.9.9" and after["kit"]["version"] != current
    assert after["last_sweep"] != manifest.get("last_sweep")
    assert "pinned to ms-appkit/v9.9.9" in out
