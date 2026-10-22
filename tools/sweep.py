#!/usr/bin/env python3
"""Bring one application up to a kit tag: pin, template files, manifest, house rules.

    python tools/sweep.py <app root> --kind desktop|mobile --tag ms-appkit/v1.5.0 \
        --kit-checkout <shared-skills root> [--report sweep-report.md]

What it changes in the application's working tree:

* the kit pin (``pyproject.toml`` dependency ref, or ``package.json`` ``msKit.ref``);
* every file the kit's template marks (``ms-appkit template vN``), refreshed
  from the template with the application's own names put back; anything the
  application wrote below ``# --- app-specific ---`` in its house-rules test
  is kept;
* ``ms-app.json``: kit version, skill version, ``last_sweep``.

Then it installs the application and runs its house rules. Exit code 0: rules
pass; 1: rules fail (the report names them); 2: nothing could be done (no
manifest, unknown kind). The family-sweep workflow opens the pull request; a
person can run this by hand for the same result.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

TEMPLATE_MARKED = {
    "desktop": ("tests/test_house_rules.py", ".github/workflows/ci.yml"),
    "mobile": ("tests/house_rules.test.mjs", ".github/workflows/ci.yml"),
}
APP_SPECIFIC = "# --- app-specific ---"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def skill_version(kit_root: Path, kind: str) -> str:
    skill = "ms-desktop-app" if kind == "desktop" else "ms-mobile-app"
    text = read(kit_root / "skills" / skill / "SKILL.md")
    return re.search(r"^\*\*Skill version ([0-9.]+)\.\*\*", text, re.MULTILINE).group(1)


def move_pin(app: Path, kind: str, tag: str, log: list[str]) -> None:
    if kind == "desktop":
        path = app / "pyproject.toml"
        text = read(path)
        new, count = re.subn(
            r"(ms-appkit(?:\[[\w,]+\])?\s*@\s*git\+https://github\.com/Machine-Saver-Inc/shared-skills(?:\.git)?)(?:@[^#\s\"']+)?(#subdirectory=packages/ms-appkit)",
            rf"\1@{tag}\2", text)
        if count:
            write(path, new)
            log.append(f"pyproject.toml: ms-appkit pinned to {tag}")
        else:
            log.append("pyproject.toml: no ms-appkit dependency line found (left alone)")
    else:
        path = app / "package.json"
        data = json.loads(read(path))
        data.setdefault("msKit", {"repo": "Machine-Saver-Inc/shared-skills"})["ref"] = tag
        write(path, json.dumps(data, indent=2) + "\n")
        log.append(f"package.json: msKit.ref set to {tag}")


def names_for(app: Path, kind: str) -> dict[str, str]:
    """What the template's example names are called in this application."""
    manifest = json.loads(read(app / "ms-app.json"))
    if kind == "desktop":
        return {"example_app": manifest["package"], "example-tool": manifest["slug"],
                "Example Tool": manifest["name"]}
    return {"example-tool": manifest["slug"], "Example Tool": manifest["name"],
            "net.machinesaver.example": manifest.get("appId", "net.machinesaver.example")}


def refresh_template_files(app: Path, kind: str, kit_root: Path, log: list[str]) -> None:
    template = kit_root / "packages" / ("ms-appkit" if kind == "desktop" else "ms-mobilekit") / "template"
    names = names_for(app, kind)
    for relative in TEMPLATE_MARKED[kind]:
        source = template / relative
        target = app / relative
        if not source.is_file():
            continue
        fresh = read(source)
        for old, new in names.items():
            fresh = fresh.replace(old, new)
        if target.is_file() and relative.startswith("tests/"):
            current = read(target)
            if APP_SPECIFIC in current:
                kept = current[current.index(APP_SPECIFIC) + len(APP_SPECIFIC):]
                if APP_SPECIFIC in fresh:
                    fresh = fresh[: fresh.index(APP_SPECIFIC) + len(APP_SPECIFIC)] + kept
        if not target.is_file() or read(target) != fresh:
            write(target, fresh)
            log.append(f"{relative}: refreshed from the kit's template")


def bump_manifest(app: Path, kind: str, tag: str, kit_root: Path, log: list[str]) -> None:
    path = app / "ms-app.json"
    data = json.loads(read(path))
    data["kit"] = {"name": tag.split("/v")[0], "version": tag.split("/v")[1]}
    data["skill"] = {"name": "ms-desktop-app" if kind == "desktop" else "ms-mobile-app",
                     "version": skill_version(kit_root, kind)}
    data["last_sweep"] = dt.date.today().isoformat()
    write(path, json.dumps(data, indent=2) + "\n")
    log.append(f"ms-app.json: kit {data['kit']['version']}, skill {data['skill']['version']}")


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)


def house_rules(app: Path, kind: str) -> tuple[bool, str]:
    if kind == "desktop":
        install = run([sys.executable, "-m", "pip", "install", "-q", "-e", ".[dev]"], app)
        if install.returncode:
            return False, "pip install failed:\n" + install.stdout[-2000:] + install.stderr[-2000:]
        done = run([sys.executable, "-m", "pytest", "-q", "-rs", "tests/test_house_rules.py"], app)
    else:
        install = run(["npm", "install", "--no-audit", "--no-fund"], app)
        if install.returncode:
            return False, "npm install failed:\n" + install.stdout[-2000:] + install.stderr[-2000:]
        done = run(["node", "--test", "tests/house_rules.test.mjs"], app)
    output = (done.stdout + done.stderr)[-6000:]
    return done.returncode == 0, output


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("app")
    parser.add_argument("--kind", choices=("desktop", "mobile"), required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--kit-checkout", required=True)
    parser.add_argument("--report", default="")
    parser.add_argument("--no-rules", action="store_true", help="change files only; do not install or test")
    args = parser.parse_args(argv)
    app = Path(args.app).resolve()
    kit_root = Path(args.kit_checkout).resolve()
    log: list[str] = []

    if not (app / "ms-app.json").is_file():
        report = ("No ms-app.json: this application predates the manifest. Copy "
                  "template/ms-app.json, fill it in, and run the sweep again.")
        if args.report:
            write(Path(args.report), report + "\n")
        print(report)
        return 2

    move_pin(app, args.kind, args.tag, log)
    refresh_template_files(app, args.kind, kit_root, log)
    bump_manifest(app, args.kind, args.tag, kit_root, log)

    passed, output = (True, "(rules not run)") if args.no_rules else house_rules(app, args.kind)
    lines = ["## What the sweep changed", *[f"- {item}" for item in log], "",
             f"## House rules at {args.tag}: {'pass' if passed else 'FAIL'}", "", "```", output.strip(), "```"]
    report = "\n".join(lines) + "\n"
    if args.report:
        write(Path(args.report), report)
    print(report)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
