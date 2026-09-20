---
name: "ms-desktop-app"
description: "Scaffold, build, release and maintain any Machine Saver desktop application — the shared shell every one of them honours (footer, navigation, Lucide icons, the button register, report a problem, check for updates), the repo and CI/CD layout, versioning discipline, and the lessons already paid for. Use when creating a new Machine Saver desktop tool or working on an existing one."
---

# Machine Saver desktop applications

**Skill version 2.1.0.** Published at
`github.com/Machine-Saver-Inc/shared-skills`, alongside **`ms-appkit`** — the
Python package that *is* the shell this skill describes. Read §0 first.

For any tool Machine Saver puts on a colleague's computer: a machine
controller, a printer utility, a gateway provisioner, a data importer, a field
calibration aid. Installed by the person who uses it rather than by IT, and
distributed from a public repo in the `Machine-Saver-Inc` org.

**The user is not a developer.** They double-click an icon, they have never read
anything about the program, and if it fails they need to be told what to do —
not what went wrong.

## The point of this skill

Every Machine Saver desktop tool should feel like the same product family.
Somebody who has used one must already know, without being told, how to report a
problem, see what changed, get the latest version, and find their way around.
That only happens if every app is built from the same shell.

1. **§1 defines the shell** — the parts that must be identical everywhere.
2. **§2 is the button register** — the shared vocabulary, and how to add to it.
3. **§3–§7 scaffold and run the project** — repo, CI/CD, releases, versioning.
4. **§8–§12 carry the lessons** already paid for.

The pattern was worked out on `espec-temperature-cycling`; that is provenance,
not scope. Where a story names that app it illustrates a general point.

**A skill enforces nothing.** It is text in a context window. So the rules that
*can* be machine-checked are functions in `ms_appkit.housekeeping`, called from
a ~40-line `tests/test_house_rules.py` copied from
`packages/ms-appkit/template/`. They fail a build regardless of what anyone
remembers, and because the checks live in the package rather than in each repo,
a lesson learned in one application becomes a gate in all of them at their next
release.

---

## 0. Do not build the shell. Import it.

`ms-appkit`, in `packages/ms-appkit/` of this repository, is the footer, the
navigation helper, the Lucide set, the update check, the problem report, the
action trail and the window they all sit in. §1 and §2 are the contract it
already implements; the rest of this skill is why it is shaped that way and what
is still yours to get right.

```toml
# pyproject.toml
dependencies = [
  "ms-appkit @ git+https://github.com/Machine-Saver-Inc/shared-skills.git#subdirectory=packages/ms-appkit",
]
```

```python
# <app>/app.py — the whole entry point
from ms_appkit.bootstrap import run

def main() -> int:
    from gateway_app.ui.main_window import MainWindow
    return run(name=APP_NAME, repo=GITHUB_REPO, version=__version__,
               slug=SLUG, window=MainWindow, single_instance=True)
```

```python
# <app>/ui/main_window.py — screens, and two hooks
from ms_appkit.shell import AppWindow

class MainWindow(AppWindow):
    def __init__(self) -> None:
        super().__init__(DEFAULTS)
        self.home = HomePage()
        self.HOME = self.add_screen(self.home, "Home")
        self.show_screen(self.HOME)
        self.start_update_check()

    def report_context(self) -> dict[str, str]:
        """Whatever would otherwise be the first question back."""
        return {"Printer": self.printer or "none chosen"}

    def busy(self) -> str | None:
        """Completes "Updates are not offered while …", or None."""
        return "a label is printing" if self.printing else None
```

A runnable example of exactly this — two screens, its own house-rules test — is
`packages/ms-appkit/template/`. Copy it and rename.

**What a new application still writes:** its screens, its driver or client and
the simulator behind it, its `core/`, its packaging, its README. Not a button
helper, not a footer, not an update checker. If you find yourself writing one of
those, you are forking the family.

**If the kit is missing something**, add it to the kit and release the kit.
Never work around it locally — a local workaround is exactly how two of these
tools stop being one family.

---

## 1. The shared shell — identical in every application

This section is the contract `ms-appkit` implements. It is here so a reviewer
can check a screen against it, and so the reasoning survives if the package ever
has to be rebuilt. **Do not reimplement any of it.**

### The window

- Title bar: the application's name and version — `Gateway Provisioner 1.2.0`.
- One stacked set of screens. No MDI, no top-level tabs.
- **A footer bar on every screen**, always present, never scrolled away.

### The footer — the family's signature

```
[🐞 Report a problem]   [MS mark] Created by Machine Saver Inc   Version 1.2.0 · last checked 19 Sep 14:02  [⟳ Check for updates]
```

Three things, in this order, on **every** screen:

1. **Left: "Report a problem"** with the `report` mark (§5).
2. **Middle: the Machine Saver logo and "Created by Machine Saver Inc"**, the
   mark scaled to about 24px — smaller and the bearing balls and flag turn to
   mud. Quiet, secondary text colour; it is a signature, not a banner.
3. **Right: the installed version**, when it last checked, and **"Check for
   updates"**. Always visible, not only on the first screen — somebody three
   screens deep reading the version out over the phone should not have to
   navigate for it.

### Navigation — Back on the LEFT

```
[← Back]                                  [secondary] [secondary] [Forward →]
```

**Back is on the left. The action that moves forward is on the right.** That is
what every other application on the machine does. `ms_appkit.widgets.action_bar`
is the only place it is decided; a screen passes `back=`, `forward=` and
`extras=` and never arranges a row itself. Two tests hold it: one proves the
helper puts its arguments in the right places, one proves no screen passed them
the wrong way round — a correct helper filled backwards by a screen is exactly
how this was reported.

Where a screen has no Back, the action that *leaves* it takes that place —
**Discard** on a result screen, **Stop the run** on a failure screen.

- **Home** carries: the app name, a one-line description, one filled **primary
  action**, then the other destinations as an equal-width column of outlined
  buttons, then a status line about whatever the app connects to.
- A long screen scrolls; it never crushes its own controls.

### Update banner

```
Version 1.3.0 is available.        [What's new]  [Update now]  [Later]
```

Same wording everywhere. **What's new** shows the release body, which is why the
body must lead with the changes (§7).

### Button roles

Three, no more, from **one shared helper** so they cannot drift:

| Role | Looks like | Used for |
| --- | --- | --- |
| primary | filled accent, bold | the one action that moves forward on this screen |
| secondary | outlined, surface background | everything else |
| danger | outlined, red text | stop, cancel a job, anything destructive |

### Where things live on disk

| What | Where |
| --- | --- |
| Results and outputs | `Documents/<App Name>/` |
| Log file | `~/.<app-slug>/<app-slug>.log` |
| Settings | `~/.<app-slug>/settings.json`, via `ms_appkit.settings` |

A settings *file* rather than `QSettings`: it can be read over somebody's
shoulder on a machine with no internet, copied to another machine, and pasted
into a problem report. A registry key cannot.

### Always present

- `--version` on the command line, printing `<App Name> X.Y.Z`.
- A single-instance lock if two copies would contend for anything.
- Settings reachable from Home, holding **every** value the program uses.
- The problem report and the action trail behind it (§5).

---

## 2. Icons and the button register

### The library is Lucide

**All marks come from Lucide** (https://lucide.dev) — the set shadcn/ui is built
on. ISC licensed, ~2,100 icons, drawn on one 24-unit grid, stroked in
`currentColor` so each one tints to the colour of the text beside it.

**They ship with `ms-appkit`** — 59 of them, vendored from `lucide-static`,
with the upstream `LICENSE` and a `SOURCE.md` recording which Lucide file each
one came from. An application vendors nothing and depends on nothing at runtime;
it calls `ms_appkit.icons.icon("back")`.

Adding one is a change to the kit, not to an app:

```sh
npm pack lucide-static          # copy the one file you need
```

into `packages/ms-appkit/src/ms_appkit/resources/icons/`, named for the idea
rather than the drawing, with a line in `SOURCE.md` and a row in the register
below. Strip only the web-only `class` attribute; change nothing else.

**The file name is the name a button asks for, not the Lucide name.**
`icon("back")`, never `icon("arrow-left")`. That indirection is what lets the
mark for an idea change without touching every screen.

Hand-drawn glyphs were tried first on the Espec app. Two shipped illegible at
16px. A maintained set beats anything drawn here in an afternoon.

### The register

**Every button in the family lives in this table.** Same words → same mark →
same role, in every application. The left column is also the vocabulary: say
*Report a problem*, never *Feedback*; *Settings*, never *Preferences*.

| Button | What it does | Mark | Lucide | Role |
| --- | --- | --- | --- | --- |
| **Back** | return to the previous screen | `back` | `arrow-left` | secondary |
| **Continue** | accept this screen and go on | `forward` | `arrow-right` | primary |
| **Cancel** | close without doing anything | `cancel` | `x` | secondary |
| **Discard** | leave without keeping the result | `discard` | `trash-2` | secondary |
| **Settings** | open the settings screen | `settings` | `sliders-horizontal` | secondary |
| **Save** | write the settings and stay | `save` | `check` | primary |
| **Restore defaults** | put every setting back as shipped | `retry` | `rotate-cw` | secondary |
| **Report a problem** | open the report dialog | `report` | `bug` | secondary |
| **Check for updates** | ask GitHub now | `refresh` | `refresh-cw` | secondary |
| **What's new** | show this release's changes | `notes` | `file-text` | secondary |
| **Update now** | download and install the release | `download` | `download` | primary |
| **Later** | dismiss the update banner | `later` | `clock` | secondary |
| **Open GitHub to post it** | open the pre-filled issue | `open` | `external-link` | primary |
| **Copy to clipboard** | put the report on the clipboard | `copy` | `copy` | secondary |
| **Test connection** | prove the thing answers | `connect` | `plug` | primary |
| **Find it for me** | probe every candidate | `search` | `search` | secondary |
| **Check again** | re-scan for devices | `refresh` | `refresh-cw` | secondary |
| **Change port** | go back to device selection | `connect` | `plug` | secondary |
| **Try again** | retry the failed operation | `retry` | `rotate-cw` | primary |
| **Open past results** | open the results folder | `folder` | `folder-open` | secondary |
| **Start …** | begin the app's main job | `start` | `play` | primary |
| **Stop …** | end the job early | `stop` | `circle-stop` | danger |

**Marks vendored and ready for the apps that do not exist yet** — use these
rather than inventing: `printer` (`printer`), `label` (`tag`), `gateway`
(`router`), `wifi`, `network`, `globe`, `barcode` (`qr-code`), `scan`
(`scan-line`), `power`, `usb`, `terminal`, `database`, `import` (`file-input`),
`export` (`file-output`), `upload`, `add` (`plus`), `remove` (`minus`), `edit`
(`pencil`), `filter`, `sort` (`arrow-up-down`), `list`, `table`, `calendar`,
`user`, `lock`, `unlock` (`lock-open`), `key` (`key-round`), `link`,
`disconnect` (`unlink`), `send`, `mail`, `clipboard` (`clipboard-list`),
`chart` (`chart-line`), `gauge`, `info`, `help` (`circle-help`), `warning`
(`triangle-alert`), `alert` (`circle-alert`), `success` (`circle-check`),
`failure` (`circle-x`).

### How to add a button

1. **Search this register first.** If the action already exists — even in a
   different app — reuse its exact words, mark and role. A printer app's
   "Start printing" is the family's **Start …** with `start`.
2. If it is genuinely new, **look for an existing mark** in the vendored set
   before adding one. Fewer marks, each used consistently, beats a large set
   used loosely.
3. If it needs a mark the kit does not hold, add it **to the kit** as above and
   release the kit. Never vendor an icon into an application.
4. **Add a row to this register** — the words, what it does, the mark, the
   Lucide name, the role — in the same change that adds the button. A button
   that is not in the register is how the family drifts.
5. Build it with `ms_appkit.widgets.button` / `primary`. Never construct one by
   hand: the helper is also where a press is recorded for the problem report.

Two tests enforce this: every button must ask for a mark the vendored set
actually holds (one shipped asking for `speed`, vendored as `gauge`, rendering
nothing at all and only logging), and the same label must always carry the same
mark.

---

## 3. Scaffolding a new application

### Ask first, before writing anything

1. What is it called, and what one sentence describes it on Home?
2. Who uses it, and what is the single job they open it to do?
3. What does it talk to — hardware, a network service, files, nothing?
4. Is there a long-running or unattended operation? (§11)
5. Windows only, or Linux too?

### The layout

```
<repo>/
├─ <app_pkg>/
│  ├─ _version.py          the only place a version is written
│  ├─ devices/ | services/ driver, discovery, simulator      (no Qt)
│  ├─ core/                the actual work, state, records    (no Qt)
│  ├─ ui/                  screens only — the shell is ms-appkit
│  └─ resources/icon.png   the application's own launcher icon
├─ tests/test_house_rules.py   copied from the kit's template, day one
├─ tools/                 screenshots.py  release_notes.py
├─ packaging/             <app>.spec  windows/<app>.iss  linux/  release-notes.md
├─ .github/workflows/     ci.yml  release.yml
└─ CHANGELOG.md  README.md  pyproject.toml
```

**Everything except `ui/` must import and run headless, with no hardware.**

### Build in this order

Each step makes the next testable.

1. `_version.py`, `pyproject.toml`, `.gitignore` — and **check the packaging
   spec is not ignored**; GitHub's stock Python `.gitignore` excludes `*.spec`.
2. `tests/test_house_rules.py`, copied and renamed. It will fail; that is fine.
3. `ci.yml`: Linux **and** Windows, across the supported Python range.
4. The **simulator** for whatever the app talks to — before the real driver.
5. The driver or client, tested against the simulator.
6. `core/`, with injectable `clock` and `sleep` so a long job runs in seconds.
7. **`pip install ms-appkit`, then `MainWindow(AppWindow)` with one screen.**
   Before the second screen exists. Retrofitting the shell meant touching eight
   files and a stylesheet at once, and that was when it *was* the shell.
8. The screens, built from `ms_appkit.widgets`.
9. `tools/screenshots.py`, README written around its output.
10. `release.yml`, `packaging/`, `tools/release_notes.py`, first tag.

### The stack

**Always:**

| Concern | Choice | Why |
| --- | --- | --- |
| The shell | **`ms-appkit`** | §0 — never rebuilt per app |
| Language | Python 3.10+ | what the team writes |
| GUI | PySide6-**Essentials** | keep `QtSvg` — it is what tints the icons |
| Bundling | PyInstaller, **onedir** | onefile unpacks ~150 MB to temp every launch |
| Windows installer | Inno Setup, **per-user** | a work machine is locked down |
| Linux (if needed) | `.deb` **and** AppImage | `.deb` for Ubuntu, AppImage elsewhere |
| Certificates | `certifi`, always in `hiddenimports` | §4 |

**Only if needed:** `pyserial` / `minimalmodbus` for serial instruments;
`pyqtgraph` for a live chart of a long series; plain `urllib` rather than
`requests`.

**Trim Qt.** Exclude in the `.spec`: `QtWebEngine*`, `QtQuick*`, `Qt3D*`,
`QtMultimedia*`, `QtCharts`, `QtDataVisualization`, `QtBluetooth`, `QtNfc`,
`QtPositioning`, `QtWebSockets`, `QtWebChannel`, `QtPdf*`, `QtDesigner`,
`QtHelp`, `QtTest`, `QtSql`, plus `matplotlib`, `scipy`, `pandas`, `tkinter`,
`IPython`, `PIL` when unused. Reference: ~209 MB → 39 MB installer.

**Name every function-level import in `hiddenimports`.**

---

## 4. Updating: check, download, install

`ms-appkit` does this. The section is why it is shaped the way it is, and what
an application still has to get right — mainly `busy()`, which is the only thing
the kit cannot know.

Against the GitHub Releases API. A public repo needs no token and no server.

| Platform | Install |
| --- | --- |
| Windows `.exe` | installer `/SILENT /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS`, then quit |
| AppImage | replace the file at `$APPIMAGE` via `os.replace`, keep the exec bit, relaunch |
| `.deb` | show the one `apt` command — **never** seek root |

### Certificates — the most expensive lesson in the family

Reported twice, and the first fix was the second bug.

- The check and the download hit **different hosts**. Windows fills its root
  store **on demand**, so a machine can verify one and fail the other. With the
  bundled certificates wired only into the checker, the user was told a new
  version existed and then told it could not be fetched.
- A **fallback after failure** was still wrong: it ran only after an attempt
  failed, and only when the failure arrived as `ssl.SSLError`.

One context, both stores, no retry:

```python
@lru_cache(maxsize=1)
def trust() -> ssl.SSLContext:
    context = ssl.create_default_context()                   # the machine's roots
    import certifi
    context.load_verify_locations(cafile=certifi.where())    # adds, not replaces
    return context
```

On a reference machine that is 166 roots against the system's 152 — exactly the
hosts that were failing.

### The rest

1. **Compare versions numerically.** `1.9.0` sorts above `1.10.0` as strings.
2. **Never update during work in progress.** Re-offer when it finishes.
3. **A failed check is not "up to date".** Three outcomes: newer, confirmed
   current, could not tell. Startup must not block: log it, show it where asked.
4. **Unverifiable means untrusted.** Mismatch *or* unfetchable `SHA256SUMS`
   means refuse and change nothing.
5. **Explain network failures, do not quote them.** Certificate / timeout / DNS
   / rate-limited, plain sentence first, raw text underneath.
6. **Wire the button to the code.** Leaving it on `webbrowser.open` shipped
   twice.
7. **Always offer "Open the release page"**, so a machine the updater cannot
   serve is one click from the file.

---

## 5. Report a problem

`ms-appkit` does this too; an application supplies `report_context()` and
nothing else. What follows is why.

Everything needed is on the user's screen and nowhere else.

**The dialog:** bug or improvement first (it sets the label), a summary, a
description, a preview, and **Open GitHub to post it** / **Copy to clipboard** /
**Cancel** — all three from the shared helper, or two render as bare words.

**Gather:** version; packaged or from source; OS and architecture; Python and Qt;
the screen; what it is connected to; the app's settings; what it was doing and
the last thing it saw; where outputs go; the last update check; log tail (~25
lines).

**Record what they did.** A ring buffer of screens opened and buttons pressed —
**labels only, never anything typed** — last fifteen into the report, in place of
blank "steps to reproduce". Record in the two places everything already passes
through: the **button helper** and the screen stack's `currentChanged`. Collapse
a repeated press into one line with a count. The next report after this shipped
showed exactly which two buttons led to the fault.

**Name a screen before you add it to the stack.** Adding the first screen makes
it current, which fires the signal that writes the trail; a name recorded
afterwards arrives too late and the first line of every report reads *opened ?*.

**The preview is editable, and what it says is what gets posted.**

**Pitfalls:** redact home paths to `~` (the repo is public); a pre-filled issue
URL over ~6000 chars is refused, so drop the log and always copy the full report
to the clipboard — but never cut the middle out of text a person wrote, send the
title and ask them to paste; never post on the user's behalf; wrap the handler so
gathering context can never stop the report opening; build the state block as one
contiguous Markdown table (a blank line stops GitHub rendering it);
`QIcon(QImage)` yields a null icon silently — go through `QPixmap.fromImage`.

Keep the report builder Qt-free so its output can be asserted in tests.

---

## 6. CI/CD

### `ci.yml` — every push and pull request

Matrix: `ubuntu-latest` and `windows-latest` × the supported Python range.

0. **State `shell: bash` once, in the job's `defaults`.** Windows runners run
   `run:` in PowerShell, where `grep`, heredocs and `|| true` do not exist —
   every bash step fails at once, and the failure looks like the tests.
1. **Qt runtime libraries on Linux** — a bare runner has no `libEGL`:
   `libegl1 libgl1 libxkbcommon-x11-0 libdbus-1-3 libxcb-cursor0 libxcb-icccm4
   libxcb-keysyms1 libxcb-shape0 libxcb-xinerama0 libxkbcommon0`.
2. Install the package.
3. **Packaging inputs are tracked by git** — fail if `git ls-files` does not know
   one.
4. Lint.
5. Tests, `QT_QPA_PLATFORM=offscreen` set **in the workflow**.
6. **Interface tests actually ran** — re-run and fail if they *skipped*.

**Anything a workflow step runs must work on the oldest Python in the matrix.**
A version-consistency check importing `tomllib` failed only the 3.10 jobs; it
was comparing three version strings, and a regex was the right tool anyway.

**Two collection traps, each turning every job red at once:** a POSIX-only
import at module scope (`pty`, `fcntl`, `termios`) makes the module
uncollectable on Windows *before* `skipif` applies — import lazily. And
`import PySide6` succeeds without the Qt libraries; the **first submodule**
import fails, so use `importorskip("PySide6.QtWidgets")`.

### `release.yml` — on a `v*` tag, plus `workflow_dispatch`

1. **Refuse a tag not on `main`** (`git merge-base --is-ancestor`). A timed-out
   push has left a tag on no branch twice.
2. Stamp `_version.py` from the tag.
3. Build. Inno Setup is **not** preinstalled on `windows-latest`
   (`choco install innosetup`); `libfuse2` does not exist under that name on
   Ubuntu 24.04 (`APPIMAGE_EXTRACT_AND_RUN=1`).
4. `sha256sum * > SHA256SUMS`.
5. Compose the body with `tools/release_notes.py` (§7).
6. Publish.
7. **Download the published assets anonymously and verify them.** Uploading is
   not the same as being downloadable.

---

## 7. Versioning and the release page

- **Semantic versioning**, tags `vMAJOR.MINOR.PATCH`. Anything a user would
  notice is a minor; a fix nobody would describe is a patch.
- **`_version.py` is the only place a version is written.**
- **A release is a tag push and nothing else.**
- **Push `main`, confirm it landed, then tag.** Retry a timed-out push rather
  than assuming it failed.
- **Read a CI run to completion before calling it green.** Nothing can check
  this for you.
- **Never pipe a test run into `tail`** — the exit code becomes the pipe's.

### The release page serves two people who want opposite things

A first-time visitor needs the download. Somebody already running the program —
who pressed **What's new**, which shows the release body — needs to know what
changed. Writing the body as the install template handed them a page explaining
how to install what they were already using. Reported as "nonsense", fairly.

**Compose it: what changed first, then how to install.**

- Every `CHANGELOG.md` entry opens with a plain-language summary before the
  first `###`. `tools/release_notes.py` lifts it, adds the download section, and
  links the full changelog.
- Write it for the person who uses the app. No file names, no test names, no
  `CI`. *"Every button now looks like a button — a clear outline, and a small
  picture on the left saying what it does"* is the register.
- A release with nothing visible says so: *"Nothing changes on screen in this
  version."*
- Backfill summaries when introducing this.

---

## 8. Talking to hardware, services and files

**Build a simulator for whatever the app talks to, before the real client is
finished.** Not a mock — something speaking the real protocol with correct
framing, plus a model of how the real thing behaves and fails. A serial
instrument on a pseudo-terminal; a fake HTTP service; a gateway that answers
provisioning commands and sometimes does not. The highest-leverage decision in
the family: the whole program and every failure path built without booking the
hardware.

**Never block the GUI thread on I/O.** `QThread` and signals.

**Remember hardware by a stable identity**, not the slot it appeared in — an
adapter's serial number rather than `COM3`, a device's MAC rather than its
current address. Identify equipment the way the people using it do, and hang
everything else underneath that, never off a free-text label.

**Give them one action that proves it works.** *Test connection* fetching a real
value — `Printer ready, 412 labels left` in green — builds trust; an address does
not. Offer *Find it for me*.

**Errors say what happened, what it means, and what to do**, with the fix as a
button where one exists. For a locally-attached device, usually four kinds:

| Kind | Headline |
| --- | --- |
| busy | *It is being used by another program* |
| missing | *It is no longer there* |
| permission | *This computer will not let the program open it* |
| silent | *It opened, but nothing is answering* |

Name the culprit where the OS allows it. Windows and Linux report the **same
errno** for different situations: Windows opens serial ports exclusively so
access-denied means contention; on Linux it usually means a missing group.

---

## 9. Making it simple to use

**Shape.** A handful of screens, one obvious action each.

**Language.** No jargon on screen. Protocol words — register, slave address,
function code, endpoint, payload — belong on an advanced page and in the log.
Status is a sentence with a colour: *"Writing label 3 of 40"* beats
`STATE: TX_LABEL`.

**Every value is editable, with good defaults.** No thresholds buried as module
constants; gather them into a settings record on day one.

**Do not hard-code the headline number.** Whatever the marquee figure is — hours,
copies, retries — it is a default. Let it be expressed either way round.

**Say plainly what the software is not.** If it drives physical equipment, name
the independent device that is the protective one.

---

## 10. Controls and forms

**A partial stylesheet override destroys the native control.** Setting `padding`
or `border-radius` *without* a border and a background makes Qt discard the whole
native appearance — secondary buttons rendered as bare words for weeks. Style a
control at all, describe every state: default, hover, pressed, focus, disabled.

**A disabled primary is a muted version of its colour, not grey.** Grey reads as
broken; muted reads as *not yet*.

**`QDialogButtonBox` buttons must come from the shared helper too.**

**Name groups; do not box them.** A group is a name on a hairline with its fields
inset beneath. A card with a shadow round every group gives them all the same
weight, which is the opposite of grouping.

**Set out pairs as pairs.** Matched values stacked as rows read as unrelated; as
two columns they can be compared.

**Size every input to its value.** A two-digit number in a window-wide box reads
as free text. Right-align numbers, tabular figures, label against its field.
Show derived figures beside the input that sets them.

### Pulling complexity back out

**Do not ask for what the program can read.** A field asking the user to type
something the program is connected to and could measure is a question it should
answer itself. Removing one deleted a field *and* made the result correct rather
than approximately correct. Look for this first.

**State one fact once.** Four controls expressing `19200 8-N-1` are one fact.
Show the line, put the controls behind a **Change**.

**One remaining value does not earn a disclosure and a heading.**

---

## 11. If the app runs long or unattended

Skip for a tool that finishes in seconds.

**Needs:** sleep inhibition; a single-instance lock; state flushed every sample;
resume on launch; a hard cap on anything that can extend the work indefinitely.

**Write results as they happen.** Stopping early — or losing power — must keep
everything up to that point. The evidence of the fault is usually in the run
that was stopped because of it.

**If the app measures something, never let a measurement become a fact it is
not.** A test that ran out of time is not equipment that ran out of capability.
Record *why* it stopped — reached, stalled, timed out, cancelled — and treat only
a stall as evidence of a limit. Carry a roll-off on when projecting past what was
measured, and label it an estimate.

**Report shape, not just extremes.** Band the data, show time and rate per band,
mark where it ran out of capacity, exclude time spent holding rather than
travelling.

---

## 12. README, screenshots, and how to work on these

**The README describes the current release and shows it.** Download first;
per-platform install steps including *"Windows protected your PC" → More info →
Run anyway*; screenshots; a numbered walkthrough; where outputs go; how to report
a problem; troubleshooting.

**Generate screenshots, do not take them.** `tools/screenshots.py`, offscreen,
identical every release. Give each shot enough height — a scrollbar means the
page is cut off — and seed anything that fills in from use.

**Then look at them.** The highest-yield habit in the family; it has caught
something on every pass: clipped text, labels overlapping because
`deleteLater()` defers (use `setParent(None)` first), an invisible selected list
item, a dark plot on a light background, a form crushing its own controls, two
illegible icons. Look in dark as well as light.

**When an issue arrives:** read the version in the report before diagnosing —
somebody who cannot auto-update keeps reporting from the build they are stuck on.
A fix that only exists in a release the user cannot reach is not delivered.
**Fix the class, not the case**: the bug was one bare `urlopen`; the fix was a
test for bare `urlopen` defaults. Reply where it was raised, at the length the
reporter earned.

**When a new lesson arrives, ask first whether it can be a test.** Adding a
sentence here is the fallback — and **prove the test fails when the rule is
broken**, or it is decoration. Three guards in this family passed against their
own violation until checked that way; §13 names them.

---

## 13. The shared-skills repository

`github.com/Machine-Saver-Inc/shared-skills` holds this skill and the kit:

```
shared-skills/
├─ skills/ms-desktop-app/SKILL.md      this file, versioned in its header
└─ packages/ms-appkit/                 the shell, versioned in pyproject.toml
   ├─ src/ms_appkit/                   identity, style, icons, widgets, footer,
   │                                   shell, update/, diagnostics, trail,
   │                                   housekeeping, bootstrap, settings
   ├─ template/                        a runnable two-screen app to copy
   └─ tests/                           the kit's own
```

**Both carry version numbers and they move together.** A change to the shell is
a change to the kit's version; if it also changes what this file says, bump the
skill too and say so in `CHANGELOG.md`. An application pins the kit by tag when
it needs to be reproducible and follows `main` otherwise.

**Changing the kit means checking the family.** Run the kit's tests, the
template's, and the house-rules suite of every application that depends on it,
before tagging.

**Prove a new guard fails when its rule is broken.** Break the rule, watch the
test go red, put it back. Three guards in this family passed against their own
violation until checked that way: one matched "CI" inside "recipe", one mistook
bullets under a leading heading for the summary it required, and one let a base
button role be satisfied by a sub-role it was supposed to be independent of.

**Clear `__pycache__` before trusting a result after restoring a mutated file.**
A `cp` restore inside the same second leaves a stale `.pyc` that Python keeps
using, and the guard appears to pass against a violation no longer on disk but
still being executed.

---

## What the repository enforces for you

The checks are `ms_appkit.housekeeping`, called from each application's
`tests/test_house_rules.py`. They fail a build, so these are not yours to
remember:

| Rule | Why it exists |
| --- | --- |
| Buttons come from the shared helper | eight files built their own |
| Every button asks for a mark the library holds | two asked for `speed`, vendored as `gauge`, and rendered nothing |
| The same label always carries the same mark | or the vocabulary stops being one |
| Icons come from Lucide, with its licence shipped | hand-drawn ones shipped illegible |
| Back is left and the forward action right — in the helper *and* at every call site | it was the other way round, and a correct helper can still be filled backwards |
| The footer carries the version, the maker and the report button | the version was on one screen only |
| Every screen has a name a report can use | the first line of every report read "opened ?" |
| A styled control sets border and background with its radius | buttons rendered as bare text |
| Each role has hover, pressed and disabled | a role styled only at rest has no pressed look |
| Every icon is legible at its shipped size, in both tints | two shipped as an asterisk and a squiggle |
| No bare `urlopen` default in the update code | the check worked and the download failed |
| One trust context carries both certificate stores | the same bug, twice |
| Every version has a plain-language summary, free of repo jargon | a release page told a user how to install what they were running |
| The release body leads with the changes | same issue, the other half |
| The version has a `CHANGELOG` entry | the body is written from it |
| Every issue in the changelog has a test naming it | a regression should be recognised |
| `--version` works from the command line | someone is on the phone to a machine with no internet |
| CI: bash declared, packaging inputs tracked, Qt libraries present, interface tests must not skip | each cost a release |
| Release: the tag is on `main`; published assets verified | each was a manual step that got missed |

Still yours: read a CI run to completion, never pipe pytest into `tail`, and
look at the screenshots.