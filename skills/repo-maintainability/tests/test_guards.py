"""Each guard must pass on a clean change and fail on its own violation.

A guard nobody has seen fail is decoration (shared-skills README, rule 2).
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"


def run(*cmd: str, cwd: Path, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    # Guards run under UTF-8 as on the Linux runners, whatever the local console.
    env = {**os.environ, "PYTHONUTF8": "1"}
    return subprocess.run([sys.executable, *cmd], cwd=cwd, input=stdin, env=env,
                          capture_output=True, text=True, encoding="utf-8")


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path
    (r / "scripts/airvibe").mkdir(parents=True)
    (r / "docs/runbooks").mkdir(parents=True)
    (r / ".maintainability").mkdir()
    (r / "scripts/airvibe_gateway_seed.py").write_text("print('seed')\n")
    (r / "scripts/edge-compose.sh").write_text("echo render\n")
    (r / "Makefile").write_text("render:\n\tpython scripts/airvibe_gateway_seed.py\n")
    (r / "docs/runbooks/bench.md").write_text("Run airvibe_gateway_seed.py on the bench\n")
    (r / ".maintainability/layout.json").write_text(json.dumps(
        {"scripts": {"families": ["airvibe", "robustel"], "allow_top_level": ["edge-compose.sh"]}}))
    git("init", "-q", "-b", "main", cwd=r)
    git("config", "user.email", "t@t", cwd=r)
    git("config", "user.name", "t", cwd=r)
    git("add", "-A", cwd=r)
    git("commit", "-qm", "base", cwd=r)
    assert run(str(SCRIPTS / "check_layout.py"), "--baseline", cwd=r).returncode == 0
    git("add", "-A", cwd=r)
    git("commit", "-qm", "baseline", cwd=r)
    git("checkout", "-qb", "pr", cwd=r)
    return r


def move_seed(r: Path) -> None:
    (r / "scripts/airvibe").mkdir(exist_ok=True)
    git("mv", "scripts/airvibe_gateway_seed.py", "scripts/airvibe/gateway_seed.py", cwd=r)


def test_reference_check_passes_when_references_are_updated(repo: Path) -> None:
    move_seed(repo)
    mk = repo / "Makefile"
    mk.write_text(mk.read_text().replace("scripts/airvibe_gateway_seed.py", "scripts/airvibe/gateway_seed.py"))
    rb = repo / "docs/runbooks/bench.md"
    rb.write_text(rb.read_text().replace("airvibe_gateway_seed.py", "airvibe/gateway_seed.py"))
    git("commit", "-qam", "move", cwd=repo)
    out = run(str(SCRIPTS / "check_path_references.py"), "--base", "main", cwd=repo)
    assert out.returncode == 0, out.stdout


def test_reference_check_fails_on_stale_makefile_and_runbook(repo: Path) -> None:
    move_seed(repo)
    git("commit", "-qam", "move", cwd=repo)
    out = run(str(SCRIPTS / "check_path_references.py"), "--base", "main", cwd=repo)
    assert out.returncode == 1
    assert "Makefile:2" in out.stdout
    assert "docs/runbooks/bench.md:1" in out.stdout      # the line a code graph never sees


def test_reference_check_ignores_baseline_records(repo: Path) -> None:
    move_seed(repo)
    git("commit", "-qam", "move", cwd=repo)
    out = run(str(SCRIPTS / "check_path_references.py"), "--base", "main", cwd=repo)
    assert ".maintainability" not in out.stdout


def test_reference_check_points_at_the_section_that_explains_shims(repo: Path) -> None:
    move_seed(repo)
    git("commit", "-qam", "move", cwd=repo)
    out = run(str(SCRIPTS / "check_path_references.py"), "--base", "main", cwd=repo)
    section = re.search(r"§(\d+)", out.stdout)
    assert section, out.stdout
    body = (SKILL / "SKILL.md").read_text(encoding="utf-8").split(f"\n## {section.group(1)}. ")[1]
    assert "shim" in body.split("\n## ")[0]


def test_layout_passes_on_a_family_file(repo: Path) -> None:
    (repo / "scripts/airvibe/new.py").write_text("x\n")
    git("add", "-A", cwd=repo)
    git("commit", "-qm", "add", cwd=repo)
    assert run(str(SCRIPTS / "check_layout.py"), "--base", "main", cwd=repo).returncode == 0


def test_layout_fails_on_new_top_level_and_unlisted_family(repo: Path) -> None:
    (repo / "scripts/new_tool.py").write_text("x\n")
    (repo / "scripts/mender").mkdir()
    (repo / "scripts/mender/x.sh").write_text("y\n")
    git("add", "-A", cwd=repo)
    git("commit", "-qm", "add", cwd=repo)
    out = run(str(SCRIPTS / "check_layout.py"), "--base", "main", cwd=repo)
    assert out.returncode == 1
    assert "scripts/new_tool.py" in out.stdout
    assert "'mender' is not a listed family" in out.stdout


def test_ratchet_only_fails_on_new_findings(tmp_path: Path) -> None:
    b = tmp_path / "t.baseline"
    seed = "a.py:10: unused x\nb.sh:3:1: SC2086\n"
    assert run(str(SCRIPTS / "ratchet.py"), "update", "--baseline", str(b), "--allow-growth",
               cwd=tmp_path, stdin=seed).returncode == 0
    shifted = "a.py:99: unused x\nb.sh:7:1: SC2086\n"
    assert run(str(SCRIPTS / "ratchet.py"), "check", "--baseline", str(b),
               cwd=tmp_path, stdin=shifted).returncode == 0
    out = run(str(SCRIPTS / "ratchet.py"), "check", "--baseline", str(b),
              cwd=tmp_path, stdin=seed + "c.py:1: unused y\n")
    assert out.returncode == 1 and "NEW: c.py: unused y" in out.stdout


def test_ratchet_refuses_to_grow_but_shrinks(tmp_path: Path) -> None:
    b = tmp_path / "t.baseline"
    run(str(SCRIPTS / "ratchet.py"), "update", "--baseline", str(b), "--allow-growth",
        cwd=tmp_path, stdin="a:1: x\nb:1: y\n")
    assert run(str(SCRIPTS / "ratchet.py"), "update", "--baseline", str(b),
               cwd=tmp_path, stdin="a:1: x\nb:1: y\nc:1: z\n").returncode == 1
    assert run(str(SCRIPTS / "ratchet.py"), "update", "--baseline", str(b),
               cwd=tmp_path, stdin="a:1: x\n").returncode == 0
    assert b.read_text() == "a: x\n"


def test_ratchet_refuses_to_grow_an_empty_baseline(tmp_path: Path) -> None:
    b = tmp_path / "t.baseline"
    run(str(SCRIPTS / "ratchet.py"), "update", "--baseline", str(b), "--allow-growth",
        cwd=tmp_path, stdin="")
    assert run(str(SCRIPTS / "ratchet.py"), "update", "--baseline", str(b),
               cwd=tmp_path, stdin="a:1: x\n").returncode == 1
    assert b.read_text() == ""


def test_ratchet_refuses_a_swapped_finding(tmp_path: Path) -> None:
    b = tmp_path / "t.baseline"
    run(str(SCRIPTS / "ratchet.py"), "update", "--baseline", str(b), "--allow-growth",
        cwd=tmp_path, stdin="a:1: x\nb:1: y\n")
    out = run(str(SCRIPTS / "ratchet.py"), "update", "--baseline", str(b),
              cwd=tmp_path, stdin="a:1: x\nc:1: z\n")
    assert out.returncode == 1 and "c: z" in out.stdout
    assert b.read_text() == "a: x\nb: y\n"


def test_ledger_check_fails_on_a_hand_written_tracker(repo: Path) -> None:
    (repo / "project-tracker.html").write_text("<!doctype html><p>Next action: ...</p>\n")
    (repo / "docs/STATUS.md").write_text("# Status\n- doing things\n")
    git("add", "-A", cwd=repo)
    git("commit", "-qm", "ledger", cwd=repo)
    out = run(str(SCRIPTS / "check_ledgers.py"), "--base", "main", cwd=repo)
    assert out.returncode == 1
    assert "project-tracker.html" in out.stdout and "docs/STATUS.md" in out.stdout


def test_ledger_check_allows_generated_status_and_archive(repo: Path) -> None:
    (repo / "STATUS.md").write_text("<!-- generated-by: render_status.py -->\n# Status\n")
    (repo / "docs/archive").mkdir(parents=True)
    (repo / "docs/archive/project-tracker.html").write_text("<!doctype html>old\n")
    git("add", "-A", cwd=repo)
    git("commit", "-qm", "generated", cwd=repo)
    out = run(str(SCRIPTS / "check_ledgers.py"), "--base", "main", cwd=repo)
    assert out.returncode == 0, out.stdout


def test_pr_links_pass_on_issue_or_adr_and_fail_without(tmp_path: Path) -> None:
    body = tmp_path / "body.md"
    for text in ("Closes #42", "see https://github.com/o/r/issues/7", "Implements ADR 0019",
                 "per ADR-0020"):
        body.write_text(text)
        assert run(str(SCRIPTS / "check_pr_links.py"), "--body-file", str(body),
                   cwd=tmp_path).returncode == 0, text
    for text in ("", "fix typo", "step #", "see PR-42 and v1.0.3"):
        body.write_text(text)
        assert run(str(SCRIPTS / "check_pr_links.py"), "--body-file", str(body),
                   cwd=tmp_path).returncode == 1, text


def test_status_render_is_marked_generated_and_grouped(tmp_path: Path) -> None:
    board = {"items": [
        {"status": "Todo", "horizon": "Next", "area": "Platform", "labels": ["blocker"],
         "content": {"number": 7, "title": "Seed gateways", "url": "https://x/7",
                     "repository": "Machine-Saver-Inc/platform"}},
        {"status": "In Progress", "content": {"number": 9, "title": "Layout gate",
                                              "url": "https://x/9"}},
    ]}
    out = run(str(SCRIPTS / "render_status.py"), cwd=tmp_path, stdin=json.dumps(board))
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines()[0].startswith("<!-- generated-by:")
    assert out.stdout.index("## In Progress (1)") < out.stdout.index("## Todo (1)")
    assert "[#7 Seed gateways](https://x/7) · platform · Platform · Next · `blocker`" in out.stdout


def test_ledger_check_ignores_code_named_after_ledgers(repo: Path) -> None:
    (repo / "scripts/airvibe/ledger_sync.py").write_text("print('not a ledger')\n")
    (repo / "scripts/airvibe/check_tracker.sh").write_text("echo ok\n")
    git("add", "-A", cwd=repo)
    git("commit", "-qm", "code", cwd=repo)
    out = run(str(SCRIPTS / "check_ledgers.py"), "--base", "main", cwd=repo)
    assert out.returncode == 0, out.stdout


def test_pr_links_needs_a_keyword_before_the_issue_number(tmp_path: Path) -> None:
    body = tmp_path / "body.md"
    for text in ("mentioned in PR #158 earlier", "step #3 of the runbook", "item #42"):
        body.write_text(text)
        assert run(str(SCRIPTS / "check_pr_links.py"), "--body-file", str(body),
                   cwd=tmp_path).returncode == 1, text
    for text in ("Refs #158", "closes issue #7", "Part of #9", "Implements #11"):
        body.write_text(text)
        assert run(str(SCRIPTS / "check_pr_links.py"), "--body-file", str(body),
                   cwd=tmp_path).returncode == 0, text


def test_status_render_accepts_a_bare_list(tmp_path: Path) -> None:
    out = run(str(SCRIPTS / "render_status.py"), cwd=tmp_path,
              stdin=json.dumps([{"status": "Todo", "content": {"number": 1, "title": "x"}}]))
    assert out.returncode == 0, out.stderr
    assert "## Todo (1)" in out.stdout


def test_reference_check_ignores_decisions_and_archives(repo: Path) -> None:
    (repo / "docs/adr").mkdir(parents=True)
    (repo / "docs/adr/0001-seed.md").write_text("We keep scripts/airvibe_gateway_seed.py.\n")
    (repo / "docs/archive").mkdir(parents=True)
    (repo / "docs/archive/old-tracker.html").write_text("ran airvibe_gateway_seed.py\n")
    git("add", "-A", cwd=repo)
    git("commit", "-qm", "records", cwd=repo)
    move_seed(repo)
    git("commit", "-qam", "move", cwd=repo)
    out = run(str(SCRIPTS / "check_path_references.py"), "--base", "main", cwd=repo)
    assert out.returncode == 1
    assert "docs/adr/" not in out.stdout and "docs/archive/" not in out.stdout
    assert "Makefile:2" in out.stdout


def test_ratchet_treats_windows_and_posix_paths_as_the_same_finding(tmp_path: Path) -> None:
    b = tmp_path / "t.baseline"
    run(str(SCRIPTS / "ratchet.py"), "update", "--baseline", str(b), "--allow-growth",
        cwd=tmp_path, stdin="scripts/a.ps1:10: PSAvoidUsingCmdletAliases alias\n")
    out = run(str(SCRIPTS / "ratchet.py"), "check", "--baseline", str(b),
              cwd=tmp_path, stdin=r".\scripts\a.ps1:12: PSAvoidUsingCmdletAliases alias" + "\n")
    assert out.returncode == 0, out.stdout


def test_ratchet_writes_posix_line_endings_everywhere(tmp_path: Path) -> None:
    b = tmp_path / "t.baseline"
    run(str(SCRIPTS / "ratchet.py"), "update", "--baseline", str(b), "--allow-growth",
        cwd=tmp_path, stdin="a:1: x\nb:1: y\n")
    assert b"\r" not in b.read_bytes()


def test_jscpd_findings_are_order_and_os_independent(tmp_path: Path) -> None:
    report = tmp_path / "jscpd-report.json"
    pair = {"format": "python", "lines": 12, "tokens": 204,
            "firstFile": {"name": r"scripts\b.py", "start": 1, "end": 12},
            "secondFile": {"name": "scripts/a.py", "start": 5, "end": 16}}
    swapped = {**pair, "firstFile": pair["secondFile"], "secondFile": pair["firstFile"]}
    report.write_text(json.dumps({"statistics": {}, "duplicates": [pair, swapped]}))
    out = run(str(SCRIPTS / "jscpd_findings.py"), str(report), cwd=tmp_path)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == ["python: scripts/a.py + scripts/b.py"]


def test_api_commit_payload_is_a_signed_branch_commit_request(tmp_path: Path) -> None:
    sys.path.insert(0, str(SCRIPTS))
    import commit_via_api
    files = {"STATUS.md": b"# Status\n", "docs/CONTEXT.md": b"ctx"}
    body = commit_via_api.payload("org/repo", "main", "chore: refresh [skip ci]", "a" * 40, files)
    inp = body["variables"]["input"]
    assert inp["branch"] == {"repositoryNameWithOwner": "org/repo", "branchName": "main"}
    assert inp["expectedHeadOid"] == "a" * 40
    assert [a["path"] for a in inp["fileChanges"]["additions"]] == ["STATUS.md", "docs/CONTEXT.md"]
    assert base64.b64decode(inp["fileChanges"]["additions"][0]["contents"]) == b"# Status\n"
    assert "createCommitOnBranch" in body["query"]


def test_api_commit_sends_only_changed_paths(repo: Path) -> None:
    (repo / "STATUS.md").write_text("new\n")
    out = run(str(SCRIPTS / "commit_via_api.py"), "--repo", "o/r", "--branch", "main",
              "--message", "m", "Makefile", cwd=repo)
    assert out.returncode == 0 and "nothing changed" in out.stdout


def test_layout_baseline_refuses_to_grow(repo: Path) -> None:
    (repo / "scripts/slipped_in.py").write_text("x\n")
    git("add", "-A", cwd=repo)
    git("commit", "-qm", "bypass merge", cwd=repo)
    out = run(str(SCRIPTS / "check_layout.py"), "--baseline", cwd=repo)
    assert out.returncode == 1 and "scripts/slipped_in.py" in out.stdout
    tolerated = (repo / ".maintainability/layout-tolerated.txt").read_text()
    assert "slipped_in" not in tolerated
    assert run(str(SCRIPTS / "check_layout.py"), "--baseline", "--allow-growth",
               cwd=repo).returncode == 0


def test_api_commit_payload_carries_deletions(tmp_path: Path) -> None:
    sys.path.insert(0, str(SCRIPTS))
    import commit_via_api
    body = commit_via_api.payload("org/repo", "main", "m", "a" * 40,
                                  {"STATUS.md": b"x"}, deletions=["old.md"])
    assert body["variables"]["input"]["fileChanges"]["deletions"] == [{"path": "old.md"}]
