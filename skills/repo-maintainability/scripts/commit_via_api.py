#!/usr/bin/env python3
"""Commit files to a branch through GitHub's GraphQL API, as a GitHub App.

  GH_TOKEN=<app installation token> commit_via_api.py --repo owner/name \\
      --branch main --message "chore: refresh [skip ci]" STATUS.md CONTEXT.md

A commit made through `createCommitOnBranch` is signed by GitHub, so it
passes a `required_signatures` rule, and when the token belongs to an App
listed as a ruleset bypass actor it lands on a protected branch without a
pull request. A plain `git push` from a runner does neither.

Only paths that differ from HEAD are sent; with nothing changed, no commit
is made. The branch must still be at HEAD (`--expected-head`), otherwise
GitHub refuses and the job fails rather than overwriting someone's push.

Run it from a job that installed nothing and checked out the trusted
commit fresh, with `--allow` naming every path or directory prefix the
decision record permits; anything else is refused before a token is used.
A tool that ran earlier in another job cannot then widen what is committed.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

MUTATION = """
mutation($input: CreateCommitOnBranchInput!) {
  createCommitOnBranch(input: $input) { commit { oid url } }
}
"""


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def changed(paths: list[str]) -> tuple[list[str], list[str]]:
    """(modified or untracked, deleted) paths relative to HEAD, among `paths`."""
    status = git("status", "--porcelain", "--untracked-files=all", "--", *paths)
    modified, deleted = set(), set()
    for line in status.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        (deleted if "D" in line[:2] else modified).add(path)
    return sorted(modified), sorted(deleted)


def payload(repo: str, branch: str, message: str, head: str, files: dict[str, bytes],
            deletions: list[str] | None = None) -> dict:
    additions = [{"path": path, "contents": base64.b64encode(data).decode("ascii")}
                 for path, data in sorted(files.items())]
    return {"query": MUTATION, "variables": {"input": {
        "branch": {"repositoryNameWithOwner": repo, "branchName": branch},
        "message": {"headline": message},
        "expectedHeadOid": head,
        "fileChanges": {"additions": additions,
                        "deletions": [{"path": p} for p in sorted(deletions or [])]},
    }}}


def post(body: dict, token: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "repo-maintainability/commit_via_api"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def allowed(path: str, prefixes: list[str]) -> bool:
    return any(path == p or (p.endswith("/") and path.startswith(p)) for p in prefixes)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--branch", required=True)
    ap.add_argument("--message", required=True)
    ap.add_argument("--expected-head", default=None)
    ap.add_argument("--allow", action="append", default=[],
                    help="a path, or a directory prefix ending in /, the commit may touch; repeatable")
    ap.add_argument("paths", nargs="+")
    args = ap.parse_args()

    if args.allow:
        refused = [p for p in args.paths if not allowed(p, args.allow)]
        if refused:
            print(f"commit_via_api: refusing paths outside the allow list: {' '.join(refused)}",
                  file=sys.stderr)
            return 2

    modified, deleted = changed(args.paths)
    if not modified and not deleted:
        print("commit_via_api: nothing changed")
        return 0
    token = os.environ.get("GH_TOKEN", "")
    if not token:
        print("commit_via_api: GH_TOKEN is not set", file=sys.stderr)
        return 2
    head = args.expected_head or git("rev-parse", "HEAD").strip()
    files = {p: Path(p).read_bytes() for p in modified}
    result = post(payload(args.repo, args.branch, args.message, head, files, deleted), token)
    if result.get("errors"):
        print("commit_via_api:", json.dumps(result["errors"]), file=sys.stderr)
        return 1
    commit = result["data"]["createCommitOnBranch"]["commit"]
    print(f"commit_via_api: {commit['oid'][:7]} {commit['url']} "
          f"({len(modified)} changed, {len(deleted)} deleted)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
