# NNNN. Maintainability gates and burn-down

Date: YYYY-MM-DD

## Status

Proposed

## Context

<!-- Fill from the audit (skill §0). Two or three sentences on what the repo
already governs and what it does not. Name the symptom with a number. -->

The repository governs decisions (ADRs), architecture (LikeC4, drift-checked),
supply chain (signed images, Renovate) and review (deterministic gates, AI
review). It governs nothing about the shape of the code. `scripts/` holds
~N top-level files: source, tests, `_candidate` experiments, fixtures and
attended wrapper pairs, with no check that fails when it grows.

Agents add and rarely remove. Without a gate that fails on regression, every
agent session leaves the directory larger than it found it.

## Decision

Add five deterministic gates to the PR tier, ahead of AI review, each failing
**only on a regression against a committed baseline**, so existing debt never
blocks a PR:

1. **Path references** — a file under `scripts/` cannot move or be deleted
   while anything in the repo still names it (full path or basename). A code
   graph cannot see Makefile, workflow, Dockerfile, systemd, TSV or runbook
   references; this textual index can.
2. **Layout** — no new top-level file in `scripts/`; new files go in a listed
   family subdirectory.
3. **Dead code** — vulture (Python), shellcheck (shell), PSScriptAnalyzer
   (PowerShell), ratcheted.
4. **Duplication** — jscpd, ratcheted.
5. **Context map** — `CONTEXT.md` regenerated and committed by a bot on every
   push to `main`; `AGENTS.md` tells agents to read it first. Never written by
   a person, an agent PR, or a local hook.

Baselines live in `.maintainability/` and are written only by the main-tier
workflow, which can lower them and refuses to raise them.

A burn-down workflow opens one Draft PR every other day, serially, that
retires, deletes, dedupes or moves exactly one target, in that order of
safety. Moves leave a shim at the old path for two releases. The PR goes
through the normal review gate; the owner merges.

All tools are MIT or Apache licensed, run locally or in CI, and are pinned
and updated by Renovate. The burn-down agent is the only paid component and
is budget-capped per PR.

## What this ADR does not change

- ADR 0006: the LikeC4 model remains the only architecture record. The
  context map is a file index, not architecture, and is checked for IPs,
  URLs and key material before commit.
- ADR 0005 / 0012: burn-down PRs are agent Draft PRs under the existing
  review and merge rules. They never self-approve or merge.
- The trusted-base guard: this ADR's workflows land through owner-reviewed
  PRs like any other workflow change.

## Consequences

- Four to five additional required checks per PR, all under a minute.
- `scripts/` stops growing at the top level from the day gate 2 merges.
- Debt is cleared at roughly one target per two days; a larger batch is a
  one-line change to the scheduler.
- A move the index cannot see (a human typing a path from memory) hits the
  shim's deprecation line instead of failing.
