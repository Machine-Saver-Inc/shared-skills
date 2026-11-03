# Role: records and comments — repo-maintainability skill, rules R1–R6

Drop this file into the repository's review-role directory (on `platform`:
`.github/review/roles/`). It adds two things the linters cannot judge.

## Where state is recorded

Blocking if violated:

- The diff adds or edits a hand-written tracker, ledger, status page, TODO
  list or progress log. State goes in an issue on the project board; the only
  status file is the generated `STATUS.md`.
- The PR body names no issue and no ADR (`Closes #N`, `Refs #N`, `ADR NNNN`).
- Evidence (a bench result, a CI run, a device readback) is pasted into a
  file instead of posted as a comment on the issue it proves, with the run
  link.

## Comments

A comment says **why**: a constraint, a non-obvious decision, a workaround
and what it works around. Flag as a suggestion, with the line as evidence:

- A comment that restates the line below it (`# increment the counter`).
- A comment that narrates the author's process (`# now we loop over...`).
- A comment that describes a change rather than the code (`# fixed bug`,
  `# added for PR 42`); that belongs in the commit message.
- Commented-out code. `ruff` rule ERA001 catches most of it; flag what it
  misses.
- A docstring that repeats the function name as a sentence.

Do not flag the absence of comments, and do not ask for more of them. If the
code is unclear, the finding is about the code: a name, a split, a return
type. There is no comment-density rule in either direction.

## Output contract

As the repository's judge expects: `severity`, `confidence`, `file:line`,
one-sentence claim, evidence. No finding without evidence.
