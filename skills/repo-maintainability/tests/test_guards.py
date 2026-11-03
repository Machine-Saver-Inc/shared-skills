"""Each guard must pass on a clean change and fail on its own violation.

A guard nobody has seen fail is decoration (shared-skills README, rule 2).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def run(*cmd: str, cwd: Path, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *cmd], cwd=cwd, input=stdin,
                          capture_output=True, text=True)


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
