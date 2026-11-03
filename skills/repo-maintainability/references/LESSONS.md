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

## 2026-11-03 — platform, phase 1 (ADR 0019 + layout gate + reference index), skill 0.1.1

**Expected:** copy three scripts, list nine families, add a two-step
workflow; the trusted-base guard fails the workflow change and the owner
reviews it.

**Found:** the handoff's count command, `git ls-files scripts | grep -vc /`,
prints 0, because every path contains a slash. The right count is
`grep -c '^scripts/[^/]*$'`: 381. Became a sentence in §0, with the command.

**Found:** the nine families from the audit covered 343 of 381 files. Of the
38 left over, 3 were the named entry points, about 17 scattered one-offs, and
18 one coherent group (gateway enrollment/identity/telemetry plans and sensor
activation/enrollment/import) with no family. Without one, the first new
onboarding script would have failed the gate with nowhere legal to go. The
owner named it `onboarding`. Became §0 step 5: sort every file before
writing `layout.json`, and ask about any leftover group.

**Found:** the trusted-base guard did **not** trip. It protects `ci.yml`,
`.github/review/` and the three ai-review scripts (`PROTECTED` in
`scripts/ai_review_sdk.py`), not every workflow. A separate
`maintainability.yml` passes it; the PR template's alternative ("or as a job
in its existing ci.yml") would have tripped it. The conflict-table row and
the template comment now say so. Sentence, not check: the guard's scope is
the target repo's, not ours.

**Found:** ai-review (0 blocking, five suggestions) caught two real bugs in
`ratchet.py update`. It compared counts, not findings, so a fixed finding
paid for a new one; and it skipped the check when the baseline was empty,
so a baseline that reached zero stopped guarding. Both now compare the
finding sets and refuse anything new without `--allow-growth`. Became
checks: `test_ratchet_refuses_a_swapped_finding`,
`test_ratchet_refuses_to_grow_an_empty_baseline`. Both went red first.
Side effect, intended: a missing baseline now also needs `--allow-growth`,
which is what §4 already said the first run uses.

**Found:** `check_path_references.py` told readers the shim rule was in §4;
it is in §3. Became a check that the section the message names is the one
that explains shims (`test_reference_check_points_at_the_section_that_explains_shims`).

**Found while proving the gate on platform:** moving
`scripts/check-mender-compose.sh` left five stale references, not two:
the Makefile, a runbook, both workflows and `project-tracker.html`. The
index caught them all; a code graph would have caught none.

**Found:** platform's AGENTS.md makes a `project-tracker.html` entry binding
before any hand-off after a push or PR checks. Each extra commit reruns the
paid review, so write the tracker entry in the same push as the last fix
where you can, not as a separate one.

**Still open:** platform's `scripts/ci/` copies predate these fixes. Ship the
fixed `ratchet.py` and `check_path_references.py` to platform with the
ratchet PR (§4 step 2), which is the first PR that runs the ratchet.
