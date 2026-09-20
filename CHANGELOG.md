# Changelog

Both things in this repository carry a version. They move together: a change to
the shell bumps `ms-appkit`, and bumps `ms-desktop-app` as well when it changes
what the skill says.

## 2026-09-20

### ms-appkit 1.1.0

**What's new** is now a window rather than a message box, because a message box
sizes itself to its text and does not scroll. One release made it 2042 pixels
tall on a 1080-pixel screen: the bottom half was unreachable, including the
button that closes it. Reported against the Espec program as issue #9.

- `NotesWindow` — a resizable dialog holding a `QTextBrowser` that renders the
  Markdown, capped at 60% of the available screen height, with **Close** on the
  left and **Open the release page** on the right.
- `ms_appkit.update.notes.what_changed()` — the part of a release body above
  the first horizontal rule. Somebody who pressed **What's new** has already
  installed the program and does not need the install steps; that was the other
  half of the release-page complaint. Qt-free, so what the window will show can
  be asserted without building one.
- `housekeeping.lint_faults()` — runs `ruff` from the test suite, and complains
  rather than passing quietly when it is not installed. The rule set is now
  stated in `pyproject.toml` so it means the same thing here and in the build.
- `misplaced_back_buttons()` no longer closes over a loop variable — found by
  the wider rule set, and it would have read the wrong file's labels the first
  time the closure outlived its iteration.
- `housekeeping.notes_window_faults()` — four checks, each proved to fail
  against its own violation: the window fits the screen, it scrolls *with the
  bar left on*, the notes are rendered rather than shown as source, and the
  install steps are not shown to somebody already running the program.

### ms-desktop-app 2.2.0

- §4 gains the rule this cost: a dialog that sizes itself to its content is a
  clipping bug waiting for a long enough input. `QMessageBox` for a sentence;
  a scrollable window for anything a person wrote.
- A checked range is not a usable one — a scrollbar switched off still reports
  its range, and the first version of that guard passed against its own
  violation because of it.
- §6 and §7: run the build's lint from the test suite, and wait for `main` to
  go green *before* tagging. Both learned the same afternoon, from an import
  in the wrong order that went out with a tag on it.
- §6 again, ten minutes later: **state the lint's rule set.** With no
  `[tool.ruff]` section each side fell back to its own installed default —
  nothing found locally, twenty-one findings in CI, same commit. A lint whose
  configuration is implicit is two different lints sharing a name.

## 2026-09-19

### ms-appkit 1.0.0 — first release

The shared shell, lifted out of the first application built on it and made
general. What an application gets by importing it, rather than by copying it:

- **The footer** — Report a problem, the Machine Saver mark, the version and
  when it last checked, on every screen.
- **`AppWindow`** — the update banner, the screens, the footer, the problem
  report and the action trail already wired. An application adds screens and
  answers two questions: what to put in a report, and when it is a bad moment.
- **`action_bar`** — Back on the left, the action that moves forward on the
  right, decided in one place.
- **59 Lucide icons**, vendored with their licence, tinted to the colour of the
  text beside them so they survive a machine set to dark.
- **`button` / `primary`** — one helper, three roles, and the place a press is
  recorded for the problem report.
- **The update check** — one trust context carrying both certificate stores,
  numeric version comparison, checksum verification, and three honest outcomes
  rather than two.
- **The problem report** — Qt-free so its output can be asserted, home paths
  redacted because the repository is public, and an editable preview so what is
  posted is what the person agreed to.
- **`housekeeping`** — the house rules as functions an application's own test
  suite calls, so a lesson learned in one program gates all of them.
- **`bootstrap.run`** — logging, the stylesheet chosen for the machine's theme,
  `--version`, and an optional single-instance lock.
- **`template/`** — a runnable two-screen application to copy.

### ms-desktop-app 2.1.0

- §0 is new: do not build the shell, import it. Every section that described
  something the kit now provides says so and stays as the reasoning.
- The house rules moved from a file each repo copies to functions in
  `ms_appkit.housekeeping` that each repo calls, so they stop drifting.
- Icons ship with the kit; adding one is a change to the kit, not to an app.
- §13 describes this repository and how the two versions move together.
- A third guard found passing against its own violation is recorded: a base
  button role was being satisfied by one of its own sub-roles.

## Before this repository

`ms-desktop-app` 1.x and 2.0.0 were maintained as a personal skill while the
pattern was worked out on `espec-temperature-cycling`. 2.0.0 is the version
that first named Lucide, reversed the navigation order and introduced the
button register.
