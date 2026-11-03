# ADR NNNN — Project state lives in GitHub Issues and the organisation board

Date: YYYY-MM-DD

Status: Proposed

## Context

<!-- Name the ledger, its size, and the rule that keeps it growing. One
number is enough. -->

The repository keeps project state in a hand-written file (`<ledger>`,
N KB, N timeline entries) under a rule in `AGENTS.md` that every hand-off
updates it. The rule has no removal step, so the file only grows; each
entry copies facts GitHub already records (PR state, CI run IDs, merges),
which go stale the moment anything happens; and every update is a PR that
re-runs the paid review gate, so updates are skipped and the file lags
anyway. The only check on it tests HTML structure, not size, duplication or
staleness.

GitHub already has what the file duplicates: issues with bodies and
comments, the organisation Project board with `Status`, `Area` and
`Horizon` fields, milestones, and the PR and CI history. What the file
holds that GitHub does not — bench and field evidence, blockers, the next
action — fits an issue comment, a labelled issue and a board column.

## Decision

1. **Issues are the ledger.** No hand-written tracker, ledger, status page,
   TODO or progress log is committed. A PR that adds one fails the
   `Records` check (`scripts/ci/check_ledgers.py`).
2. **Every PR names the issue or ADR it serves** (`Closes #N`, `Refs #N`,
   `ADR NNNN`); `scripts/ci/check_pr_links.py` fails it otherwise. The
   `no-issue` label is the typo-level escape, as `no-adr` is for the ADR
   gate.
3. **Every issue and PR lands on the organisation board when it opens**
   (`.github/workflows/project-sync.yml`). Blockers, decisions, deferrals
   and evidence are issues with the matching label, opened from the issue
   templates in `.github/ISSUE_TEMPLATE/`.
4. **Evidence is a comment on the issue it proves**, posted when observed,
   with the CI run or artefact link, and marked retrospective when it is.
   A closed issue is the only "done".
5. **`STATUS.md` is the only status file.** The main-tier workflow renders
   it from the board on every push to `main`, with a `generated-by:` first
   line and no timestamp. Nobody edits it.
6. **The ledger rule in `AGENTS.md` is replaced** by the five rules above.
   The ledger file is frozen on merge of this ADR and archived under
   `docs/archive/` by the next PR, which also moves its evidence rows to
   comments on the issues they prove. Its integrity scripts go with it.

## What this ADR does not change

- The PR flow (ADR 0005) and the merge rules (ADR 0012): agents still open
  Draft PRs, never self-approve, never merge without PR-specific owner
  direction. An issue closed by a merged PR is the record of that merge.
- The ADR gate: decisions still change through ADRs. An issue labelled
  `decision` is where a question waits; the ADR is where it is answered.
- What may be written down: no credentials, public infrastructure IPs,
  full hardware identifiers or private logs in an issue, a comment or
  `STATUS.md`, exactly as the ledger rule already required.

## Consequences

- Two one-time repository settings: `vars.PROJECT_NUMBER` and
  `secrets.PROJECT_TOKEN`, because `GITHUB_TOKEN` cannot read an
  organisation board.
- Two more deterministic checks per PR, each under ten seconds.
- A hand-off is an issue comment, not a PR, so it costs no review run and
  happens when the thing happened.
- The owner reads one generated page and one board instead of a file that
  was last reconciled whenever someone remembered.
