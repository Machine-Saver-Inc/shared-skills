#!/usr/bin/env python3
"""Choose the next maintainability burn-down target and police its change (ADR 0022).

  burndown_pick.py pick [--kind K] [--skip-file F] [--now EPOCH]  > target.json
  burndown_pick.py check-patch --target target.json --patch change.patch < touched.txt
  burndown_pick.py verify --target target.json --findings tool-output.txt

`pick` reads the committed baselines and the tree and prints one target as
JSON, or `{}` when there is nothing to do. Order, safest first:

  retire  a `*_candidate*` file under scripts/ untouched for 60 days that
          nothing outside itself and its own test names, by path, basename or
          dotted import
  delete  one vulture finding (dead Python)
  dedupe  one jscpd pair

Moving files into their families is not a burn-down kind yet: a move has to
carry path-keyed baseline findings, root-relative arithmetic and package
closures with it, and that needs its own design (#181).

Keys in --skip-file (rejected PRs and recorded declines) are passed over, so a
rejected change is never proposed twice.

`check-patch` is the open job's gate on a change it did not make: every touched
path (the list on stdin, taken from the index after `git apply --index`) must
be one the target allows, nothing may be forbidden, and the patch may carry no
symlink, submodule, mode change or binary content. `verify` proves the
target's own finding is gone from a fresh tool run.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_layout import POLICY, violation
from check_path_references import find_references
from ratchet import normalise

KINDS = ("retire", "delete", "dedupe")
RETIRE_AGE_DAYS = 60
MAINT = Path(".maintainability")
# Never changed by burn-down in any repo: workflows, review machinery, the gates
# and their baselines, decisions, house rules, release files.
FORBIDDEN = (".github/", ".maintainability/", "scripts/ci/", "docs/adr/",
             "AGENTS.md", "CLAUDE.md", "renovate.json", "release-please-config.json",
             ".release-please-manifest.json", "CHANGELOG.md")
# Each repo adds its own in `.maintainability/burndown.json`, read from HEAD so
# a patch cannot widen its own reach: {"forbidden": ["edge/base/", ...]}.
BURNDOWN_CONFIG = MAINT / "burndown.json"
HELPER_SUFFIXES = (".py", ".sh", ".ps1")
GENERATED = {"CONTEXT.md", "STATUS.md"}
DELETABLE = {"import", "function", "class", "method", "attribute", "property"}
# Segments of letters, digits, `_`, `@`, `.` and `-`, none starting with `.`
# or `-`: no whitespace, quotes or shell characters, no `.`/`..`/empty segment,
# nothing absolute.
PLAIN_PATH = re.compile(r"[A-Za-z0-9_@][A-Za-z0-9._@-]*(?:/[A-Za-z0-9_@][A-Za-z0-9._@-]*)*")
VULTURE = re.compile(r"^(?P<path>\S+): unused (?P<what>[\w ]+?) '(?P<name>[^']+)'")
JSCPD = re.compile(r"^(?P<fmt>\w+): (?P<a>\S+) \+ (?P<b>\S+)$")
UNSAFE_PATCH = re.compile(
    r"^(old mode |new mode |(new|deleted) file mode (?!100644$|100755$)|GIT binary patch|Binary files )|\x00",
    re.MULTILINE)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


@functools.lru_cache(maxsize=1)
def repo_forbidden() -> tuple[str, ...]:
    try:
        extra = json.loads(git("show", f"HEAD:{BURNDOWN_CONFIG.as_posix()}")).get("forbidden", [])
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, AttributeError):
        return ()
    return tuple(p for p in extra if isinstance(p, str) and p)


def forbidden(path: str) -> bool:
    return any(path == f or (f.endswith("/") and path.startswith(f))
               for f in FORBIDDEN + repo_forbidden())


def referrers(path: str) -> list[str]:
    """Files that name `path`: the reference index (full path and basename), the
    bare stem as a whole word anywhere (imports, `"stem"` in a packager's list,
    `import a, stem`), and for Python the dotted module name. A retire deletes,
    so any mention at all keeps the file."""
    found = {r[0] for r in find_references(Path("."), [path])}
    searches = [["-w", "-F", "-e", PurePosixPath(path).stem]]
    if path.endswith(".py"):
        searches.append(["-F", "-e", path[:-3].replace("/", ".")])
    for args in searches:
        hits = subprocess.run(["git", "grep", "-l", *args], check=False, capture_output=True, text=True)
        found |= {h for h in hits.stdout.splitlines() if h}
    return sorted(f for f in found - {path} if not generated(f))


def generated(path: str) -> bool:
    """Files the main tier rewrites from the tree (ADR 0019, ADR 0020). They list
    every script, so a mention there keeps nothing alive, and refresh drops it."""
    return path.startswith(".maintainability/") or path in GENERATED


def key_for(kind: str, ident: str) -> str:
    """Readable and unique: a slug of the target plus a hash of all of it."""
    slug = re.sub(r"[^a-z0-9]+", "-", ident.lower()).strip("-")[:48].strip("-")
    return f"{kind}-{slug}-{hashlib.sha1(ident.encode('utf-8')).hexdigest()[:8]}"


def lines(path: Path) -> list[str]:
    return [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] \
        if path.exists() else []


def last_commit_age_days(path: str, now: float) -> float:
    stamp = git("log", "-1", "--format=%ct", "--", path).strip()
    return (now - int(stamp)) / 86400 if stamp else 0.0


def companion_test(path: str) -> str | None:
    p = Path(path)
    for name in (f"test_{p.name}", f"test-{p.name}"):
        cand = (p.parent / name).as_posix()
        if Path(cand).exists():
            return cand
    return None


def is_candidate(path: str) -> bool:
    """One definition, shared with the panel (render_maintainability.py P1), so
    the count a human reads is the count the bot acts on."""
    name = Path(path).name
    return "_candidate" in name and not name.startswith(("test_", "test-"))


def pick_retire(now: float, skip: set[str]) -> dict | None:
    files = [f for f in git("ls-files", "scripts").splitlines() if is_candidate(f)]
    for path in sorted(files):
        key = key_for("retire", path)
        if key in skip or forbidden(path) or last_commit_age_days(path, now) < RETIRE_AGE_DAYS:
            continue
        test = companion_test(path)
        own = sorted({path, test} - {None})
        outside = sorted({r for p in own for r in referrers(p)} - set(own))
        if outside:
            continue
        return {"kind": "retire", "key": key, "paths": own,
                "evidence": f"{path}: last changed {last_commit_age_days(path, now):.0f} days "
                            f"ago; nothing outside {', '.join(own)} names it by path, "
                            "basename or import."}
    return None


def pick_delete(skip: set[str]) -> dict | None:
    for line in lines(MAINT / "vulture.baseline"):
        m = VULTURE.match(line)
        if not m or forbidden(m["path"]) or not Path(m["path"]).exists():
            continue
        # An "unused variable" is usually a parameter an interface requires
        # (a callback, a protocol method); vulture cannot know. Not worth a run.
        if m["what"] not in DELETABLE:
            continue
        # A test module's "unused" import is how a TestCase from elsewhere
        # gets run; removing it drops those tests from CI without a trace.
        if m["what"] == "import" and Path(m["path"]).name.startswith(("test_", "test-")):
            continue
        key = key_for("delete", line)
        if key not in skip:
            return {"kind": "delete", "key": key, "paths": [m["path"]], "finding": line,
                    "evidence": f"vulture: {line}"}
    return None


def pick_dedupe(skip: set[str]) -> dict | None:
    for line in lines(MAINT / "jscpd.baseline"):
        m = JSCPD.match(line)
        if not m or any(forbidden(p) or not Path(p).exists() for p in (m["a"], m["b"])):
            continue
        key = key_for("dedupe", line)
        if key not in skip:
            return {"kind": "dedupe", "key": key, "paths": sorted({m["a"], m["b"]}),
                    "finding": line, "evidence": f"jscpd: {line}"}
    return None


def pick(kind: str | None, skip: set[str], now: float) -> dict:
    pickers = {"retire": lambda: pick_retire(now, skip), "delete": lambda: pick_delete(skip),
               "dedupe": lambda: pick_dedupe(skip)}
    for k in ([kind] if kind else list(KINDS)):
        target = pickers[k]()
        if target:
            return target
    return {}


def load_layout(ref: str = "HEAD") -> dict:
    """The layout policy as committed at `ref`, never as a patch left it."""
    try:
        return json.loads(git("show", f"{ref}:{POLICY.as_posix()}"))
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return {}


def helper_dirs(paths: list[str], layout: dict) -> set[str]:
    """Where a dedupe may add its one helper: beside the target's files, or,
    where that directory may only grow in families (check_layout), in one of
    its listed families."""
    dirs = set()
    for p in paths:
        parent = PurePosixPath(p).parent.as_posix()
        rules = layout.get(parent)
        dirs |= {f"{parent}/{f}" for f in rules.get("families", [])} if rules else {parent}
    return {d for d in dirs if not forbidden(d + "/")}


def layout_allows(path: str, layout: dict) -> bool:
    return not any(violation(path, d, rules, set())
                   for d, rules in layout.items() if path.startswith(d + "/"))


def patch_problems(target: dict, touched: dict[str, str], patch: str,
                   layout: dict | None = None) -> list[str]:
    """Why the open job must refuse this change; empty when it may proceed.

    `touched` maps each path to its index status, A (added), M (modified) or
    D (deleted), from `git diff --cached --name-status --no-renames`."""
    layout = layout or {}
    kind = target.get("kind")
    allowed = set(target.get("paths", []))
    homes = helper_dirs(sorted(allowed), layout)
    problems, helpers = [], []
    for p, status in sorted(touched.items()):
        pp = PurePosixPath(p)
        if not PLAIN_PATH.fullmatch(p):
            problems.append(f"{p!r}: not a plain repository path")
            continue
        if forbidden(p):
            problems.append(f"{p}: forbidden path")
        elif kind == "retire":
            if p not in allowed or status != "D":
                problems.append(f"{p}: a retire may only delete the target's paths")
        elif p in allowed:
            if status != "M":
                problems.append(f"{p}: the target's files may be edited, not {status}")
        elif (kind == "dedupe" and status == "A" and pp.parent.as_posix() in homes
                and pp.suffix in HELPER_SUFFIXES
                and layout_allows(p, layout)):
            helpers.append(p)
        else:
            problems.append(f"{p}: not a path this target may change")
    if len(helpers) > 1:
        problems.append(f"more than one new helper: {helpers}")
    if kind == "retire" and set(touched) != allowed:
        problems.append("a retire must delete exactly the target's paths")
    for m in UNSAFE_PATCH.finditer(patch):
        problems.append(f"unsafe patch line: {m.group(0).strip()}")
    return problems


def content_problems(touched: dict[str, str], root: Path = Path(".")) -> list[str]:
    """Judge the files as they will be committed, not the patch that made them:
    a text hunk can still leave binary bytes, which a reviewer is never shown."""
    problems = []
    for p, status in sorted(touched.items()):
        if status == "D":
            continue
        f = root / p
        if f.is_symlink() or not f.is_file():
            problems.append(f"{p}: not a regular file")
        elif b"\0" in f.read_bytes():
            problems.append(f"{p}: binary content")
    return problems


def parse_name_status(raw: str) -> dict[str, str]:
    """`git diff --name-status -z` output: status NUL path NUL, repeated."""
    parts = raw.split("\0")
    if parts and parts[-1] == "":
        parts.pop()
    return {parts[i + 1]: parts[i] for i in range(0, len(parts) - 1, 2)}


def verify(target: dict, findings: list[str]) -> bool:
    """True when the target's own finding is absent from a fresh tool run."""
    if "finding" not in target:
        return True
    return not any(normalise(f) == target["finding"] for f in findings)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pick")
    p.add_argument("--kind", choices=KINDS, default=None)
    p.add_argument("--skip-file", type=Path, default=None)
    p.add_argument("--now", type=float, default=None)
    c = sub.add_parser("check-patch")
    c.add_argument("--target", type=Path, required=True)
    c.add_argument("--patch", type=Path, required=True)
    c.add_argument("--paths-out", type=Path, default=None,
                   help="write the accepted paths here, NUL-separated, for the commit")
    v = sub.add_parser("verify")
    v.add_argument("--target", type=Path, required=True)
    v.add_argument("--findings", type=Path, required=True)
    v.add_argument("--expect-present", action="store_true",
                   help="succeed when the target is still there to remove (the base tree)")
    args = ap.parse_args()

    if args.cmd == "pick":
        skip = set(lines(args.skip_file)) if args.skip_file else set()
        print(json.dumps(pick(args.kind, skip, args.now or time.time()), indent=2))
        return 0
    target = json.loads(args.target.read_text(encoding="utf-8"))
    if args.cmd == "check-patch":
        return check_patch_cli(target, args.patch, args.paths_out)
    return verify_cli(target, lines(args.findings), args.expect_present)


def check_patch_cli(target: dict, patch: Path, paths_out: Path | None) -> int:
    touched = parse_name_status(sys.stdin.read())
    problems = patch_problems(target, touched, patch.read_text(encoding="utf-8", errors="replace"),
                              load_layout()) or content_problems(touched)
    if not touched:
        problems.append("the change touches nothing")
    for problem in problems:
        print(f"burndown_pick: {problem}", file=sys.stderr)
    if problems:
        return 2
    if paths_out:
        paths_out.write_text("".join(p + "\0" for p in sorted(touched)), encoding="utf-8")
    return 0


def verify_cli(target: dict, findings: list[str], expect_present: bool) -> int:
    """After the change: 0 when the target is gone. On the base tree
    (`expect_present`): 0 when it is still there to remove."""
    gone = verify(target, findings)
    if expect_present:
        gone = gone if "finding" in target else not all(Path(p).exists() for p in target["paths"])
        print(f"burndown_pick: {target.get('key')} is {'already gone' if gone else 'there to remove'}")
        return 1 if gone else 0
    print(f"burndown_pick: {target.get('key')} is {'gone' if gone else 'still reported'}")
    return 0 if gone else 1


if __name__ == "__main__":
    sys.exit(main())
