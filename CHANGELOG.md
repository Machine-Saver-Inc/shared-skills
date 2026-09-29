# Changelog

Both things in this repository carry a version. They move together: a change to
the shell bumps `ms-appkit`, and bumps `ms-desktop-app` as well when it changes
what the skill says.

## 2026-09-29 - Espec integration

### ms-appkit 1.4.0

- Helper text and status colors now stay readable in both light and dark themes.
- Closing waits for network workers to finish and cancels an active download.

Programs stay open reliably and wait for hardware work to finish before
showing or installing an update. Reporting a problem still opens if the
program cannot read part of its current state.

- Retain the main window throughout the application event loop. `run()` in
  1.3.x discarded it right after building it (introduced in 1.3.0).
- Defer update offers while busy and re-check before invoking an installer.
- Add `refresh_busy_state()` for application job start/finish hooks.
- Keep running update workers alive across repeated checks and window close.
- Keep the report dialog available when an application's context hook fails.
- Five lifecycle regressions were proved failing against 1.3.0 before fixing.

### ms-desktop-app 2.4.2

Document the job lifecycle hook used to defer and re-offer updates.

## 2026-09-28 (evening)

### ms-appkit 1.3.1

Nothing changes on screen in a released program. A copy built without its
sign-in key now says so when asked to sign in, instead of failing at Google.

- `identity.stamped_secret(package)` — the OAuth client secret the release
  build wrote into `<package>/_client_secret.py`, else `MS_GOOGLE_CLIENT_SECRET`,
  else empty.
- `tracked_secret_faults` now also fails a tracked `_client_secret.py`.
- Three new tests, each proved to fail against its own violation.
- The template's **Sign out** sits beside the name of whoever is signed in, sized
  to its words rather than stretched across the window.

### ms-desktop-app 2.4.1

- §1a said to put the client secret in `_private.py`. The family's own
  credential rule fails that file, correctly. The secret now comes from the
  repository secret `GOOGLE_CLIENT_SECRET`, stamped in by the release workflow;
  *Using it* and the `release.yml` fragment say how. Found while setting up the
  first private program.

## 2026-09-28 (later)

### ms-appkit 1.3.0

A program can now be **private**. The person using it signs in with their
machinesaver.net Google account before it opens, it updates from Machine
Saver's own release store instead of GitHub, the passwords it needs are fetched
after sign-in instead of being kept in a file, and **Report a problem** emails
the support group. Public programs are unchanged.

- `configure(..., visibility="private", private=PrivateConfig(...))`, and the
  same two arguments on `bootstrap.run`. A private program without its sign-in
  settings, or a public one with them, is refused at startup.
- `ms_appkit.auth` — sign-in through the system browser (PKCE, loopback on
  `127.0.0.1`), only the configured domain let in, the sign-in kept in the
  operating system's credential store, 14 days offline, locked out at once if
  Google says the account is suspended. No Qt, so every path is tested.
- `ms_appkit.signin` — the sign-in screen, and the gate `run` passes through
  before it builds the window.
- `GoogleCloudStorage` release channel, and `channel.feed()` to write the
  `latest.json` it reads. Not being signed in is a failed update check with a
  sentence, not a crash.
- `ms_appkit.secrets.get(name)` — Secret Manager, with the person's own token.
- **Email it to support** replaces **Open GitHub to post it** in a private
  program's report dialog; `diagnostics.redact` now also removes anything
  shaped like a Google credential, from every report.
- The footer says who is signed in, and when the program is working offline.
- Three new house rules: `visibility_faults`, `tracked_secret_faults`,
  `private_config_faults`. The template carries them, a **Sign out** on its
  Settings screen for private programs, and `VISIBILITY` / `PRIVATE`.
- The `private` extra installs `keyring`.
- 34 new tests; each new guard was broken on purpose and watched go red (13
  breaks, 13 failures).

### ms-desktop-app 2.4.0

- §1a describes what is built rather than what is planned: *Using it* (the
  extra, `_private.py`, `secrets.get`, **Sign out**, hidden imports, the CI
  variable), the checks and where each one lives, and a `release.yml` fragment
  for a private release — feed written last, an anonymous download proved
  refused, the published files checked against `SHA256SUMS`.
- The offline notice lives in the footer on every screen, and a clock set back
  ends the grace period rather than extending it.

## 2026-09-28

### ms-desktop-app 2.3.0

A program can now be **private** as well as public. The people who run a
private program sign in with their machinesaver.net Google account before it
opens; its downloads, updates and the credentials it uses are only reachable
after that sign-in. Public programs, including the Espec burn-in program, work
exactly as before.

- New §1a, *Public or private*: what each one means, what private promises and
  what it does not, sign-in through the system browser (whole machinesaver.net
  domain, Internal consent screen, `hd` checked), a 14-day offline grace period
  that ends at once if Google says the account is suspended, releases in a
  domain-only Cloud Storage bucket, credentials in Secret Manager instead of a
  tracked `.env`, **Email it to support** in place of a GitHub issue, and a
  release workflow that must prove an anonymous download is *refused*.
- §3 asks it as question 6, before anything is written.
- The register gains **Sign in with Google**, **Sign out** and **Email it to
  support**, using marks the kit already holds.
- The kit implements private programs from 1.3.0. Until then every program is
  public.

### ms-appkit 1.2.0

Nothing changes on screen in this version.

- `ms_appkit.update.channel` — where releases come from, behind one small
  interface: the feed address and headers, how the answer is read, the headers
  a download needs, the release page, and what to call the host in a sentence.
  `GitHubReleases` is the only channel and behaves exactly as the code it
  replaced; the private channel in 1.3.0 plugs in here.
- The checker, the downloader, the checksum fetch, the footer and the window
  now ask the channel instead of naming GitHub. An error on a host that is not
  GitHub will no longer blame GitHub's hourly limit.
- `CheckOutcome.reached` — whether the host answered. `reached_github` stays as
  a name for existing callers.
- Five new tests, each proved to fail against its own violation: a public
  program's channel is the GitHub feed it always was; the feed is read by the
  channel; every download and checksum request carries the channel's headers
  (where a private host's token will go); an error names the host it was
  talking to; and no update code outside `channel.py` names GitHub.

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
