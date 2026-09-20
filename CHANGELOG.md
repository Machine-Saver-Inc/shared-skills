# Changelog

Both things in this repository carry a version. They move together: a change to
the shell bumps `ms-appkit`, and bumps `ms-desktop-app` as well when it changes
what the skill says.

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
