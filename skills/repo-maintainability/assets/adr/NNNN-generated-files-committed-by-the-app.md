# ADR NNNN — Generated files are committed to main by a dedicated App

Date: YYYY-MM-DD

Status: Proposed

## Context

ADR 0019 (decision 5) and ADR 0020 (point 5) promise files that a bot
rewrites on `main` after every merge and that no person or agent PR ever
edits: `CONTEXT.md`, `STATUS.md`, and the ratchet baselines under
`.maintainability/`. The `main` ruleset requires every change to arrive
through a pull request with signed commits. A workflow's `git push` is
neither, so the promise could not be kept as written.

Three ways out were put to the owner: a bot PR after every merge (a paid
review and a click per merge, forever); run artifacts that nobody commits
(baselines never lower, which defeats ADR 0019); or let one GitHub App
commit through GitHub's API, which signs the commit, and list that App as a
ruleset bypass actor so the commit lands without a PR. The owner chose the
third.

## Decision

1. A dedicated GitHub App, `<repo> Maintainability Bot` (ID `<id>`,
   installed on this repo only, Contents read/write and
   nothing else), is a bypass actor on the `main` ruleset with
   `bypass_mode: always`. It is not the release App: the Release Bot keeps
   its PR-opening role and no bypass, so the third-party release action
   never holds a bypass-capable token.
2. The App commits only through `scripts/ci/commit_via_api.py`
   (`createCommitOnBranch`): signed by GitHub, with `expectedHeadOid` so a
   concurrent push makes it fail rather than overwrite, and only the paths
   that changed.
3. The only workflow that mints this App's token is
   `.github/workflows/maintainability-main.yml`, in its last step, after
   every third-party tool has run; the only paths it commits are
   `CONTEXT.md`, `STATUS.md` and `.maintainability/*`. Its commits carry
   `[skip ci]`; they contain no source.
4. The App's private key is a repository secret the owner holds; its
   installation is reviewed in the organisation's GitHub Apps settings.

## What this ADR does not change

- The PR flow (ADR 0005) and merge rules (ADR 0012) for people and agents:
  every source change still goes through a reviewed PR. The App's bypass
  is used by one workflow for generated files, and that workflow's own
  `GITHUB_TOKEN` has no permissions.
- The gates: a bypass merge that added findings makes the next
  `ratchet.py update` refuse to grow, so the main-tier run fails loudly.
- ADR 0006: `CONTEXT.md` is checked for IPs, endpoints and key material
  before it is committed; it is a file index, not architecture.

## Consequences

- One ruleset entry to apply (`gh api -X PUT` from the versioned file) and
  one line in `scripts/test_review_policy.py`.
- The App is trusted with the same reach a repository admin's bypass has.
  That reach is bounded by the workflow that holds the key and by the
  signed, attributable commits it produces. Widening what the App commits
  needs this ADR amended.
- Revoking the App's key stops generated-file refreshes; releases are
  unaffected, since they use the other App.
