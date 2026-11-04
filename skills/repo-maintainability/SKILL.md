---
name: "repo-maintainability"
description: "Fit a Machine Saver repository — existing or brand new — with self-updating, free, open-source tooling that keeps it understandable to humans and agents and stops agents from leaving it messier than they found it: a reference index, a layout gate, ratcheted lint/dead-code/duplication baselines, project state in GitHub Issues and the org Project board instead of hand-written trackers, a generated STATUS.md, a bot-maintained context map and code graph, and a serial burn-down scheduler. Use whenever Leo asks to clean up, reorganise or 'fix' a repo for agentic development, to start a new repo under the house rules, to add codebase-understanding or maintainability tooling, to stop a directory or a tracker file sprawling, to move bookkeeping into issues, or to set up a burn-down of technical debt — even if he only says the repo is getting hard to work in. Run it again on the same repo after each phase to record what was learned."
---

# Repo maintainability

**Skill version 0.2.5.** Published at `github.com/Machine-Saver-Inc/shared-skills`.
First run: `Machine-Saver-Inc/platform`, November 2026.

For any Machine Saver repository that agents develop in, whether it exists
already (§0–§7) or is being started today (§8). The problem it solves is
specific: agents add and rarely remove, so a repo with no gate on code shape
grows a flat pile of scripts, candidates and copied wrappers that nobody can
hold in their head, and a repo with no rule on where state lives grows a
hand-written tracker that nobody reads. This skill fits the repo with gates
that fail **only on regression**, puts state in GitHub Issues and the
organisation Project board, a map and a status page that rebuild themselves,
and a scheduler that burns the existing pile down one small PR at a time.

**Every rule here is enforced by a script in `scripts/`, not by this text.**
Each script was broken on purpose and watched go red before it was kept
(`tests/test_guards.py`; see `references/LESSONS.md`). When a new lesson
arrives, the first question is whether it can be a check; the sentence here
is the fallback.

**Nothing in the finished setup needs manual upkeep.** If a step you are
about to add would need a person to remember something, redesign it.

## 0. Before anything: read what the repo already enforces

Most repos Machine Saver runs are not greenfield. `platform` already had
per-directory `AGENTS.md`, binding ADRs, an architecture-as-code model with a
drift check, Renovate, release-please, gitleaks and an AI review gate with a
trusted-base guard. Two of the "obvious" additions (an AI-maintained
`ARCHITECTURE.md`, a git-hook context map) would have competed with rules the
repo already had and broken one of its principles.

So the audit comes first, and its output is a list of conflicts, not a
list of tools. Read, in this order:

1. The root `README.md` and every `AGENTS.md` / `CLAUDE.md`.
2. `docs/adr/` (or wherever decisions live) — note every ADR that governs
   docs, architecture, review or CI, because your changes will cite them.
3. `.github/workflows/`, the `Makefile`, `renovate.json`, any ruleset.
4. The largest flat directory. Count its top-level files with
   `git ls-files scripts | grep -c '^scripts/[^/]*$'` (not `grep -vc /`:
   every path contains a slash, so that always says 0). That number goes
   in the ADR.
5. Sort every top-level file in it into the families you intend to list.
   Whatever is left over is either an `allow_top_level` entry point or a
   group that needs a family of its own; ask the owner to name any group
   of more than a handful (on `platform`: 18 gateway and sensor onboarding
   scripts became `onboarding`).

Then write the conflict table before proposing anything. For `platform` it
was:

| Candidate | Conflict | Resolution |
| --- | --- | --- |
| MAP-style `ARCHITECTURE.md` | ADR 0006 makes LikeC4 + ADRs the only architecture record | dropped |
| ctxmap git hook | per-clone hooks are not "reproducible from git"; a committed `CONTEXT.md` regenerated per commit conflicts across parallel agent PRs | generate on `main` only, bot commit |
| Fallow | TS/JS only; repo is Python, bash, PowerShell, YAML, OpenTofu | dropped |
| A job added to `ci.yml` | the trusted-base guard fails any change to `ci.yml`, `.github/review/` or the review scripts (`PROTECTED` in `scripts/ai_review_sdk.py`) | ship the gates as their own workflow file, which the guard does not watch; still one gate per owner-reviewed PR |

## 1. The tools, and why each is free

| Layer | Tool | Licence | Runs where |
| --- | --- | --- | --- |
| Reference index | `scripts/check_path_references.py` (this skill) | MIT | PR tier |
| Layout gate | `scripts/check_layout.py` (this skill) | MIT | PR tier |
| Records gate | `scripts/check_ledgers.py`, `scripts/check_pr_links.py` (this skill) | MIT | PR tier |
| Board sync | `actions/add-to-project` | MIT | on issue/PR open |
| Status page | `scripts/render_status.py` (this skill) | MIT | main tier, bot commit |
| Ratchet | `scripts/ratchet.py` (this skill) | MIT | PR + main tier |
| Python lint | ruff, `assets/lint/ruff.toml` | MIT | PR + main tier |
| Dead code | vulture, shellcheck, PSScriptAnalyzer | MIT / GPL-3 (tool only) / MIT | PR + main tier |
| Duplication | jscpd | MIT | PR + main tier |
| Context map | ctxmap | MIT | main tier, bot commit |
| Code graph | codebase-memory-mcp | MIT, single binary, 66+ languages | main tier, committed index |
| Human graph | Understand-Anything | MIT | weekly, committed JSON |
| Tool versions | Renovate | already present | weekly |

Not used, and why: GitNexus (PolyForm Noncommercial), jCodeMunch (paid in
for-profit use), DeepWiki (public repos only), Greptile / Sourcegraph /
Mintlify / Swimm (paid), Repowise (AGPL-3), Graphify (overlaps the code
graph). Fallow is excellent but TS/JS only; use it if the repo is.

## 1b. Records: where state lives

Owner decision, November 2026, after `platform`'s `project-tracker.html`
reached 591 KB and 411 timeline entries under a binding "update before every
hand-off" rule that had no removal rule. Every rule below has a check; the
check is the rule.

| | Rule | Enforced by |
| --- | --- | --- |
| R1 | **Issues are the ledger.** No hand-written tracker, ledger, status page, TODO or progress log is committed. Blockers, next actions, decisions and deferrals are issues with the matching label. | `check_ledgers.py` (PR tier, fails on an added file); `assets/issue-templates/`, `assets/labels.json` |
| R2 | **Every PR names its issue or ADR** (`Closes #N`, `Refs #N`, `ADR NNNN`). The `no-issue` label is the typo-level escape, like `no-adr`. Bots and the release PR are exempt. | `check_pr_links.py` (PR tier) |
| R3 | **Every issue and PR is on the organisation board** from the moment it opens. One board, the fields `Status`, `Area`, `Horizon`. | `assets/workflows/project-sync.yml` |
| R4 | **Status is generated.** `STATUS.md` is rendered from the board on every push to `main`, carries a `generated-by:` first line, and is never edited. No timestamp: the commit is the timestamp. | `render_status.py` in `maintainability-main.yml` |
| R5 | **Evidence is an issue comment** with the CI run or artefact link, on the issue it proves, at the time it was observed. A closed issue is the only "done". | `assets/review-roles/records-and-comments.md` |
| R6 | **Comments say why, never what, and never hold code.** No comment-density rule in either direction; unclear code gets a better name or a split, not a comment. | ruff `ERA001` through the ratchet; the review role above |
| R7 | **Lint is ratcheted from the first PR**: ruff (`assets/lint/ruff.toml`), shellcheck, PSScriptAnalyzer, jscpd. On a new repo every baseline starts empty and `update` refuses growth, so there is never a day when it was allowed. | `maintainability-pr.yml`, `ratchet.py` |

Why not ban comments outright: the *why* then moves to commit messages and
ADRs, which an agent reading the function never sees, and it re-derives the
constraint, sometimes wrongly. ERA001 and the role rule remove the comments
that are slop; the ones left are the ones that stop slop.

If the repo uses release-please, run it with a **GitHub App installation
token** (`actions/create-github-app-token`; Contents and Pull requests
write) rather than `GITHUB_TOKEN` or a personal token: a PR opened by
`GITHUB_TOKEN` never triggers workflows, so the release PR arrives with no
checks; and a commit a personal token creates through the API is unsigned,
so a `required_signatures` rule blocks it anyway. GitHub signs the commits
an App creates, so the release PR is an ordinary PR; the PR-links step
exempts it by branch prefix. If the repo has an AI review gate with an
actor allowlist, the App's `<name>[bot]` login goes on it next to Renovate,
or the required review check refuses the release PR as a bot. And to make
an open release PR pick up a changed trusted base, update its branch
(`gh pr update-branch`); a rerun reuses the old event's base SHA.

Two one-time settings per repo, because `GITHUB_TOKEN` cannot touch an
organisation board: `vars.PROJECT_NUMBER` and `secrets.PROJECT_TOKEN` (a
fine-grained token with organisation Projects read/write). Labels:
`for l in $(jq -c '.[]' assets/labels.json); do gh label create "$(jq -r .name <<<"$l")" --color "$(jq -r .color <<<"$l")" --description "$(jq -r .description <<<"$l")" --force; done`.

## 2. The audit → ADR

Copy `assets/adr/NNNN-maintainability-gates.md`, number it after the repo's
last ADR, fill the Context from §0 and the conflict table, and keep the
"what this ADR does not change" section — it is what the owner reads first.
If the repo has an `adr-gate`, this ADR is what satisfies it for the whole
PR sequence.

If the repo has a hand-written ledger and a rule that keeps it (`platform`
had both in `AGENTS.md`), that rule changes only through its own ADR: copy
`assets/adr/NNNN-records-in-issues.md`. The ADR freezes the ledger on
merge; the archive and the evidence migration are the next PR.

## 3. Why the graph cannot see every path, and what can

A tree-sitter code graph resolves imports and calls inside parsed source.
A repo like `platform` invokes most of `scripts/` **by string**: Makefile
targets, workflow `run:` steps, Dockerfile `COPY`, compose `command:`,
systemd `ExecStart=`, `.tsv` manifests, sibling wrappers calling each other
by relative path, OpenTofu cloud-init templates, runbooks, a tracker HTML
page. And outside the repo: a bench runner's checkout, a local mirror,
scripts baked into published images.

So the graph is for **blast radius** (callers, duplicates, orphans), and
`check_path_references.py` is for **moves**. It indexes every file of every
type for every watched filename, by full path and by bounded basename, and
fails a PR that moves or deletes a file still named anywhere. The burn-down
agent runs `--index` first and updates every hit, runbooks included.

For consumers outside the repo, every move leaves a **shim** at the old path
for two releases — a bash/PowerShell stub that `exec`s the new location with
a deprecation line, or a Python module that re-exports. Published images are
pinned by tag so running devices are unaffected; the next build picks up the
new path. Residual risk: a human typing a path from memory, who gets the
deprecation line instead of a failure.

## 4. The PR sequence

One gate per PR, ADR first, because a trusted-base guard (and plain
reviewability) wants small workflow changes. Order:

1. **ADR + layout gate + reference index.** Stops the pile growing today
   and makes every later move safe. Copy the three scripts from this skill
   into the repo's `scripts/ci/` (never leave them at the top level of the
   directory you are gating). Write `.maintainability/layout.json` with the
   families you found in §0. Run `check_layout.py --baseline` once; commit
   the tolerated list. **Commit before proving a gate**: every gate diffs
   `base..HEAD`, so a staged move or deletion is invisible to it and the
   proof passes for the wrong reason.
1b. **Records ADR + records gate + board sync.** Where the repo has a
   hand ledger: the ADR from §2, the `AGENTS.md` rule replaced, the
   `Records` and `PR names its issue` steps, `project-sync.yml`, the issue
   templates and labels, the review role. The ledger file stays until the
   next PR archives it under `docs/archive/` (which `check_ledgers.py`
   allows) and moves its evidence rows to issue comments.
2. **Ratcheted baselines.** Add the remaining steps of
   `assets/workflows/maintainability-pr.yml`, ruff included. Seed the
   baselines **on the CI runners, not your machine**: copy
   `assets/workflows/maintainability-seed.yml` to the branch with the
   branch's name in its `push:` trigger (a `workflow_dispatch` only sees
   workflows on the default branch), push, download the artifacts, commit
   their files, and delete the seed workflow before the PR leaves Draft. Tool versions, paths and line endings then match
   what the PR tier will see. That dispatch is the only time
   `--allow-growth` is ever used.
3. **Context map + code graph + status page.**
   `assets/workflows/maintainability-main.yml`. One line in the root
   `AGENTS.md`: *Read `CONTEXT.md` and `STATUS.md` first; query the code
   graph before grepping.* Never a git hook.
4. **This skill's lessons.** Append what the first three PRs taught to
   `references/LESSONS.md` and bump the skill version.
5. **Burn-down.** `assets/workflows/maintainability-burndown.yml`, plus the
   repo-specific `burndown_pick.py` and `burndown_agent.py` (on `platform`,
   built on `scripts/ai_review_sdk.py`'s bridge). Every other day, serial,
   budget-capped. The PR goes through the repo's own review gate and the
   owner merges.

Each PR is a Draft PR from the agent, per the repo's own rules; the owner
reviews. That is the whole human cost.

## 5. The ratchet, which is the whole idea

Every finding tool pipes into `ratchet.py check --baseline <file>`. The
check fails only on findings not already in the baseline, with line numbers
stripped so a shifted line is not "new". The main-tier workflow runs
`ratchet.py update`, which rewrites the baseline from what remains and
**refuses to grow**. Nobody edits a baseline. Debt can only go down.

This is why the gates can be switched on in a repo with hundreds of findings
on day one without blocking anybody.

## 6. Still to build (as of 0.2.4)

- A finding tool that crashes or fails to start prints nothing, and an
  empty pipe looks like zero findings. Each ratchet step should capture
  the tool's exit code and accept only its documented "findings" codes
  before the ratchet sees the output (review suggestion on platform PR 5).

- `burndown_pick.py` / `burndown_agent.py` are specified in the burn-down
  workflow's comments and not yet written; they are repo-specific because
  they reuse the target repo's agent bridge.
- The weekly Understand-Anything job is a placeholder until the target repo
  has an agent runner it can use headless.
- Pin versions in the workflow templates against the registries before the
  first PR; the numbers in the templates are the ones known at writing.

## 7. When you come back to a repo

Run the audit again (§0), diff the conflict table, read `LESSONS.md`, then
check: did the baselines go down? Did any burn-down PR get closed rather
than merged, and why? Is there a file `check_ledgers.py` would have caught
if it had been there, and why wasn't it? Those answers are the next lesson.

## 8. Starting a new repository

Nothing to audit and nothing to burn down, so the whole of §4 lands in the
first PR, before any feature code. In this order, all from `assets/`:

1. `README.md` with the repo's purpose; `AGENTS.md` with the house rules
   (`platform`'s root `AGENTS.md` is the model: Draft PRs, Conventional
   Commits, never self-merge, read `CONTEXT.md` and `STATUS.md` first);
   `docs/adr/0001-<why-this-repo-exists>.md`. Decisions go in ADRs from
   day one.
2. `.github/ISSUE_TEMPLATE/` from `assets/issue-templates/`; labels from
   `assets/labels.json`; `vars.PROJECT_NUMBER` and `secrets.PROJECT_TOKEN`
   set; `project-sync.yml`.
3. `scripts/ci/` with every script in this skill's `scripts/`;
   `.maintainability/layout.json` naming the families the repo will have
   (`ci` is always one), `records.json` only if the defaults need changing,
   `ruff.toml` from `assets/lint/`.
4. `maintainability.yml` from `maintainability-pr.yml` complete, and
   `maintainability-main.yml`. Baselines are empty files, committed. From
   now on `ratchet.py update` refuses the first finding, so no debt is ever
   tolerated; `--allow-growth` is never passed in a new repo.
5. The review role from `assets/review-roles/` if the repo has an AI
   review gate; otherwise the same rules are the PR template's checklist.

The first feature PR then names its issue, lands in a family directory,
passes an empty baseline, and appears on the board and in `STATUS.md`
without anyone doing anything. That is the test of the setup: if the first
real PR needs a person to remember a step, §8 is wrong.
