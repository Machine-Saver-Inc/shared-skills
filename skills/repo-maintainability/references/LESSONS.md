# Lessons

Append-only. One dated entry per repo per phase. Each entry says what was
expected, what happened, and whether the fix became a check or a sentence.
A lesson that became a check names the test that proves it.

## 2026-11-03 — platform, phase 0 (audit) and skill 0.1.0

**Expected:** a greenfield-style rollout — agent context file, architecture
doc, code graph, dead-code gate.

**Found:** the repo already governed decisions, architecture, supply chain
and review more strictly than any tool would. Two of the planned additions
would have competed with it:

- An AI-maintained `ARCHITECTURE.md` competes with ADR 0006 (LikeC4 is the
  only architecture record, generated views are never hand-edited, no IPs
  or credentials in the model). Dropped. Became a sentence in §0.
- A git-hook-regenerated `CONTEXT.md` breaks "reproducible from git" and
  would conflict across parallel agent PRs. Moved to a bot commit on `main`.
  Became the design of `maintainability-main.yml`.

**Found:** the gap was code shape, not maps. `scripts/` had ~400 top-level
files mixing source, tests, `_candidate` experiments, fixtures and attended
`.ps1`/`.sh` pairs. Nothing failed when it grew.

**Found:** a code graph cannot see how this repo invokes its scripts
(Makefile, workflows, Dockerfiles, systemd, TSV, runbooks). Became
`check_path_references.py`, proved to fail on a move that left a Makefile
line and a runbook line stale (`test_reference_check_fails_on_stale_makefile_and_runbook`).

**Found while proving the guards:** the reference check flagged its own
`.maintainability/layout-tolerated.txt` as a consumer of a moved file.
Baselines are records of findings, not consumers. `.maintainability/` is now
in the check's skip list (`test_reference_check_ignores_baseline_records`);
the main-tier workflow regenerates the tolerated list after each merge.

**Found:** `git` does not keep empty directories across branch switches, so
a test harness that `git mv`s into a family directory must `mkdir -p` it
first. Harness only; no change to the scripts.

**Licence check:** GitNexus is PolyForm Noncommercial and jCodeMunch needs a
paid licence in for-profit use — both looked open source at a glance. Always
read the LICENSE file, not the README badge.

**Decisions by the owner:** no paid or proprietary tools; burn-down cadence
every other day; the burn-down agent may use the existing paid review key,
budget-capped.
