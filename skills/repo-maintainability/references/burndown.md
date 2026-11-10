# Setting up the burn-down (§4 step 5)

The burn-down opens one Draft PR at a time that removes one baselined
finding. It ran first on `platform` (ADR 0022 there); every script here is
the one that runs there, with the forbidden paths made per-repo.

## What to copy

| From this skill | To the repo |
| --- | --- |
| `scripts/burndown_pick.py`, `burndown_agent.py`, `burndown_mechanical.py`, `burndown_ratchets.sh` | `scripts/ci/` |
| `assets/workflows/maintainability-burndown.yml` | `.github/workflows/` |
| `tests/test_burndown.py` | `scripts/ci/test_burndown.py`, run from the PR tier |

`burndown_ratchets.sh` names the directories the finding tools scan
(`scripts cloud mcp eval` for vulture, `scripts cloud edge` for jscpd). They
must match the PR and main tiers, or `verify` judges a different tree from
the one the gates baseline.

## What to decide

- **Forbidden paths.** Burn-down never changes workflows, the gates and
  baselines, decisions, house rules or release files, in any repo. Add the
  repo's own in `.maintainability/burndown.json`:
  `{"forbidden": ["edge/base/", "docs/architecture/", "scripts/ai_review_sdk.py"]}`
  (platform's: code that needs two-vendor hardware tests, the architecture
  model, the review machinery). It is read from `HEAD`, so a patch cannot
  widen its own reach, and `.maintainability/` is forbidden anyway.
- **The agent's SDK pin.** The workflow installs
  `.github/review/sdk-requirements.txt` (`claude-agent-sdk==<version>`). A
  repo without an AI review gate adds that file; Renovate keeps it current.
- **Budget.** `BURNDOWN_BUDGET_USD` (5) and `BURNDOWN_MAX_TURNS` (60) per
  attempt. A retire costs nothing; it is mechanical.

## One-time setup

1. A GitHub App, `<repo> Burn-down Bot`: Contents and Pull requests
   read/write, installed on this repo only, **no ruleset bypass**. A PR
   opened with `GITHUB_TOKEN` never triggers CI, so it could never pass.
2. Its ID in `vars.BURNDOWN_APP_ID`; its key as `BURNDOWN_APP_PRIVATE_KEY` in
   an environment `burndown-bot` whose deployment policy is `main` only.
   The bootstrap script creates the environment and reads the policy back;
   a test pins it (on platform, `scripts/test_review_policy.py`).
3. If the repo has an AI review actor allowlist, add the App's `[bot]`
   login, or its PRs get no review.
4. `ANTHROPIC_API_KEY` as a repository secret, and the `burn-down` label
   (`assets/labels.json`).

## The trust boundary, in one paragraph

`pick` has no model and no write token. `work` runs the model with
Read/Glob/Grep/Edit/Write only, inside the checkout and out of the forbidden
paths, with no GitHub token; nothing the model wrote is executed there, only
the gates. Its patch is hostile. `open` copies the judging scripts aside,
applies the patch, refuses any path the target does not allow, any symlink,
mode change or binary, then mints the App token for one signed API commit
and one Draft PR. `record` turns a declined or failed target into a closed
`burndown/<key>` issue so it is never retried; reopen it to allow another
attempt. The PR's own CI runs the tests; the owner merges.

## Reusing the agent

`burndown_agent.run_model(prompt, root, budget, turns, schema)` is the
bounded, tokenless model run on its own, and `classify` turns its result
into output, a target failure or an infrastructure failure. A second
scheduled agent (platform's weekly bug sweep, issue 199) imports both rather
than copying them; its summary carries `total_cost_usd`, `num_turns` and
`usage`.
