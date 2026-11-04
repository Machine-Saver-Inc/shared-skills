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


def changed(paths: list[str]) -> list[str]:
    """Paths whose working-tree content differs from HEAD (or are untracked)."""
    status = git("status", "--porcelain", "--untracked-files=all", "--", *paths)
    return sorted({line[3:].strip() for line in status.splitlines() if line.strip()})


def payload(repo: str, branch: str, message: str, head: str, files: dict[str, bytes]) -> dict:
    additions = [{"path": path, "contents": base64.b64encode(data).decode("ascii")}
                 for path, data in sorted(files.items())]
    return {"query": MUTATION, "variables": {"input": {
        "branch": {"repositoryNameWithOwner": repo, "branchName": branch},
        "message": {"headline": message},
        "expectedHeadOid": head,
        "fileChanges": {"additions": additions},
    }}}


def post(body: dict, token: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "repo-maintainability/commit_via_api"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--branch", required=True)
    ap.add_argument("--message", required=True)
    ap.add_argument("--expected-head", default=None)
    ap.add_argument("paths", nargs="+")
    args = ap.parse_args()

    paths = changed(args.paths)
    if not paths:
        print("commit_via_api: nothing changed")
        return 0
    token = os.environ.get("GH_TOKEN", "")
    if not token:
        print("commit_via_api: GH_TOKEN is not set", file=sys.stderr)
        return 2
    head = args.expected_head or git("rev-parse", "HEAD").strip()
    files = {p: Path(p).read_bytes() for p in paths}
    result = post(payload(args.repo, args.branch, args.message, head, files), token)
    if result.get("errors"):
        print("commit_via_api:", json.dumps(result["errors"]), file=sys.stderr)
        return 1
    commit = result["data"]["createCommitOnBranch"]["commit"]
    print(f"commit_via_api: {commit['oid'][:7]} {commit['url']} ({len(paths)} file(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
