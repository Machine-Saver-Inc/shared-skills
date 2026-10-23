#!/usr/bin/env python3
"""Check registry/apps.yaml: shape, uniqueness, and the rules the schema cannot say.

    python tools/check_registry.py            # the file's shape and cross-entry rules
    python tools/check_registry.py --github   # also that every repository exists (needs gh)

Standard library plus PyYAML; no jsonschema dependency, so the few rules the
schema file states are checked here by hand and the schema stays the readable
statement of the contract for the catalog and the intake service.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "apps.yaml"
SCHEMA = ROOT / "registry" / "schema.json"


def load():
    import yaml  # PyYAML; installed by CI, present in any dev environment

    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))


def faults(entries, schema: dict) -> list[str]:
    found: list[str] = []
    if not isinstance(entries, list) or not entries:
        return ["apps.yaml must be a non-empty list of applications"]
    props = schema["items"]["properties"]
    required = set(schema["items"]["required"])
    seen_slugs: dict[str, int] = {}
    seen_repos: dict[str, int] = {}
    for index, entry in enumerate(entries):
        where = f"entry {index + 1} ({entry.get('slug', '?') if isinstance(entry, dict) else '?'})"
        if not isinstance(entry, dict):
            found.append(f"{where}: not a mapping")
            continue
        missing = required - set(entry)
        extra = set(entry) - set(props)
        if missing:
            found.append(f"{where}: missing {sorted(missing)}")
        if extra:
            found.append(f"{where}: unknown fields {sorted(extra)}")
        for key, spec in props.items():
            if key not in entry:
                continue
            value = entry[key]
            if "enum" in spec and value not in spec["enum"]:
                found.append(f"{where}: {key} must be one of {spec['enum']}, not {value!r}")
            if "pattern" in spec and (not isinstance(value, str) or not re.fullmatch(spec["pattern"], value)):
                found.append(f"{where}: {key} {value!r} does not match {spec['pattern']}")
            if spec.get("type") == "string" and isinstance(value, str) and (
                    len(value) < spec.get("minLength", 0) or len(value) > spec.get("maxLength", 10**9)):
                found.append(f"{where}: {key} must be {spec.get('minLength', 0)} to "
                             f"{spec.get('maxLength', 'any')} characters")
        catalog = entry.get("catalog")
        if isinstance(catalog, dict):
            for flag in ("listed", "public"):
                if not isinstance(catalog.get(flag), bool):
                    found.append(f"{where}: catalog.{flag} must be true or false")
            if catalog.get("public") and entry.get("visibility") == "private":
                found.append(f"{where}: a private application cannot be in the public catalog")
        issues = entry.get("issues")
        if isinstance(issues, dict):
            if not re.fullmatch(props["issues"]["properties"]["repo"]["pattern"], str(issues.get("repo", ""))):
                found.append(f"{where}: issues.repo must be a Machine-Saver-Inc repository")
            labels = issues.get("labels", [])
            if not isinstance(labels, list) or len(labels) > 5 or not all(isinstance(l, str) and l for l in labels):
                found.append(f"{where}: issues.labels must be up to five non-empty strings")
        else:
            found.append(f"{where}: issues must be a mapping")
        allowed_kits = {"desktop": ("ms-appkit", "none"), "mobile": ("ms-mobilekit", "none"),
                        "script": ("none",)}.get(entry.get("kind"), ())
        if "kit" in entry and allowed_kits and entry["kit"] not in allowed_kits:
            found.append(f"{where}: a {entry['kind']} application's kit must be one of {list(allowed_kits)}, not {entry['kit']!r}")
        # A private desktop program's downloads sit behind a machinesaver.net
        # sign-in in the release store; a public one's on GitHub, where anyone
        # can fetch them. Anything else either hides a public program or
        # publishes a private one.
        if entry.get("kind") == "desktop" and entry.get("visibility") == "private" \
                and entry.get("releases") != "gcs":
            found.append(f"{where}: a private desktop program releases to the Machine Saver "
                         "release store; releases must be gcs")
        if entry.get("kind") == "desktop" and entry.get("visibility") == "public" \
                and entry.get("releases") == "gcs":
            found.append(f"{where}: a public desktop program releases on GitHub; the release "
                         "store needs a machinesaver.net sign-in")
        if entry.get("kind") == "script" and entry.get("releases") not in ("none", "github"):
            found.append(f"{where}: a script has no release store; releases must be none or github")
        slug = entry.get("slug")
        if slug in seen_slugs:
            found.append(f"{where}: slug repeats entry {seen_slugs[slug]}")
        seen_slugs.setdefault(slug, index + 1)
        repo = entry.get("repo")
        if repo in seen_repos:
            found.append(f"{where}: repo repeats entry {seen_repos[repo]}")
        seen_repos.setdefault(repo, index + 1)
    return found


def github_faults(entries) -> list[str]:
    found = []
    for entry in entries:
        for key in ("repo", ("issues", "repo")):
            repo = entry[key] if isinstance(key, str) else entry[key[0]][key[1]]
            result = subprocess.run(["gh", "api", f"repos/{repo}", "-q", ".private"],
                                    check=False, capture_output=True, text=True)
            if result.returncode != 0:
                found.append(f"{entry['slug']}: {repo} is not reachable ({result.stderr.strip()[:80]})")
            elif isinstance(key, str):
                private = result.stdout.strip() == "true"
                declared = entry["visibility"] == "private"
                if private != declared:
                    found.append(f"{entry['slug']}: visibility says {entry['visibility']} but the "
                                 f"repository is {'private' if private else 'public'}")
    return found


def main(argv: list[str]) -> int:
    entries = load()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    found = faults(entries, schema)
    if "--github" in argv:
        found += github_faults(entries)
    for line in found:
        print(f"  {line}")
    print(f"{len(entries)} applications, {len(found)} faults")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
