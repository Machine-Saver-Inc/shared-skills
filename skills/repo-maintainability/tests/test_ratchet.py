"""The ratchet follows git moves with `--base` and is otherwise unchanged
(issue #181). A move that leaves a shim behind is a copy to git, not a rename,
and that is the move ADR 0022 prescribes, so it is the case that matters."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "scripts"
RATCHET = HERE / "ratchet.py"
SHIM = '#!/usr/bin/env bash\n# Shim (#181).\nexec bash "$(dirname "${BASH_SOURCE[0]}")/ci/a.sh" "$@"\n'


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


class Repo(unittest.TestCase):
    """A base branch holds scripts/a.sh, scripts/a.sh.bak and scripts/other.sh;
    the PR branch is made by each test."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git("init", "-q", "-b", "main", cwd=self.root)
        git("config", "user.email", "t@example.invalid", cwd=self.root)
        git("config", "user.name", "t", cwd=self.root)
        (self.root / "scripts").mkdir()
        self.body = "#!/bin/sh\n" + "".join(f"echo line {i}\n" for i in range(20))
        self.write("scripts/a.sh", self.body)
        self.write("scripts/a.sh.bak", self.body + "# bak\n")
        self.write("scripts/other.sh", "#!/bin/sh\nls $x\n")
        self.commit("base")
        git("checkout", "-q", "-b", "pr", cwd=self.root)
        self.baseline = self.root / "tool.baseline"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, rel: str, text: str) -> None:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, newline="\n")

    def commit(self, message: str) -> None:
        git("add", "-A", cwd=self.root)
        git("commit", "-q", "-m", message, cwd=self.root)

    def move(self, new: str = "scripts/ci/a.sh", shim: bool = False, edit: str = "echo edited\n") -> None:
        # The move is detected at git's default similarity, not only at 100%.
        self.write(new, self.body + edit)
        if shim:
            self.write("scripts/a.sh", SHIM)
        else:
            (self.root / "scripts" / "a.sh").unlink()
        self.commit("move")

    def ratchet(self, *args: str, stdin: str, baseline: str) -> subprocess.CompletedProcess:
        self.baseline.write_text(baseline, newline="\n")
        env = {**os.environ, "PYTHONUTF8": "1"}
        return subprocess.run([sys.executable, str(RATCHET), *args, "--baseline", str(self.baseline)],
                              cwd=self.root, input=stdin, check=False,
                              capture_output=True, text=True, env=env)


class MoveFollowing(Repo):
    def test_without_base_is_unchanged(self) -> None:
        # Byte-for-byte today's output: the moved file's finding is new.
        self.move()
        r = self.ratchet("check", stdin="scripts/ci/a.sh:3:1: warning: x [SC2086]\n",
                         baseline="scripts/a.sh:3:1: warning: x [SC2086]\n")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout.replace("\r\n", "\n"),
                         "NEW: scripts/ci/a.sh: warning: x [SC2086]\n\n"
                         f"1 new finding(s) not in {self.baseline} (1 total, 1 tolerated, 1 cleared since).\n")
        r = self.ratchet("check", stdin="scripts/other.sh:2:4: warning: y [SC2086]\n",
                         baseline="scripts/other.sh:2:4: warning: y [SC2086]\n")
        self.assertEqual((r.returncode, r.stdout.replace("\r\n", "\n")),
                         (0, "ratchet: no new findings (1 total, 1 tolerated, 0 cleared since)\n"))

    def test_pure_rename_passes(self) -> None:
        self.move()
        r = self.ratchet("check", "--base", "main",
                         stdin=".\\scripts\\ci\\a.sh:3:1: warning: x [SC2086]\n",
                         baseline="scripts/a.sh:3:1: warning: x [SC2086]\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("no new findings (1 total, 1 tolerated, 0 cleared since)", r.stdout)

    def test_move_with_shim_left_behind_passes(self) -> None:
        # The ADR 0022 move: git sees M at the old path and A at the new one.
        self.move(shim=True)
        r = self.ratchet("check", "--base", "main",
                         stdin="scripts/ci/a.sh:3:1: warning: x [SC2086]\n",
                         baseline="scripts/a.sh:3:1: warning: x [SC2086]\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # A finding the shim itself introduces is still new.
        r = self.ratchet("check", "--base", "main",
                         stdin="scripts/ci/a.sh:3:1: warning: x [SC2086]\n"
                               "scripts/a.sh:3:1: warning: q [SC2154]\n",
                         baseline="scripts/a.sh:3:1: warning: x [SC2086]\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("NEW: scripts/a.sh: warning: q [SC2154]", r.stdout)

    def test_move_plus_new_finding_fails_naming_only_the_new_one(self) -> None:
        self.move(shim=True)
        r = self.ratchet("check", "--base", "main",
                         stdin="scripts/ci/a.sh:3:1: warning: x [SC2086]\n"
                               "scripts/ci/a.sh:21:1: warning: z [SC2034]\n",
                         baseline="scripts/a.sh:3:1: warning: x [SC2086]\n")
        self.assertEqual(r.returncode, 1)
        self.assertEqual([l for l in r.stdout.splitlines() if l.startswith("NEW:")],
                         ["NEW: scripts/ci/a.sh: warning: z [SC2034]"])

    def test_jscpd_pair_with_one_moved_member_passes(self) -> None:
        self.move(shim=True)
        r = self.ratchet("check", "--base", "main",
                         stdin="bash: scripts/ci/a.sh + scripts/other.sh\n",
                         baseline="bash: scripts/a.sh + scripts/other.sh\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_jscpd_pair_is_resorted_when_the_move_changes_its_order(self) -> None:
        # jscpd_findings.py prints the two members sorted, so after the move
        # "scripts/other.sh" comes first.
        self.move(new="scripts/zz/a.sh", shim=True)
        r = self.ratchet("check", "--base", "main",
                         stdin="bash: scripts/other.sh + scripts/zz/a.sh\n",
                         baseline="bash: scripts/a.sh + scripts/other.sh\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_move_only_rewrites_the_whole_path(self) -> None:
        # scripts/a.sh.bak is untouched by the move, so its finding stays put
        # and a finding at scripts/ci/a.sh.bak would be new.
        self.move(shim=True)
        r = self.ratchet("check", "--base", "main",
                         stdin="scripts/a.sh.bak:3:1: warning: x [SC2086]\n",
                         baseline="scripts/a.sh.bak:3:1: warning: x [SC2086]\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.ratchet("check", "--base", "main",
                         stdin="scripts/ci/a.sh.bak:3:1: warning: x [SC2086]\n",
                         baseline="scripts/a.sh.bak:3:1: warning: x [SC2086]\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("NEW: scripts/ci/a.sh.bak: warning: x [SC2086]", r.stdout)

    def test_update_follows_the_move_and_still_refuses_growth(self) -> None:
        # On main the bot runs update against the merge's first parent; the
        # moved finding is not growth, a finding the edit added is.
        self.move(shim=True)
        r = self.ratchet("update", "--base", "HEAD^",
                         stdin="scripts/ci/a.sh:3:1: warning: x [SC2086]\n",
                         baseline="scripts/a.sh:3:1: warning: x [SC2086]\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.baseline.read_text(), "scripts/ci/a.sh: warning: x [SC2086]\n")
        r = self.ratchet("update", "--base", "HEAD^",
                         stdin="scripts/ci/a.sh:3:1: warning: x [SC2086]\n"
                               "scripts/ci/a.sh:21:1: warning: z [SC2034]\n",
                         baseline="scripts/a.sh:3:1: warning: x [SC2086]\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("refusing to add 1 finding(s)", r.stdout)

    def test_a_split_keeps_the_source_tolerated(self) -> None:
        # A copy whose source is still a real file (a split, not a shim):
        # what was tolerated at the source stays tolerated there too.
        self.write("scripts/ci/a.sh", self.body)
        self.write("scripts/a.sh", self.body + "echo kept\n")
        self.commit("split")
        r = self.ratchet("check", "--base", "main",
                         stdin="scripts/a.sh:3:1: warning: x [SC2086]\n"
                               "scripts/ci/a.sh:3:1: warning: x [SC2086]\n",
                         baseline="scripts/a.sh:3:1: warning: x [SC2086]\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_base_baseline_means_the_commit_that_last_wrote_it(self) -> None:
        # Two merges since the bot last wrote the baseline; a run that only
        # looked at the last one would miss the move.
        git("checkout", "-q", "main", cwd=self.root)
        self.baseline.write_text("scripts/a.sh:3:1: warning: x [SC2086]\n", newline="\n")
        self.commit("bot writes the baseline")
        self.move(shim=True)
        self.write("scripts/other.sh", "#!/bin/sh\nls $x\necho later\n")
        self.commit("a later, unrelated merge")
        r = self.ratchet("update", "--base", "baseline",
                         stdin="scripts/ci/a.sh:3:1: warning: x [SC2086]\n",
                         baseline="scripts/a.sh:3:1: warning: x [SC2086]\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.baseline.read_text(), "scripts/ci/a.sh: warning: x [SC2086]\n")
        r = self.ratchet("update", "--base", "HEAD^",
                         stdin="scripts/ci/a.sh:3:1: warning: x [SC2086]\n",
                         baseline="scripts/a.sh:3:1: warning: x [SC2086]\n")
        self.assertEqual(r.returncode, 1, "HEAD^ alone misses the earlier merge")

    def test_unresolvable_base_warns_and_follows_nothing(self) -> None:
        self.move(shim=True)
        r = self.ratchet("check", "--base", "no-such-ref",
                         stdin="scripts/ci/a.sh:3:1: warning: x [SC2086]\n",
                         baseline="scripts/a.sh:3:1: warning: x [SC2086]\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("cannot diff against no-such-ref", r.stderr)
        self.assertIn("NEW: scripts/ci/a.sh: warning: x [SC2086]", r.stdout)


if __name__ == "__main__":
    unittest.main()
