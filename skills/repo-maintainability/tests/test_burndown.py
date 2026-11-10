"""Burn-down picker, patch check, retire and the agent's boundary (ADR 0022).

Each guard is seen to fail against its own violation before it is trusted.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import ClassVar

HERE = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(HERE))

import burndown_agent
import burndown_pick
import commit_via_api

DAY = 86400


def git(*args: str, cwd: Path, env: dict | None = None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=env).stdout


def run(script: str, *args: str, cwd: Path, stdin: str | None = None):
    env = {**os.environ, "PYTHONUTF8": "1"}
    return subprocess.run([sys.executable, str(HERE / script), *args], check=False, cwd=cwd,
                          input=stdin, capture_output=True, text=True, encoding="utf-8", env=env)


class Repo(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for d in ("scripts/airvibe", ".maintainability", "docs/runbooks", ".github/workflows"):
            (self.root / d).mkdir(parents=True)
        git("init", "-q", "-b", "main", cwd=self.root)
        git("config", "user.email", "t@t", cwd=self.root)
        git("config", "user.name", "t", cwd=self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, rel: str, text: str) -> None:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self, days_ago: int = 0) -> None:
        git("add", "-A", cwd=self.root)
        when = f"{int(time.time()) - days_ago * DAY} +0000"
        env = {**os.environ, "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
        git("commit", "-qm", "c", cwd=self.root, env=env)

    def pick(self, *args: str) -> dict:
        out = run("burndown_pick.py", "pick", *args, cwd=self.root)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)


class PickTests(Repo):
    def test_retire_needs_age_and_no_outside_reference(self) -> None:
        self.write("scripts/airvibe_x_candidate.py", "print(1)\n")
        self.write("scripts/test_airvibe_x_candidate.py", "import airvibe_x_candidate\n")
        # The generated files list every script; a mention there keeps nothing alive.
        self.write(".maintainability/layout-tolerated.txt", "scripts/airvibe_x_candidate.py\n")
        self.write(".maintainability/ruff.baseline", "scripts/airvibe_x_candidate.py: E1 x\n")
        self.write("CONTEXT.md", "airvibe_x_candidate: a candidate\n")
        self.commit(days_ago=70)
        target = self.pick("--kind", "retire")
        self.assertEqual(target["paths"], ["scripts/airvibe_x_candidate.py",
                                           "scripts/test_airvibe_x_candidate.py"])

    def test_verify_on_the_base_tree_wants_the_target_present(self) -> None:
        self.write("scripts/airvibe/a.py", "import os\n")
        self.commit()
        finding = {"kind": "delete", "key": "d", "paths": ["scripts/airvibe/a.py"],
                   "finding": "scripts/airvibe/a.py: unused import 'os' (90% confidence)"}
        retire = {"kind": "retire", "key": "r", "paths": ["scripts/airvibe/a.py"]}
        (self.root / "f.txt").write_text("scripts/airvibe/a.py:1: unused import 'os' (90% confidence)\n")
        (self.root / "none.txt").write_text("")
        for target, findings, rc in ((finding, "f.txt", 0), (finding, "none.txt", 1),
                                     (retire, "none.txt", 0),
                                     ({**retire, "paths": ["scripts/gone.py"]}, "none.txt", 1)):
            (self.root / "t.json").write_text(json.dumps(target))
            out = run("burndown_pick.py", "verify", "--target", "t.json", "--findings", findings,
                      "--expect-present", cwd=self.root)
            self.assertEqual(out.returncode, rc, (target["key"], findings, out.stdout))

    def test_retire_skips_young_candidates(self) -> None:
        self.write("scripts/airvibe_young_candidate.py", "x\n")
        self.commit(days_ago=10)
        self.assertEqual(self.pick("--kind", "retire"), {})

    def test_retire_sees_dotted_imports_and_workflow_test_modules(self) -> None:
        self.write("scripts/airvibe_used_candidate.py", "x = 1\n")
        self.write("scripts/verify_thing.py", "from scripts.airvibe_used_candidate import x\n")
        self.commit(days_ago=90)
        self.assertEqual(self.pick("--kind", "retire"), {})
        git("rm", "-q", "scripts/verify_thing.py", cwd=self.root)
        self.write(".github/workflows/w.yml", "run: python3 -m unittest scripts.test_airvibe_used_candidate\n")
        self.write("scripts/test_airvibe_used_candidate.py", "pass\n")
        self.commit(days_ago=90)
        self.assertEqual(self.pick("--kind", "retire"), {})

    def test_delete_reads_vulture_and_honours_skip(self) -> None:
        self.write("scripts/airvibe/a.py", "import os\n")
        self.write(".maintainability/vulture.baseline",
                   "scripts/airvibe/a.py: unused import 'os' (90% confidence)\n")
        self.commit()
        target = self.pick("--kind", "delete")
        self.assertEqual(target["paths"], ["scripts/airvibe/a.py"])
        skip = self.root / "skip.txt"
        skip.write_text(target["key"] + "\n")
        self.assertEqual(self.pick("--kind", "delete", "--skip-file", str(skip)), {})

    def test_delete_never_targets_a_forbidden_path(self) -> None:
        self.write("scripts/ci/gate.py", "import os\n")
        self.write(".maintainability/vulture.baseline",
                   "scripts/ci/gate.py: unused import 'os' (90% confidence)\n")
        self.commit()
        self.assertEqual(self.pick("--kind", "delete"), {})

    def test_delete_leaves_test_module_imports_alone(self) -> None:
        self.write("scripts/test_x.py", "from scripts.test_y import YTests\n")
        self.write(".maintainability/vulture.baseline",
                   "scripts/test_x.py: unused import 'YTests' (90% confidence)\n")
        self.commit()
        self.assertEqual(self.pick("--kind", "delete"), {})

    def test_delete_passes_over_unused_variables(self) -> None:
        self.write("scripts/airvibe/a.py", "def f(cb, unused):\n    return cb\n")
        self.write(".maintainability/vulture.baseline",
                   "scripts/airvibe/a.py: unused variable 'unused' (100% confidence)\n")
        self.commit()
        self.assertEqual(self.pick("--kind", "delete"), {})

    def test_retire_sees_a_stem_named_in_a_packager_list_or_comma_import(self) -> None:
        self.write("scripts/airvibe_listed_candidate.py", "x = 1\n")
        self.write("scripts/airvibe/package.py", "ENTRIES = ('airvibe_listed_candidate', 'other')\n")
        self.commit(days_ago=90)
        self.assertEqual(self.pick("--kind", "retire"), {})
        git("rm", "-q", "scripts/airvibe/package.py", cwd=self.root)
        self.write("scripts/tools/use.py", "import json, airvibe_listed_candidate\n")
        self.commit(days_ago=90)
        self.assertEqual(self.pick("--kind", "retire"), {})

    def test_retire_sees_bare_stem_imports(self) -> None:
        self.write("scripts/airvibe_bare_candidate.py", "x = 1\n")
        self.write("scripts/tools/use.py", "from airvibe_bare_candidate import x\n")
        self.commit(days_ago=90)
        self.assertEqual(self.pick("--kind", "retire"), {})

    def test_verify_matches_findings_without_line_numbers(self) -> None:
        target = {"key": "k", "finding": "scripts/a.py: unused variable 'x' (100% confidence)"}
        self.assertFalse(burndown_pick.verify(
            target, ["scripts/a.py:12: unused variable 'x' (100% confidence)"]))
        self.assertTrue(burndown_pick.verify(target, ["scripts/b.py:3: unused import 'os'"]))


class KeyTests(unittest.TestCase):
    def test_keys_are_unique_and_bounded(self) -> None:
        entries = {
            "dedupe": ["python: scripts/a/x.py + scripts/a/y.py", "python: scripts/a/x.py + scripts/a/z.py"],
            "delete": ["scripts/a.py: unused function 'f' (60% confidence)",
                       "scripts/a.py: unused function 'g' (60% confidence)",
                       "scripts/" + "deep/" * 30 + "a.py: unused import 'os' (90% confidence)"],
        }
        for kind, lines in entries.items():
            keys = [burndown_pick.key_for(kind, l) for l in lines]
            self.assertEqual(len(keys), len(set(keys)), kind)
            self.assertTrue(all(len(k) <= 80 for k in keys))


class PatchCheckTests(unittest.TestCase):
    delete: ClassVar[dict] = {"kind": "delete", "key": "k", "paths": ["scripts/airvibe/a.py"]}
    dedupe: ClassVar[dict] = {"kind": "dedupe", "key": "k", "paths": ["scripts/airvibe/a.py", "scripts/airvibe/b.py"]}
    retire: ClassVar[dict] = {"kind": "retire", "key": "k", "paths": ["scripts/x_candidate.py"]}
    both: ClassVar[dict] = {"scripts/airvibe/a.py": "M", "scripts/airvibe/b.py": "M"}

    def problems(self, target: dict, touched: dict[str, str], patch: str = "") -> list[str]:
        return burndown_pick.patch_problems(target, touched, patch)

    def test_only_the_target_paths(self) -> None:
        self.assertEqual(self.problems(self.delete, {"scripts/airvibe/a.py": "M"}), [])
        self.assertTrue(self.problems(self.delete, {"scripts/airvibe/a.py": "M", "json.py": "A"}))
        self.assertTrue(self.problems(self.delete, {"scripts/airvibe/helper.py": "A"}))

    def test_the_target_files_are_edited_not_deleted(self) -> None:
        self.assertTrue(self.problems(self.delete, {"scripts/airvibe/a.py": "D"}))

    def test_dedupe_may_add_one_helper_beside_its_files(self) -> None:
        self.assertEqual(self.problems(self.dedupe, {**self.both, "scripts/airvibe/_shared.py": "A"}), [])
        self.assertTrue(self.problems(self.dedupe, {**self.both, "scripts/airvibe/h1.py": "A",
                                                    "scripts/airvibe/h2.py": "A"}))
        self.assertTrue(self.problems(self.dedupe, {**self.both, "scripts/robustel/h.py": "A"}))
        self.assertTrue(self.problems(self.dedupe, {**self.both, "scripts/airvibe/.hidden.py": "A"}))
        self.assertTrue(self.problems(self.dedupe, {**self.both, "scripts/airvibe/h.txt": "A"}))

    def test_a_helper_goes_only_where_the_layout_gate_accepts_it(self) -> None:
        layout = {"scripts": {"families": ["airvibe", "pi-bench", "ci"], "allow_top_level": []}}
        top = {"kind": "dedupe", "key": "k",
               "paths": ["scripts/bench-preflight.sh", "scripts/test-bench-preflight.sh"]}
        mine = {p: "M" for p in top["paths"]}
        cases = {"scripts/bench-common.sh": False, "scripts/pi-bench/bench-common.sh": True,
                 "scripts/ci/bench-common.sh": False, "scripts/unlisted/bench-common.sh": False,
                 "scripts/pi-bench/deeper/bench-common.sh": False}
        for helper, expected in cases.items():
            ok = not burndown_pick.patch_problems(top, {**mine, helper: "A"}, "", layout)
            self.assertEqual(ok, expected, helper)
            if ok:
                self.assertTrue(burndown_pick.layout_allows(helper, layout), helper)
        family = {"kind": "dedupe", "key": "k", "paths": ["scripts/airvibe/a.py", "scripts/airvibe/b.py"]}
        self.assertEqual(burndown_pick.patch_problems(
            family, {**self.both, "scripts/airvibe/shared.py": "A"}, "", layout), [])
        stray = {"kind": "dedupe", "key": "k", "paths": ["scripts/unlisted/a.py", "scripts/unlisted/b.py"]}
        self.assertTrue(burndown_pick.patch_problems(
            stray, {"scripts/unlisted/a.py": "M", "scripts/unlisted/b.py": "M",
                    "scripts/unlisted/shared.py": "A"}, "", layout))

    def test_a_helper_is_new_never_an_existing_sibling(self) -> None:
        self.assertTrue(self.problems(self.dedupe, {**self.both, "scripts/airvibe/c.py": "M"}))
        self.assertTrue(self.problems(self.dedupe, {**self.both, "scripts/airvibe/c.py": "D"}))

    def test_retire_deletes_exactly_its_paths(self) -> None:
        self.assertEqual(self.problems(self.retire, {"scripts/x_candidate.py": "D"}), [])
        self.assertTrue(self.problems(self.retire, {}))
        self.assertTrue(self.problems(self.retire, {"scripts/x_candidate.py": "M"}))

    def test_paths_must_be_plain(self) -> None:
        for bad in ("scripts/airvibe/a.py ", " scripts/airvibe/a.py", "scripts/airvibe/../a.py",
                    "./scripts/airvibe/a.py", "/scripts/airvibe/a.py", "scripts/airvibe/a\x01.py"):
            self.assertTrue(self.problems(self.delete, {bad: "M"}), repr(bad))
        # Helpers that pass every other rule (right place, suffix, status) and
        # are refused only for not being plain.
        for helper in ("scripts/airvibe/h\x01.py", "scripts/airvibe/h\n.py", "scripts/airvibe/a b.py",
                       "scripts/airvibe/x'y.py", "scripts/airvibe/x$y.py", "scripts/airvibe/./h.py",
                       "scripts/airvibe//h.py", "scripts/airvibe/-h.py"):
            self.assertTrue(self.problems(self.dedupe, {**self.both, helper: "A"}), repr(helper))
        self.assertEqual(self.problems(self.dedupe, {**self.both, "scripts/airvibe/h_2-x@a.py": "A"}), [])

    def test_forbidden_paths_and_unsafe_patch_content(self) -> None:
        target = {"kind": "delete", "key": "k", "paths": [".github/workflows/ci.yml"]}
        self.assertTrue(self.problems(target, {".github/workflows/ci.yml": "M"}))
        ok = {"scripts/airvibe/a.py": "M"}
        for line in ("new file mode 120000", "new file mode 160000", "old mode 100644",
                     "GIT binary patch", "Binary files a/x and b/x differ"):
            self.assertTrue(self.problems(self.delete, ok, line + "\n"), line)
        self.assertEqual(self.problems(self.delete, ok, "new file mode 100644\n"), [])
        self.assertTrue(self.problems(self.delete, ok, "+c\x00d\n"))

    def test_committed_files_are_judged_for_binary_content(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "text.sh").write_bytes(b"echo hi\n")
            (root / "bin.sh").write_bytes(b"echo\x00hi\n")
            self.assertEqual(burndown_pick.content_problems({"text.sh": "M", "gone.sh": "D"}, root), [])
            self.assertTrue(burndown_pick.content_problems({"bin.sh": "M"}, root))
            self.assertTrue(burndown_pick.content_problems({"missing.sh": "A"}, root))

    def test_name_status_is_parsed_from_nul_separated_output(self) -> None:
        raw = "M\0scripts/a.py\0A\0scripts/b c.py\0D\0scripts/d.py\0"
        self.assertEqual(burndown_pick.parse_name_status(raw),
                         {"scripts/a.py": "M", "scripts/b c.py": "A", "scripts/d.py": "D"})

    def test_cli_refuses_an_empty_change_and_writes_accepted_paths(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "t.json").write_text(json.dumps(self.delete))
            (Path(d) / "p").write_text("")
            out = run("burndown_pick.py", "check-patch", "--target", "t.json", "--patch", "p",
                      cwd=Path(d), stdin="")
            self.assertEqual(out.returncode, 2)
            (Path(d) / "scripts/airvibe").mkdir(parents=True)
            (Path(d) / "scripts/airvibe/a.py").write_text("x = 1\n")
            out = run("burndown_pick.py", "check-patch", "--target", "t.json", "--patch", "p",
                      "--paths-out", "touched", cwd=Path(d), stdin="M\0scripts/airvibe/a.py\0")
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual((Path(d) / "touched").read_text(), "scripts/airvibe/a.py\0")
            (Path(d) / "touched").unlink()
            (Path(d) / "scripts/airvibe/a.py").write_bytes(b"x = 1\x00\n")
            out = run("burndown_pick.py", "check-patch", "--target", "t.json", "--patch", "p",
                      "--paths-out", "touched", cwd=Path(d), stdin="M\0scripts/airvibe/a.py\0")
            self.assertEqual(out.returncode, 2, "binary content must stop the CLI")
            self.assertFalse((Path(d) / "touched").exists())


class RetireTests(Repo):
    def test_retire_removes_only_the_named_files(self) -> None:
        self.write("scripts/airvibe_x_candidate.py", "x\n")
        self.write("scripts/keep.py", "y\n")
        self.commit()
        (self.root / "t.json").write_text(json.dumps(
            {"kind": "retire", "key": "r", "paths": ["scripts/airvibe_x_candidate.py"]}))
        self.assertEqual(run("burndown_mechanical.py", "--target", "t.json", cwd=self.root).returncode, 0)
        self.assertFalse((self.root / "scripts/airvibe_x_candidate.py").exists())
        self.assertTrue((self.root / "scripts/keep.py").exists())


class ApiCommitTests(unittest.TestCase):
    def test_symlinks_and_outside_paths_are_never_read(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            cwd = os.getcwd()
            os.chdir(d)
            try:
                Path("ok.txt").write_text("x")
                self.assertEqual(commit_via_api.regular_file_bytes("ok.txt"), b"x")
                with self.assertRaises(ValueError):
                    commit_via_api.regular_file_bytes("missing.txt")
                try:
                    os.symlink(os.path.abspath("ok.txt"), "link.txt")
                except (OSError, NotImplementedError):
                    return
                with self.assertRaises(ValueError):
                    commit_via_api.regular_file_bytes("link.txt")
            finally:
                os.chdir(cwd)


class AgentBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp()).resolve()

    def test_reads_anywhere_inside_writes_only_outside_forbidden(self) -> None:
        a = burndown_agent.allowed
        self.assertTrue(a(self.root, "Read", {"file_path": ".github/workflows/ci.yml"}))
        self.assertTrue(a(self.root, "Edit", {"file_path": "scripts/airvibe/a.py"}))
        self.assertFalse(a(self.root, "Edit", {"file_path": ".github/workflows/ci.yml"}))
        self.assertFalse(a(self.root, "Write", {"file_path": "scripts/ci/ratchet.py"}))
        self.assertFalse(a(self.root, "Write", {"file_path": ".maintainability/ruff.baseline"}))
        self.assertTrue(a(self.root, "Edit", {"file_path": "edge/base/docker-compose.yml"}))

    def test_a_repo_adds_its_own_forbidden_paths_from_head(self) -> None:
        repo = self.root / "repo"
        (repo / ".maintainability").mkdir(parents=True)
        (repo / ".maintainability/burndown.json").write_text('{"forbidden": ["edge/base/"]}')
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "c",
                        "--allow-empty"], cwd=repo, check=True)
        cwd = Path.cwd()
        os.chdir(repo)
        try:
            burndown_pick.repo_forbidden.cache_clear()
            self.assertFalse(burndown_pick.forbidden("edge/base/x.yml"), "uncommitted config counts")
            subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
            subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "c"],
                           cwd=repo, check=True)
            burndown_pick.repo_forbidden.cache_clear()
            self.assertTrue(burndown_pick.forbidden("edge/base/x.yml"))
            self.assertFalse(burndown_agent.allowed(repo, "Edit", {"file_path": "edge/base/x.yml"}))
        finally:
            os.chdir(cwd)
            burndown_pick.repo_forbidden.cache_clear()

    def test_nothing_leaves_the_checkout_or_reaches_git(self) -> None:
        a = burndown_agent.allowed
        self.assertFalse(a(self.root, "Read", {"file_path": "../secrets"}))
        self.assertFalse(a(self.root, "Read", {"file_path": "/etc/passwd"}))
        self.assertFalse(a(self.root, "Read", {"file_path": ".git/config"}))
        self.assertFalse(a(self.root, "Edit", {"file_path": "scripts/../../x.py"}))

    def test_writes_name_only_paths_the_open_job_would_accept(self) -> None:
        a = burndown_agent.allowed
        for path in ("scripts/x/.GIT/y", "scripts/.Git/y", "GIT~1/x", "scripts/airvibe/a b.py",
                     ".jscpd.json", "scripts/airvibe/.hidden.py"):
            self.assertFalse(a(self.root, "Write", {"file_path": path}), path)
        self.assertFalse(a(self.root, "Read", {"file_path": ".GIT/config"}))
        self.assertTrue(a(self.root, "Write", {"file_path": "scripts/airvibe/h_2.py"}))

    def test_home_and_variables_are_never_names_in_the_checkout(self) -> None:
        a = burndown_agent.allowed
        for tool, inputs in (("Grep", {"pattern": "x", "path": "~"}),
                             ("Glob", {"pattern": "**/*", "path": "~/work/_temp"}),
                             ("Write", {"file_path": "~/.gitconfig"}),
                             ("Read", {"file_path": "$HOME/.ssh/id_rsa"}),
                             ("Grep", {"pattern": "x", "path": "%USERPROFILE%"})):
            self.assertFalse(a(self.root, tool, inputs), (tool, inputs))
        self.assertTrue(a(self.root, "Grep", {"pattern": "x", "path": "scripts/~notes"}))

    def exit_code(self, outcome) -> int:
        async def fake(*_args):
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        target = self.root / "t.json"
        target.write_text(json.dumps({"kind": "delete", "key": "k", "paths": ["a.py"]}))
        argv, real = sys.argv, burndown_agent.run
        sys.argv = ["burndown_agent.py", "--target", str(target),
                    "--summary", str(self.root / "s.json")]
        burndown_agent.run = fake
        try:
            return burndown_agent.main()
        finally:
            sys.argv, burndown_agent.run = argv, real

    def test_exit_codes_separate_the_target_from_the_infrastructure(self) -> None:
        done = {"status": "done", "summary": "s", "files_changed": []}
        self.assertEqual(self.exit_code(done), 0)
        self.assertEqual(self.exit_code({**done, "status": "declined"}), 3)
        self.assertEqual(self.exit_code(burndown_agent.TargetFailure("out of turns")), 4)
        with self.assertRaises(RuntimeError):
            self.exit_code(RuntimeError("no result"))

    def test_only_the_five_tools_and_structured_output(self) -> None:
        a = burndown_agent.allowed
        for tool in ("Bash", "Task", "WebFetch", "NotebookEdit", "MultiEdit", None):
            self.assertFalse(a(self.root, tool, {"file_path": "scripts/a.py"}), tool)
        self.assertTrue(a(self.root, "StructuredOutput", {}))
        self.assertTrue(a(self.root, "Grep", {"path": "scripts"}))

    def test_search_patterns_stay_inside_the_checkout(self) -> None:
        a = burndown_agent.allowed
        self.assertTrue(a(self.root, "Glob", {"pattern": "scripts/**/*.py"}))
        self.assertTrue(a(self.root, "Grep", {"pattern": "..", "glob": "*.py"}))
        for pattern in ("/home/runner/**/*", "../../**/*", "scripts/../../x", "C:/x/*", "~/x", None):
            self.assertFalse(a(self.root, "Glob", {"pattern": pattern}), pattern)
        self.assertFalse(a(self.root, "Grep", {"pattern": "x", "glob": "/etc/*"}))


class Result:
    def __init__(self, subtype: str = "success", is_error: bool = False, out=None,
                 terminal_reason: str | None = None) -> None:
        self.subtype, self.is_error, self.result = subtype, is_error, "text"
        self.terminal_reason = terminal_reason
        self.structured_output = out if out is not None else {
            "status": "done", "summary": "s", "files_changed": []}
        self.total_cost_usd = 0.1


class AgentOutcomeTests(unittest.TestCase):
    """Whose failure it was decides whether the target is ever tried again."""

    def classify(self, result, denied=()):
        return burndown_agent.classify(result, list(denied))

    def test_too_big_or_out_of_bounds_is_the_target(self) -> None:
        for subtype in burndown_agent.TARGET_SUBTYPES:
            with self.assertRaises(burndown_agent.TargetFailure, msg=subtype):
                self.classify(Result(subtype, is_error=True))
        with self.assertRaises(burndown_agent.TargetFailure):
            self.classify(Result(), denied=["Bash"])
        with self.assertRaises(burndown_agent.TargetFailure):
            self.classify(Result(out="not a dict"))

    def test_api_and_transport_errors_are_the_infrastructure(self) -> None:
        for result in (None, Result("success", is_error=True),
                       Result("success", is_error=True, terminal_reason="api_error"),
                       Result("error_during_execution", is_error=True)):
            with self.assertRaises(RuntimeError) as caught:
                self.classify(result)
            self.assertNotIsInstance(caught.exception, burndown_agent.TargetFailure)
        self.assertEqual(self.classify(Result())["status"], "done")

    def test_an_error_on_the_target_size_or_output_is_the_target(self) -> None:
        for reason in burndown_agent.TARGET_REASONS:
            with self.assertRaises(burndown_agent.TargetFailure, msg=reason):
                self.classify(Result("success", is_error=True, terminal_reason=reason))

    def run_with_sdk(self, *events):
        """Drive run() through a stand-in SDK that yields or raises `events`."""
        import asyncio
        import types
        from unittest import mock

        class ResultMessage(Result):
            pass

        async def query(prompt, options):
            for event in events:
                if isinstance(event, Exception):
                    raise event
                yield ResultMessage(*event)

        sdk = types.SimpleNamespace(ClaudeAgentOptions=lambda **kw: kw, HookMatcher=lambda **kw: kw,
                                    ResultMessage=ResultMessage, query=query)
        target = {"kind": "delete", "key": "k", "paths": ["scripts/a.py"]}
        with mock.patch.dict(sys.modules, {"claude_agent_sdk": sdk}), \
                mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "t"}), \
                tempfile.TemporaryDirectory() as d:
            (Path(d) / "AGENTS.md").write_text("house rules")
            return asyncio.run(burndown_agent.run(target, Path(d), 1.0, 2))

    def test_the_result_not_the_exit_exception_decides(self) -> None:
        exited = RuntimeError("Command failed with exit code 1")
        with self.assertRaises(burndown_agent.TargetFailure):
            self.run_with_sdk(("error_max_turns", True), exited)
        with self.assertRaises(RuntimeError) as caught:
            self.run_with_sdk(("success", True), exited)
        self.assertNotIsInstance(caught.exception, burndown_agent.TargetFailure)
        with self.assertRaises(RuntimeError):
            self.run_with_sdk(exited)
        self.assertEqual(self.run_with_sdk(("success", False))["status"], "done")


if __name__ == "__main__":
    unittest.main()
