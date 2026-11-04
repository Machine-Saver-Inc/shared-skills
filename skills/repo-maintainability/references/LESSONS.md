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

## 2026-11-03 — owner decisions after platform PR 1, skill 0.2.0

**Decided by the owner:** project state belongs in GitHub Issues and one
organisation board, not in a hand-written file; cleanliness is enforced by
lint and CI, not by sentences; comments that say *what* are slop, comments
that say *why* are not, and there is no density rule either way. These became
§1b (R1–R7) and §8, each with a check.

**Found:** platform's `project-tracker.html` was 591 KB with 411 timeline
entries and 40 blockers, each new entry written twice (verification and
timeline), old next-actions never removed, and caveats copied into every
entry ("HIL skipped" 21 times). The rule that kept it was one commit on
2026-10-13 with no ADR. Its only check tested HTML structure. The two PRs
before the maintainability one did not update it at all, because each
update is a PR that re-runs the paid review. Became `check_ledgers.py`
(`test_ledger_check_fails_on_a_hand_written_tracker`) and the ADR template
for moving a ledger into issues.

**Found:** GitHub already had most of the structure: 38 well-named open
issues, a board with `Status`/`Area`/`Horizon`, but only 17 of the 38 on the
board, 4 issues ever closed, no templates, no milestones. The missing piece
was never a tool, it was a check that a PR names its issue
(`test_pr_links_pass_on_issue_or_adr_and_fail_without`) and a workflow that
puts issues on the board.

**Found while linting the skill with its own config:** `check_layout.py`'s
`main` had complexity 15 against the ceiling of 12. The skill did not pass
its own rules until it was split. A skill that ships a lint config must run
it on itself in CI; shared-skills now does.

**Found:** comment density on platform's scripts is 1–3 %. Comments were
never the slop; 381 flat files, 55 `_candidate` files and 37/82 attended
`.ps1`/`.sh` pairs were. The owner's instinct to ban comments was aimed at
the right feeling and the wrong target; R6 keeps the aim and moves the
target.

**Found while proving the records gate on platform:** `check_ledgers.py`
flagged `scripts/ci/check_ledgers.py`, its own file, because the name
matches `*ledger*`. Second time a guard has caught its own files (0.1.0: the
reference check and its tolerated list). A ledger is a document, so the
check now examines document extensions only
(`test_ledger_check_ignores_code_named_after_ledgers`). Standing rule: the
first thing to run a new guard against is the PR that adds it.

**Found by ai-review on platform PR 2 (0 blocking, 6 suggestions), all
fixed upstream first:** the PR-links check re-ran only on push, so the
`no-issue` label and a body edit could not clear a red result (template now
listens to `edited`, `labeled`, `unlabeled`); a bare `#N` anywhere satisfied
it, including "PR #158" in prose (a GitHub keyword is now required,
`test_pr_links_needs_a_keyword_before_the_issue_number`); `render_status.py`
crashed on a bare JSON list (`test_status_render_accepts_a_bare_list`);
`ratchet.py`'s `--allow-growth` help still described the count rule;
`project-sync.yml` went red on the very PR that added it because its secret
did not exist yet (it now warns and passes until the settings exist).
Accepted, not fixed: a hand-written file can fake the `generated-by:` marker;
the review role catches that, and exact-matching the marker would couple two
scripts for a case nobody has a reason to attempt.

**Found:** platform's `ci.yml` still calls `scripts/check-project-tracker.js`,
and `ci.yml` is trusted-base protected. The archive PR that removes the
tracker therefore has to be the owner's own PR, or leave the scripts in
place and remove only the file. Write that into the records ADR's
Consequences next time.

**Found in this very run:** a Python helper that rewrites files from a
bash heredoc turned `\b` into a backspace and silently skipped three edits,
and the commit went out with a failing test. Edit files with a tool that
shows the diff, and never commit on a suite that is not fully green.

## 2026-11-03 — platform, archive PR (PR 3), skill 0.2.1

**Found:** the local proof of the archive PR passed for the wrong reason.
The scripts were `git rm`'d but not committed, and every gate diffs
`base..HEAD`, so the reference check saw nothing moved. CI then found four
dangling references. Became a sentence in §4 step 1: commit before proving.

**Found:** two of the four were the ADR that says the scripts are removed
and the archived tracker that once called them. A decision and an archive
name a path as it was, and must keep doing so; they are records, like
baselines, not consumers. `docs/adr/` and `docs/archive/` are now skipped
(`test_reference_check_ignores_decisions_and_archives`). Runbooks stay in:
a person follows them.

**Found:** platform's review shard contract refuses a per-file diff over
300 KB, and the archived tracker's rename was 608 KB. A file that size can
never be reviewed, moved or deleted under the normal gate; archiving it is
necessarily an owner-bypass PR. One more reason a ledger file must never
exist: the day it needs to go, the review gate cannot watch it go.

## 2026-11-03 — platform, release PR (PR 4), skill 0.2.2

**Found:** after `gates` became required, the next release-please PR could
never merge: a PR opened by `GITHUB_TOKEN` triggers no workflow, so the
required checks never report. v0.4.0 (203 commits since v0.3.0) went in by
admin bypass. Fix: release-please runs with a fine-grained token (Contents
and Pull requests write). Became a sentence in §1b.

**Found by ai-review on the token PR:** with a human-owned token the
release PR stops being a bot, so rule R2's PR-links step would block it,
since release-please writes no `Closes #N`. Exempted by its fixed branch
prefix `release-please--` in the template. Also: the token input falls back
to `github.token` when the secret is absent; an expired token is not absent
and fails loudly, which is the right signal to mint a new one. The first
draft of that comment claimed the fallback covered expiry; review caught it. Sentence and template, not a check: the gate
runs in the target repo's workflow and the proof is the next release PR.

## 2026-11-04 — platform, ratchet PR (PR 5), skill 0.2.3

**Found before seeding:** the developer machine is Windows, with no sudo in
WSL, no PSScriptAnalyzer, shellcheck 0.9.0 and node only on the Windows
side. Baselines seeded there would carry tool versions, path separators and
line endings the PR tier never sees, and the first CI run would report
"new" findings that were nothing of the kind. Became §4 step 2: seed on the
runners through a temporary dispatch workflow and commit the artifacts.
Became a check too: `ratchet.py` treats a backslash path and a slash path
as the same finding, on the baseline side as well as the input side
(`test_ratchet_treats_windows_and_posix_paths_as_the_same_finding`).

**Found:** `$_.ScriptPath` from Invoke-ScriptAnalyzer is the runner's
absolute path, so a PowerShell baseline would have been tied to the
runner's checkout directory. The template writes repo-relative paths.

**Found in this run, again:** the commit went out with the new test red,
because the check was `pytest | grep -E 'passed|failed' && commit`, and
grep succeeds on "failed" too. Second time a wrong local gate let a red
suite through. Gate on pytest's exit code, never on its text.

**Found while seeding:** `gh workflow run` answered "not found on the
default branch": a `workflow_dispatch` is only addressable once the file
exists on `main`. The seed workflow now triggers on push to the seeding
branch instead; the template carries a placeholder branch name.

**Found on the first seed:** the jscpd baseline came back empty, which
looked like good news and was a dead gate: `--silent` suppresses the clone
list, not just the progress bar. The templates now run jscpd without it,
with `NO_COLOR=1` so no escape codes reach the baseline, and strip the
`[line:col - line:col]` ranges so a clone that moves is not "new". Also:
`actions/upload-artifact` skips dot-directories unless
`include-hidden-files: true`, so the Linux baselines never uploaded. A
baseline of zero on day one is a finding about the pipeline, not the code.

**Found on the second seed:** ruff's concise output ends with "Found N
errors." and a fixable-count line; both landed in the baseline and would
have changed on every run. The pipelines keep only `path:line:col: ` lines.
The PowerShell baseline came back with CRLF because `write_text` on a
Windows runner uses the platform newline; `ratchet.py` now writes POSIX
endings everywhere (`test_ratchet_writes_posix_line_endings_everywhere`,
red on Windows first). And the 0.2.0 templates had the ruff step's two
lines joined into one, a Python heredoc having eaten the `\`-newline; the
same bug that bit the 0.2.0 workflow on platform. Templates are files to
edit with a diff in front of you, not strings to rewrite in a script.

## 2026-11-04 — platform, first token-authored release PR, skill 0.2.4

**Found:** the first real release PR after the token change (0.5.0) ran
every check and got a clean review, then sat `BLOCKED`: the ruleset
requires signed commits, and a commit release-please creates through the
API with a personal token is unsigned. Half of the problem was solved by
the token (checks run); the other half needs a GitHub App installation
token, whose API commits GitHub signs. §1b now says App, not PAT. Rule of
thumb: before choosing a credential for a bot that commits, read every
rule on the protected branch, not just the status checks.

**Carried forward from review:** a finding tool that crashes prints
nothing and an empty pipe is indistinguishable from zero findings. Listed
in §6 until the ratchet steps check exit codes.

## 2026-11-04 — platform, the App-authored release PR, skill 0.2.5

**Found:** the first release PR the App opened had a GitHub-signed commit
and every deterministic check green, and the review gate refused it: the
guard allows human actors and `renovate[bot]`, and the App is a bot. The
allowlist gained `machine-saver-release-bot[bot]` (platform PR 8, an
owner-bypass PR since the guard is trusted-base). §1b now says so for any
repo with an actor allowlist: a bot that may open PRs must be on it.

**Found:** release-please does not rewrite an open release PR whose
content has not changed, so the unsigned PR stayed unsigned after the
switch to the App; closing it made the next run open a signed one. And
re-running a failed review job reuses the original event's base SHA, so
the old guard runs again; `gh pr update-branch` fires a new event against
the current trusted base, and the merge commit it adds is GitHub-signed.

**Proof:** release PR #175, author `machine-saver-release-bot[bot]`,
`verification.verified: true`, all checks green, 0 blocking findings,
merge state CLEAN with no bypass. #167 closed on evidence.

## 2026-11-04 — platform, main tier (PR 9), skill 0.3.0

**Found:** a bot cannot `git push` to `platform`'s `main`: the ruleset
requires a pull request and signed commits, and a runner's push is neither.
Three ways out were put to the owner (App as bypass actor with API commits;
refresh PRs through paid review on every merge; artifacts only). He chose
the first. `commit_via_api.py` sends `createCommitOnBranch`, which GitHub
signs, with `expectedHeadOid` so a race fails instead of overwriting, and
only the paths that changed. The App is a bypass actor
(`actor_type: Integration`, `bypass_mode: always`); the policy test pins it.
Payload and no-op paths are unit-tested; the live commit is proven by the
first run on `main`.

**Found:** the template's tool pins were guesses. ctxmap is 0.1.0 on PyPI
(not 0.3.2) and builds a structural map offline with no LLM, 6 KB for 316
files; its "Last updated" line is replaced, since a changing line would
make every run a change. codebase-memory-mcp is 0.12.1 and keeps its index
per user, driven by MCP calls, so the "committed index" promise in the ADR
template was not implementable as written; the graph is deferred to its
own issue and §6 says so. Pin against the registry before writing the ADR,
not after.

**Found:** on a Windows developer machine ctxmap and `render_status.py`
both died on cp1252 (`✓`, `·`); `PYTHONUTF8=1` and an explicit UTF-8
stdout fix it. Runners are fine; the lesson is for whoever proves things
locally on Windows.

**Found by ai-review on the main-tier PR (2 blocking):** the templates
set `defaults: run: shell: bash`, and GitHub runs an explicit bash shell
with `-o pipefail`, so every ratchet pipe would fail the moment a tool
found anything, while the comment two lines above said never to add
pipefail. The PR-tier workflow on platform only passed because its copy
had no explicit shell. Both templates drop it, with the reason inline.
And: a ruleset bypass for an App is a decision, not a setting; it got its
own ADR (`assets/adr/NNNN-generated-files-committed-by-the-app.md`).

**Found by ai-review on the main-tier PR, third pass (1 blocking):** the
ruleset bypass had gone to the release App, whose token the release-please
action also receives, so a third-party action held a bypass-capable
token. The owner chose a second App: `Maintainability Bot`, Contents write
only, token minted in the last step of the one workflow that commits, and
the only bypass actor. Rule: one App per trust boundary; a bypass-capable
token never reaches a step that runs someone else's code.

**Found by ai-review on the main-tier PR, fourth pass (1 blocking):** the
App token was minted in the same job that had just run pip- and
npm-installed tools, so a compromised package could leave a `.pth` or a
patched `commit_via_api.py` behind and use the token. The commit now
happens in a separate job: fresh checkout of the trusted commit, nothing
installed, token minted there and nowhere else, generated files arriving
as artifacts, and `commit_via_api.py --allow` refusing any path outside
the ADR's list (`test_api_commit_refuses_paths_outside_the_allow_list`).
Hash-pinned installs for the generating job are the next tightening (§6).

**Found by ai-review on the main-tier PR, fifth pass (2 blocking):** a
repository secret reaches a workflow on any pushed branch, so anyone who
can push a branch could mint the bypass App's token and commit to `main`.
The key is now an Environment secret with a `main`-only deployment branch
policy and the commit job runs in that environment. And `permissions: {}`
at the workflow level with nothing at job level blocks `actions/checkout`
on a private repo; each job grants `contents: read`. Both are in the
template and in the ADR template's point 4. Setting an environment secret
needs the key value, which only the owner has: creating the environment
and its branch policy is the agent's, re-setting the secret into it is the
owner's, and the repository-level copy is deleted after.
