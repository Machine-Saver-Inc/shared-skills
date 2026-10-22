#!/usr/bin/env python3
"""Every skill and kit says the version its header claims, and the CHANGELOG knows it.

    python tools/check_versions.py

Four artifacts, two pairs. A pair moves together: a change to a kit bumps the
kit, and bumps its skill when it changes what the skill says. The mobile skill
also names the desktop skill it is the counterpart of, and that must be the
desktop skill's current version. No tomllib: the CI matrix starts at 3.10.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def find(pattern: str, path: str) -> str:
    text = (ROOT / path).read_text(encoding="utf-8")
    found = re.search(pattern, text, re.M)
    assert found, f"{pattern} not found in {path}"
    return found.group(1)


def main() -> int:
    desktop_skill = find(r"^\*\*Skill version ([0-9.]+)\.\*\*", "skills/ms-desktop-app/SKILL.md")
    appkit = find(r'^version = "([0-9.]+)"', "packages/ms-appkit/pyproject.toml")
    stamped = find(r'^__version__ = "([0-9.]+)"', "packages/ms-appkit/src/ms_appkit/_version.py")
    mobile_skill = find(r"^\*\*Skill version ([0-9.]+)\.\*\*", "skills/ms-mobile-app/SKILL.md")
    counterpart = find(r"counterpart of `ms-desktop-app` \*\*([0-9.]+)\*\*", "skills/ms-mobile-app/SKILL.md")
    mobilekit = json.loads((ROOT / "packages/ms-mobilekit/package.json").read_text(encoding="utf-8"))["version"]

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    mobile_changelog = (ROOT / "packages/ms-mobilekit/CHANGELOG.md").read_text(encoding="utf-8")
    template_manifest = json.loads((ROOT / "packages/ms-appkit/template/ms-app.json").read_text(encoding="utf-8"))

    faults = []
    if stamped != appkit:
        faults.append(f"_version.py says {stamped}, pyproject.toml says {appkit}")
    for name, version in (("ms-desktop-app", desktop_skill), ("ms-appkit", appkit),
                          ("ms-mobile-app", mobile_skill), ("ms-mobilekit", mobilekit)):
        if f"{name} {version}" not in changelog:
            faults.append(f"{name} {version} has no entry in CHANGELOG.md")
    if f"## [{mobilekit}]" not in mobile_changelog:
        faults.append(f"ms-mobilekit {mobilekit} has no entry in packages/ms-mobilekit/CHANGELOG.md")
    if counterpart != desktop_skill:
        faults.append(f"the mobile skill says it is the counterpart of ms-desktop-app {counterpart}; "
                      f"the desktop skill is {desktop_skill}")
    if template_manifest["kit"]["version"] != appkit or template_manifest["skill"]["version"] != desktop_skill:
        faults.append("packages/ms-appkit/template/ms-app.json does not name the current kit and skill")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for version in (desktop_skill, appkit, mobile_skill, mobilekit):
        if f"**{version}**" not in readme:
            faults.append(f"README.md's version table does not show {version}")
    for line in faults:
        print(f"  {line}")
    print(f"ms-desktop-app {desktop_skill}, ms-appkit {appkit}, ms-mobile-app {mobile_skill}, "
          f"ms-mobilekit {mobilekit}; {len(faults)} faults")
    return 1 if faults else 0


if __name__ == "__main__":
    sys.exit(main())
