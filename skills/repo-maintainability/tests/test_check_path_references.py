"""The instruction-file gate (`check_path_references.py --docs`) is seen to fail
against its own violation before it is trusted."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(HERE))

import check_path_references as cpr  # noqa: E402


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


class DocsGate(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git("init", "-q", cwd=self.root)
        (self.root / "edge").mkdir()
        (self.root / "docs" / "runbooks").mkdir(parents=True)
        (self.root / "edge" / "vendor.env").write_text("X=1\n")
        (self.root / "docs" / "runbooks" / "real.md").write_text("# real\n")
        (self.root / "scripts").mkdir()
        (self.root / "scripts" / "org-up.sh").write_text("#!/bin/sh\n")
        git("add", "-A", cwd=self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_docs(self) -> subprocess.CompletedProcess:
        env = {**os.environ, "PYTHONUTF8": "1"}
        return subprocess.run([sys.executable, str(HERE / "check_path_references.py"),
                               "--root", str(self.root), "--docs"],
                              check=False, capture_output=True, text=True, env=env)

    def test_existing_paths_pass(self) -> None:
        (self.root / "README.md").write_text(
            "See `docs/runbooks/real.md`, `edge/`, `vendor.env` (bare name anywhere), "
            "`edge/vendors/<vendor>/` (placeholder), `robustel/{a,b}` (brace set), "
            "`.github/workflows/*.yml` (glob), `make eval` and `lora` (not paths).\n")
        (self.root / "Makefile").write_text("org-up:\n\tbash scripts/org-up.sh\n")
        r = self.run_docs()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_missing_path_fails_and_names_the_line(self) -> None:
        (self.root / "README.md").write_text("ok `docs/runbooks/real.md`\nbad `docs/gone.md`\n")
        r = self.run_docs()
        self.assertEqual(r.returncode, 1)
        self.assertIn("README.md:2: names a path that does not exist: docs/gone.md", r.stdout)

    def test_makefile_bare_tokens_are_checked(self) -> None:
        (self.root / "Makefile").write_text(
            'x:\n\t@echo "see Pre-Hardware Setup Sequence.md" && exit 1\n')
        r = self.run_docs()
        self.assertEqual(r.returncode, 1)
        self.assertIn("Makefile:2: names a path that does not exist: Sequence.md", r.stdout)

    def test_referrer_relative_paths_resolve(self) -> None:
        (self.root / "edge" / "AGENTS.md").write_text("values live in `vendor.env`; see `../docs/runbooks/real.md`\n")
        r = self.run_docs()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_candidates_skip_urls_flags_and_commands(self) -> None:
        found = cpr.doc_candidates(
            "`https://example.invalid/x.md` `--base` `#L12` `a/b.py` `make eval` "
            "`bash scripts/x.sh robustel config` `Development Plan.md` `docs/y.md#top` "
            "`C:\\Users\\x.md` [link](docs/z.md) `(docs/w.md)`", True)
        self.assertEqual(found, [(1, "a/b.py"), (1, "scripts/x.sh"), (1, "Development Plan.md"),
                                 (1, "docs/y.md"), (1, "docs/w.md"), (1, "docs/z.md")])

    def test_fenced_code_is_scanned_for_bare_paths(self) -> None:
        text = "prose scripts/not-checked.sh\n```bash\nbash scripts/gone.sh config\n```\n"
        self.assertEqual(cpr.doc_candidates(text, True), [(3, "scripts/gone.sh")])

    def test_dead_path_inside_a_command_fails(self) -> None:
        (self.root / "README.md").write_text("run `bash scripts/missing.sh --flag`\n")
        r = self.run_docs()
        self.assertEqual(r.returncode, 1)
        self.assertIn("README.md:1: names a path that does not exist: scripts/missing.sh", r.stdout)

    def test_recipe_relative_script_resolves_by_name(self) -> None:
        (self.root / "Makefile").write_text("up:\n\tcd scripts && ./org-up.sh\n")
        r = self.run_docs()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
