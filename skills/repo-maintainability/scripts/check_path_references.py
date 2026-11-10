#!/usr/bin/env python3
"""Fail when a file under a watched directory is moved or deleted while
something in the repository still names it.

A code graph resolves imports and calls. A repository like `platform` invokes
most of its scripts by *string* -- from Makefiles, workflow `run:` steps,
Dockerfiles, systemd units, compose files, TSV manifests, runbooks and sibling
wrappers -- and a graph is blind to every one of those. This check is the
complement: a textual index of every file in the repo, matched against every
watched filename by full relative path and by bare basename.

Usage:
  check_path_references.py --base <git-ref>              # CI: diff against base
  check_path_references.py --removed a.py --removed b.sh # explicit list
  check_path_references.py --index                       # print the whole index
  check_path_references.py --docs                        # instruction files name real paths

Exit 1 on any dangling reference, printed as
  <referrer>:<line>: still names <watched file>
or, for --docs,
  <instruction file>:<line>: names a path that does not exist: <path>

Watched directories and skip rules come from `.maintainability/layout.json`
when it exists (its top-level keys), else `scripts/`.

`--docs` is the other direction: the files every agent and every newcomer
loads first (README.md, AGENTS.md, edge/AGENTS.md, Makefile) may only name
paths that exist. README.md pointed at a document outside the repository from
its first commit; nothing noticed because nothing checked.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_WATCH = ("scripts",)
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build",
             ".maintainability"}   # baselines are records of findings, not consumers
# Records, not consumers: a decision or an archive names a path as it was,
# and must keep doing so after the move. Runbooks are consumers and stay in.
RECORD_PATHS = ("docs/adr/", "docs/archive/")
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip",
                   ".gz", ".tar", ".whl", ".pyc", ".so", ".exe", ".dll"}
MIN_BASENAME_LEN = 8          # shorter basenames match everywhere
GENERIC_BASENAMES = {"index.js", "main.py", "setup.sh", "test.sh", "README.md",
                     "__init__.py"}

# --docs: the always-loaded instruction files, and what counts as a path in them.
DOC_FILES = ("README.md", "AGENTS.md", "edge/AGENTS.md", "Makefile")
DOC_SUFFIXES = (".md", ".py", ".sh", ".ps1", ".yml", ".yaml", ".json", ".toml", ".go",
                ".tf", ".hcl", ".mjs", ".js", ".txt", ".env", ".service", ".alloy",
                ".likec4", ".html")
BACKTICKED = re.compile(r"`([^`\n]+)`")
LINK_TARGET = re.compile(r"\]\(([^)#\s]+)")
# Prose outside backticks and fences is not scanned. Inside a fence, and in the
# Makefile (no backticks), any whitespace-free token ending in a document or
# script suffix is a path. The suffix set is narrower than DOC_SUFFIXES on
# purpose: recipes name runtime-only files (`backend.auto.hcl`, `.env`) that
# are never committed. A name with spaces still ends in a token that fails to
# resolve, which is the point.
BARE_PATH = re.compile(r"(?<![\w./-])((?:[\w.-]+/)*[\w.-]+\.(?:md|py|sh|ps1|ya?ml|json|toml))(?![\w-])")
NOT_A_PATH = set("<>{}*$\\")  # placeholders, brace sets, globs, make variables, Windows paths


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout


def watch_dirs(root: Path) -> tuple[str, ...]:
    policy = root / ".maintainability" / "layout.json"
    if policy.exists():
        return tuple(json.loads(policy.read_text()).keys()) or DEFAULT_WATCH
    return DEFAULT_WATCH


def repo_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() not in BINARY_SUFFIXES:
                out.append(p)
    return out


def watched(root: Path, dirs: tuple[str, ...]) -> list[str]:
    files: list[str] = []
    for d in dirs:
        base = root / d
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.is_file() and not any(s in p.parts for s in SKIP_DIRS):
                files.append(p.relative_to(root).as_posix())
    return files


def removed_since(root: Path, base: str, dirs: tuple[str, ...]) -> list[str]:
    """Paths deleted, or renamed away from, since `base`, under the watched dirs."""
    diff = git("diff", "--name-status", "-M", base, "HEAD", cwd=root)
    gone: list[str] = []
    for line in diff.splitlines():
        parts = line.split("\t")
        if parts[0][0] in "DR":
            gone.append(parts[1])          # for R this is the old name
    prefixes = tuple(f"{d}/" for d in dirs)
    return [p for p in gone if p.startswith(prefixes)]


def patterns_for(rel: str) -> list[re.Pattern[str]]:
    pats = [re.compile(re.escape(rel))]
    base = os.path.basename(rel)
    if len(base) >= MIN_BASENAME_LEN and base not in GENERIC_BASENAMES:
        # bare basename, bounded so `foo_bar.sh` does not match `xfoo_bar.sh`
        pats.append(re.compile(r"(?<![\w./-])" + re.escape(base) + r"(?![\w-])"))
    return pats


def find_references(root: Path, targets: list[str]) -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    compiled = {t: patterns_for(t) for t in targets}
    for f in repo_files(root):
        rel = f.relative_to(root).as_posix()
        if rel.startswith(RECORD_PATHS):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for target, pats in compiled.items():
                if rel == target:
                    continue
                if any(p.search(line) for p in pats):
                    hits.append((rel, lineno, target))
    return hits


def path_like(tok: str) -> bool:
    return "/" in tok or tok.endswith(DOC_SUFFIXES)


def paths_in_span(span: str) -> list[str]:
    """The paths a backticked span names: a lone path, the path words of a command
    (`bash scripts/x.sh robustel`), or a file name with spaces (`Some Plan.md`),
    which is how a dead link to a document outside the repo once hid."""
    tok = span.strip().strip("(").rstrip(".,:;)").split("#", 1)[0]
    if not tok or NOT_A_PATH & set(tok) or tok.startswith(("http://", "https://", "-")):
        return []
    slash_words = [w for w in tok.split() if "/" in w and not w.startswith("-")]
    if slash_words:
        return slash_words
    return [tok] if tok.endswith(DOC_SUFFIXES) else []


def doc_candidates(text: str, backticks: bool) -> list[tuple[int, str]]:
    """(line, path) for every token in an instruction file that reads as a path."""
    out: list[tuple[int, str]] = []
    fenced = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if backticks and line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if backticks and not fenced:
            spans = BACKTICKED.findall(line) + LINK_TARGET.findall(line)
            found = [p for span in spans for p in paths_in_span(span)]
        else:
            found = [p for p in BARE_PATH.findall(line) if not NOT_A_PATH & set(p)]
        out.extend((lineno, p) for p in found)
    return out


def resolves(root: Path, referrer: Path, tok: str, basenames: set[str]) -> bool:
    """Relative to the referrer, then the root; a bare filename anywhere in the tree
    (a Makefile recipe runs after its own `cd`, so `./x.sh` is a bare name)."""
    rel = tok.rstrip("/").removeprefix("./")
    if (referrer.parent / rel).exists() or (root / rel).exists():
        return True
    return "/" not in rel and rel in basenames


def check_docs(root: Path) -> list[tuple[str, int, str]]:
    basenames = {os.path.basename(p) for p in git("ls-files", cwd=root).splitlines()}
    missing: list[tuple[str, int, str]] = []
    for rel in DOC_FILES:
        f = root / rel
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for lineno, tok in doc_candidates(text, backticks=rel != "Makefile"):
            if not resolves(root, f, tok, basenames):
                missing.append((rel, lineno, tok))
    return missing


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=".")
    ap.add_argument("--base", help="git ref to diff against (CI)")
    ap.add_argument("--removed", action="append", default=[],
                    help="a watched path being moved or deleted")
    ap.add_argument("--index", action="store_true",
                    help="print every reference to every watched file")
    ap.add_argument("--docs", action="store_true",
                    help="every path named in the instruction files must exist")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    dirs = watch_dirs(root)

    if args.index:
        for referrer, line, target in find_references(root, watched(root, dirs)):
            print(f"{referrer}:{line}: {target}")
        return 0

    if args.docs:
        missing = check_docs(root)
        for referrer, line, tok in missing:
            print(f"{referrer}:{line}: names a path that does not exist: {tok}")
        if missing:
            print(f"\n{len(missing)} dead reference(s) in the instruction files. "
                  "Fix the path or the prose in this PR.")
            return 1
        print("check_path_references --docs: every path named in", ", ".join(DOC_FILES), "exists")
        return 0

    targets = list(args.removed)
    if args.base:
        targets += removed_since(root, args.base, dirs)
    if not targets:
        print("check_path_references: nothing moved or deleted under", ", ".join(dirs))
        return 0

    hits = find_references(root, targets)
    if not hits:
        print(f"check_path_references: {len(targets)} removed path(s), no dangling references")
        return 0
    for referrer, line, target in hits:
        print(f"{referrer}:{line}: still names {target}")
    print(f"\n{len(hits)} dangling reference(s). Update them in this PR, "
          "or leave a shim at the old path (see the repo-maintainability skill, §3).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
