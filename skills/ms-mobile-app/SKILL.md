---
name: "ms-mobile-app"
description: "Scaffold, build, release and maintain any Machine Saver iPhone/Android application — the ms-mobilekit shell every one of them imports (signature footer, tab bar, Lucide icons, the button register, report a problem, update check, settings), the Capacitor repo and CI/CD layout, store accounts and versioning, and the lessons already paid for. Use when creating a new Machine Saver mobile app or working on an existing one."
---

# Machine Saver mobile applications

**Skill version 1.0.0.** Published at `github.com/Machine-Saver-Inc/shared-skills`,
alongside **`ms-mobilekit`** — the JavaScript package that *is* the shell this
skill describes. It is the mobile counterpart of `ms-desktop-app` **2.4.3** and
follows its section numbers, so a reader of one knows where to look in the
other. Read §0 first.

For any app Machine Saver puts on a technician's or customer's phone: a sensor
companion that reads a unit over NFC or BLE, a field commissioning aid, a label
scanner, a site walk-down checklist. Installed from the App Store or Google Play
(or TestFlight / sideload while in test), from a repo in the `Machine-Saver-Inc`
org.

**The user is not a developer, and is probably standing next to a machine.**
One hand, gloves, sunlight, poor signal. They opened the app to do one thing. If
it fails they need to be told what to do — not what went wrong.

## The point of this skill

Every Machine Saver mobile app should feel like the same product family as every
Machine Saver desktop tool. Somebody who has used one must already know, without
being told, how to report a problem, see what changed, get the latest version,
and find their way around.

1. **§1 defines the shell** — same contract as desktop, with the concessions
   named and justified.
2. **§2 is the button register** — the *same* register; marks carry across.
3. **§3–§7 scaffold and run the project** — Capacitor, CI/CD, stores, versioning.
4. **§8–§12 carry the lessons**, including the ones learned on the AirVibe
   Cellular app, which is this skill's provenance, not its scope.

**A skill enforces nothing.** The rules that can be machine-checked are functions
in `ms-mobilekit/housekeeping`, called from a ~10-line
`tests/house_rules.test.mjs` copied from `packages/ms-mobilekit/template/`.
They fail a build regardless of what anyone remembers. Every one of them has been
proved to go red against its own violation.

### How this differs from desktop — the short list

| Desktop rule | Mobile | Why |
| --- | --- | --- |
| Footer on every screen | **Tab bar** on every screen; the signature (Report a problem · Created by Machine Saver · version · Check for updates) lives on **Home** and on **More**, one tap from anywhere | 60 px of footer on a 390 px-wide phone is a quarter of the content; a tab bar *is* the always-present bar, and More is the family's fixed place for the signature |
| Check for updates → download → install | Check → **"Update now" opens the store listing** (or TestFlight) | A phone cannot install a build itself; the store does, and signs it |
| Settings file in `~/.<app>/` | `localStorage` through `ms-mobilekit/settings`, **exported whole into every report** | No user-visible filesystem; the report is where a settings file would have been read over a shoulder |
| Results in `Documents/<App>/` | **Share sheet** (`navigator.share`) and, when native, the Files app via a Capacitor plugin | There is no desktop to find a folder on |
| Log file, log tail in the report | **Action trail + "last thing seen"** in the report; no persistent log | Nothing on a phone reads a log; the trail is what diagnosed the last three reports |
| `--version` on the command line | Version in the signature **and** in the top bar's title on long-press | The phone call "what version are you on" still happens; two taps max |
| Simulator for the hardware | **The same, shipped in the app**: Help → *Status examples* reaches every state without hardware | Testers, support and store reviewers all need to see the screens; a store reviewer has no sensor |
| Python / PySide6 / PyInstaller / Inno | **HTML + ES modules, no framework, in a Capacitor shell**; Android built in CI, iOS archived in Xcode until signing secrets exist | The web app runs unchanged in Chrome on Android for day-one field use; the shell adds Core NFC / BLE / camera |

Everything not in that table is the same rule as desktop.

---

## 0. Do not build the shell. Import it.

```sh
npm i git+https://github.com/Machine-Saver-Inc/shared-skills.git#subdirectory=packages/ms-mobilekit
```

`postinstall` runs `tools/vendor_kit.mjs`, which copies the kit's runtime into
`www/vendor/ms-mobilekit/` so the app ships self-contained (Capacitor copies
`www/` as-is, and there is no bundler to resolve `node_modules` at runtime).

```html
<!-- www/index.html -->
<link rel="stylesheet" href="vendor/ms-mobilekit/kit.css">
<div class="ms-shell"><div class="ms-phone">
  <header class="ms-top">…<button class="btn" data-mark="theme" data-ms-theme>Auto</button></header>
  <main class="ms-main">
    <section class="ms-screen" data-screen="home" data-title="Home">…</section>
  </main>
  <nav class="ms-tabs">
    <button class="ms-tab" data-mark="home" data-go="home">Home</button>
    <button class="ms-tab" data-mark="help" data-go="help">Help</button>
    <button class="ms-tab" data-mark="more" data-go="more">More</button>
  </nav>
</div></div>
<script type="module" src="js/app.js"></script>
```

```js
// www/js/app.js — the whole entry point
import { shell, signature, openReport, checkForUpdate } from '../vendor/ms-mobilekit/index.js';
import { VERSION } from './version.js';
const ms = shell({ app: 'AirVibe Cellular', version: VERSION, home: 'home' });
window.ms = ms;   // the UI gate and screenshot tool drive the app through this
```

Everything below `www/vendor/` is the kit. An application never copies a line of
it; it calls it.

---

## 1. The shared shell — identical in every application

The contract `ms-mobilekit` implements. **Do not reimplement any of it.**

### The frame

- One column, `max-width: 430px`, centred and framed as a phone on a wide screen
  (so the same page is a usable desktop preview and a usable store screenshot).
- A **top bar** on every screen: app name or the current screen's title on the
  left, the theme button on the right. Nothing else; it is not a toolbar.
- `viewport-fit=cover` and safe-area insets on `:root`, the sticky top bar and
  the tab bar. A page that ignores this draws under the notch and the home bar.
- **A tab bar on every screen**, 3–5 tabs, **the last one always *More***.
- Light and dark: tokens on `:root`, redefined under `prefers-color-scheme` and
  under `[data-theme]`. The theme button cycles Auto / Light / Dark and remembers.

### The signature — the family's footer

```
[🐞 Report a problem]  [⟳ Check for updates]
[MS mark] Created by Machine Saver Inc
AirVibe Cellular 1.2.0 · last checked 19 Sep 14:02
```

On **Home** (below the fold is fine) and at the bottom of **More**. Built by
`signature()`; never laid out by hand. Somebody three screens deep reading the
version out over the phone taps More and it is there.

### Navigation — Back on the LEFT

```
[← Back]                                   [secondary]  [Continue →]
```

Same rule as desktop: **Back is left, the forward action is right**, and
`actionBar({ back, forward, extras })` is the only place that is decided. A full
screen's one primary action may instead be a full-width filled button at the
bottom of the content (the thumb zone) — that is still "right". Where a screen
has no Back, the action that leaves it takes that place.

**The OS back gesture / Android back button must do what Back does.** The kit
listens to `popstate`; a screen opened with `screens.go()` is a history entry.

- **Home** carries: the app name, a one-line description, **one filled primary
  action**, the other destinations as equal-width outlined buttons, a status
  line about whatever the app connects to, then the signature.
- A long screen scrolls; it never crushes its controls. Nothing is fixed to the
  bottom except the tab bar.
- **Every tap target is at least 44 × 44 px.** The UI gate measures this.

### Update banner

```
Version 1.3.0 is available.    [What's new]  [Update now]  [Later]
```

Same wording as desktop. **Update now** opens the store listing for this
platform (TestFlight during test); **What's new** shows the release body, which
is why the body must lead with the changes (§7).

### Button roles

Three, from **one shared helper** (`button` / `primary` / `danger`, or
`<button class="btn" data-mark="…">` enhanced at load), each with hover, pressed,
focus and disabled described in `kit.css`:

| Role | Looks like | Used for |
| --- | --- | --- |
| primary | filled accent, dark text | the one action that moves forward on this screen |
| secondary | outlined, surface background | everything else |
| danger | outlined, red text | stop, cancel a job, anything destructive |

The accent pair (`--ms-accent`, `--ms-accent-ink`) is the only token an app
overrides, from its product's brand. AirVibe Cellular: `#FFFF00` on black.
**Accent text on a light panel must pass 4.5:1 or be used as a fill only** —
yellow text on white does not pass; the gate catches it.

### Where things live on the phone

| What | Where |
| --- | --- |
| Settings | `localStorage`, via `settings(key, defaults)`; `export()` goes into every report |
| Results and outputs | the share sheet (`navigator.share`), or a Files/Documents plugin when native |
| What the app last saw | in memory, handed to the report as `lastSeen` |
| Theme | `localStorage` `ms-theme` |

### Always present

- The version on screen (signature) — and the kit shows `<App> X.Y.Z` on a
  long-press of the top bar title.
- Settings reachable from More, holding **every** value the program uses.
- The problem report and the action trail behind it (§5).
- **Status examples** in Help: every state the app can show, reachable with no
  hardware (§8).

---

## 2. Icons and the button register

### The library is Lucide — the same one

The kit vendors **74 marks** from `lucide-static` 1.50.0: the desktop kit's 59,
so every word in the desktop register carries its mark unchanged, plus the
mobile set: `home`, `nfc`, `sound`, `play`, `share`, `camera`, `bluetooth`,
`more`, `phone`, `magnet`, `battery`, `signal`, `location`, `store`, `theme`.
`icons/LICENSE` (ISC) and `icons/SOURCE.md` ship inside `www/vendor/`.

**The file name is the name a button asks for, not the Lucide name.**
`data-mark="back"`, never `arrow-left`. Adding a mark is a change to the kit.

### The register

**The desktop register applies in full** — same words, same mark, same role
(`ms-desktop-app` §2). Rows that are mobile-specific or re-stated here:

| Button | What it does | Mark | Lucide | Role |
| --- | --- | --- | --- | --- |
| **Home** (tab) | the first screen | `home` | `house` | tab |
| **Help** (tab) | status examples + questions | `help` | `circle-help` | tab |
| **More** (tab) | settings, signature, about | `more` | `ellipsis` | tab |
| **Read** / **Scan** (tab) | the app's main sensing job | `nfc` / `scan` / `camera` | | tab |
| **Sounds** (tab) | the device's tone library | `sound` | `volume-2` | tab |
| **Play** | play one tone | `play` | `play` | secondary |
| **Share** | hand the report / result to another app | `share` | `share-2` | secondary |
| **Send by email** | mail the report (private repo) | `mail` | `mail` | primary |
| **Try again** | retry the failed read | `retry` | `rotate-cw` | primary |
| **Read again** | start another read | `nfc` | `nfc` | primary |
| **Open the store** | go to the listing | `store` | `store` | secondary |
| **Auto / Light / Dark** | theme | `theme` | `sun-moon` | secondary |

### How to add a button

Identical to desktop: search the register, reuse the words; look for an
existing mark; add to the kit, never the app; add a row in the same change;
build it with the helper or `class="btn" data-mark`. Two checks hold it: every
button asks for a mark the kit holds, and the same label always carries the same
mark.

---

## 3. Scaffolding a new application

### Ask first

1. Name, and the one sentence on Home.
2. Who holds the phone, and the single job they open it to do.
3. What it talks to — NFC tag, BLE device, camera/QR, a web service, nothing?
4. Does it have to work with no signal? (Usually yes. Design offline-first.)
5. Public repo (GitHub issue reports) or private (email reports)?
6. Which stores, and under which account (§6).

### The layout

```
<repo>/
├─ www/
│  ├─ index.html           screens, each <section class="ms-screen" data-screen="…">
│  ├─ js/version.js        the only place a version is written
│  ├─ js/<domain>.js       the actual work — parsing, rules, state. No DOM.
│  ├─ js/<device>.js       the adapter: native plugin / web API / none
│  ├─ js/app.js            UI wiring only; the shell is the kit
│  ├─ assets/              the app's own art and sounds (never icons)
│  └─ vendor/ms-mobilekit/ written by vendor_kit.mjs; gitignored
├─ native.json             every capability (nfc, camera, …) with its usage string
├─ capacitor.config.json   appId net.machinesaver.<app>, appName
├─ tests/house_rules.test.mjs   copied from the kit's template, day one
├─ tests/<domain>.test.mjs      the work, under Node
├─ tools/screenshots.mjs
├─ .github/workflows/      ci.yml  release.yml
└─ CHANGELOG.md  README.md  package.json
```

**Everything except `app.js` and the adapter must import and run under Node,
with no DOM and no hardware.** That is what makes the hint engine, the parser
and the rules testable in CI.

### Build in this order

1. `version.js`, `package.json`, `capacitor.config.json`, `native.json`,
   `.gitignore` — then `npm i` so the kit vendors.
2. `tests/house_rules.test.mjs`, copied. It fails; fine.
3. `ci.yml` from the template.
4. **The status examples** — the record or state for every situation the app
   will ever show, as data. This is the simulator (§8).
5. The domain module and its tests, driven by those examples.
6. The adapter, with the `none` backend first so the web build works.
7. **The shell with one screen** — before the second screen exists.
8. The screens.
9. `tools/screenshots.mjs`, README written around its output.
10. `release.yml`, store listing (§6), first tag.

### The stack

| Concern | Choice | Why |
| --- | --- | --- |
| The shell | **`ms-mobilekit`** | §0 |
| Language | HTML + ES modules, **no framework, no bundler** | runs unchanged in a browser; nothing to build to test; what the team can read |
| Native shell | **Capacitor 7** | wraps `www/` as-is; one codebase, two stores |
| NFC | `@capgo/capacitor-nfc` (MIT; iOS Core NFC + Android) with Web NFC in Chrome/Android | the two free, maintained paths |
| BLE / camera | Capacitor community plugins, chosen per app and named in `native.json` | |
| Fonts | IBM Plex Sans from Google Fonts **with a real fallback stack** | the kit's face; offline the fallback is fine |
| Tests | `node --test`; Playwright for the gate and screenshots | no test framework to install |
| Android build | Gradle in CI, unsigned AAB; **Play App Signing** signs it | no keystore in the repo, ever |
| iOS build | Xcode archive → TestFlight, locally, until signing secrets exist for a macOS runner | §6 |

---

## 4. Updating: check, and send them to the store

`ms-mobilekit/update` does the part a phone allows. Against the GitHub Releases
API (a public repo needs no token) or, for a private repo, a `version.json` the
app publishes next to its privacy policy on machinesaver.com.

| Platform | "Update now" does |
| --- | --- |
| iOS (store) | opens the App Store listing |
| iOS (TestFlight) | opens the TestFlight link |
| Android | opens the Play listing; a sideloaded test phone gets the release page |
| Web | reloads |

1. **Compare versions numerically.** `compareVersions` — `1.10.0` beats `1.9.0`.
2. **A failed check is not "up to date".** Three outcomes: newer, current,
   could not tell. `explainNetworkError` turns the failure into a sentence.
3. **Every `fetch` carries `AbortSignal.timeout`.** A bare fetch on a phone with
   one bar of signal hangs the screen. The housekeeping check refuses one.
4. **Never check during the job.** Check on Home, after the first idle second.
5. **Always offer "Open the release page"**, so a phone the store cannot serve
   (an MDM-locked work phone) is one tap from the file.

Certificates: not the family's problem on mobile — the OS trust store is used
and is current. Keep the lesson anyway: if a check ever fails with a certificate
error, explain it, do not quote it.

---

## 5. Report a problem

`ms-mobilekit/report` does this; an application supplies `context()` and a
target (`repo` for a public repo, `email` for a private one).

**The dialog:** bug or improvement, a summary, a description, an editable
preview, and **Open GitHub to post it** *or* **Send by email**, plus **Share**
(the OS share sheet, when present), **Copy to clipboard**, **Cancel** — all from
the helper.

**Gather:** app and version; platform (ios / android / web) and device string;
the screen; what it is connected to; the settings record; what it last saw
(the last NFC record, the last BLE packet — truncated to ~1500 chars); the
action trail.

**Record what they did.** The same ring buffer as desktop — screens opened and
buttons pressed, **labels only, never anything typed** — last fifteen into the
report, repeated presses collapsed with a count. Recorded in the two places
everything passes through: the button helper and `screens.go()`.

**Name a screen before you show it.** `data-screen` on every `.ms-screen`, or
the first line of every report reads *opened ?*. Checked.

**Pitfalls carried across:** a pre-filled issue URL over ~6000 chars is refused,
so the kit trims the body and always copies the full report first; the state
block is one contiguous Markdown table; the context gatherer is wrapped so it
can never stop the report opening; never post on the user's behalf.

**Mobile-specific:** a private repo cannot receive a public issue — use
`email`. Serial numbers and ICCIDs are not personal data but *are* identifying;
keep reports going to Machine Saver, not to a public tracker, unless the repo is
deliberately public.

---

## 6. CI/CD and the stores

### `ci.yml` — every push and pull request

Node 20 and 22. 0. **`shell: bash` once, in `defaults`.** 1. `npm ci` (vendors
the kit). 2. **Packaging inputs tracked by git** — `git ls-files --error-unmatch`
on `capacitor.config.json`, `native.json`, `www/index.html`, `www/js/*.js`.
3. Version consistency. 4. House rules and unit tests. 5. Playwright, then the
**UI gate**: seven widths from 360 to 1024 × light and dark; fails on horizontal
scroll, clipped text, contrast under 4.5:1, and any tap target under 44 px.
6. Screenshots, uploaded as an artifact. **Read the run to completion.**

### `release.yml` — on a `v*` tag, plus `workflow_dispatch`

1. **Refuse a tag not on `main`.** 2. Stamp `version.js` and `package.json`
from the tag. 3. `cap add android` if absent, **`apply_native.mjs`** (writes
`native.json` into the manifest), `cap sync`. 4. Build the unsigned AAB and APK.
5. `SHA256SUMS`. 6. Body from `release_notes.mjs` (§7). 7. Publish.
8. **Download the published asset anonymously and verify it.**

iOS archives need a macOS runner and four secrets (`APPLE_CERT_P12`,
`APPLE_CERT_PASSWORD`, `APPLE_PROVISION`, `ASC_API_KEY`). Until they exist:
`npx cap open ios` → Xcode → Signing & Capabilities → add the capability named
in `native.json` → Product → Archive → Distribute → TestFlight. Say so in the
README; do not pretend the workflow does it.

### Store accounts — the expensive lesson in this family

- **Enroll as an organisation, never a personal account.** Google exempts
  organisation accounts from the 12-tester / 14-day closed-testing gate that
  personal accounts created after 13 Nov 2023 must pass. Apple requires a
  D‑U‑N‑S number and verifies signing authority by phoning the reference you
  name — tell that person to expect the call.
- **Use the legal name exactly as D&B has it.** Apple's D‑U‑N‑S lookup returned
  `MACHINE SAVER INC.`; Nelly's records say `Machine Saver, Inc.`; a directory
  said `MachineSaver, Inc.`. Only the D&B form passes verification.
- **Company-owned accounts** (an Apple ID and a Google account on the
  machinesaver.net domain), not a person's. The account outlives the person.
- Budget: Apple approval a day to a week after the call; Play verification a
  few days. Neither is Monday. **Day-one field use is the web app in Chrome on
  Android** (Web NFC works) plus TestFlight internal testing the day Apple
  approves.
- The listing needs a **privacy policy URL** (on machinesaver.com), store
  screenshots (`tools/screenshots.mjs` at 1290×2796 and 1080×1920 — generate,
  do not take), and a "what's new" text — which is the CHANGELOG summary (§7).

---

## 7. Versioning and the release page

- **Semantic versioning**, tags `vMAJOR.MINOR.PATCH`. The store build number is
  the CI run number; it only ever goes up.
- **`www/js/version.js` is the only place a version is written.** The check
  fails if `package.json` or `CHANGELOG.md` disagree.
- **A release is a tag push and nothing else.** Push `main`, confirm it landed,
  then tag.
- **Every `CHANGELOG.md` entry opens with a plain-language summary** before the
  first `###`, written for the person using the app, free of repo jargon. The
  check refuses `CI`, `workflow`, `refactor`, `lint` and file names. That
  summary is also the store's "what's new" and the banner's **What's new**.
- **The release body leads with the changes, then where to get it.**
- Never pipe a test run into `tail`.

---

## 8. Talking to hardware, services and the phone

**Ship the simulator in the app.** On desktop the simulator is a fake device on
a pseudo-terminal; on mobile it is **Help → Status examples**: one button per
situation the app can be in, each driving the real parser and the real hint
engine with a stored record. Testers see every screen without a sensor; store
reviewers can exercise the app; support can say "tap *Weak signal* and compare".
A house-rule check refuses an app with no `data-ex` examples.

**The adapter has three backends and the app never knows which:** `native`
(Capacitor plugin), `web` (the browser API), `none`. One `readOnce()` resolves
to the same shape from all three. Write `none` first so the page works in a
browser from the first commit.

**Ask for a permission at the moment of use, with the reason in the OS prompt.**
`native.json` holds the usage string (≥ 20 characters, checked); nothing is
requested on launch.

**Never block on I/O without a timeout**, and show *what the user should do
while waiting* ("hold the phone still"), not a spinner.

**Remember hardware by its stable identity** — a unit number, a serial — never
by the order it was seen.

**Errors say what happened, what it means, and what to do**, with the fix as a
button. For a tag or device read, usually four kinds:

| Kind | Headline |
| --- | --- |
| nothing there | *Nothing to read here — move the phone slowly over the sticker* |
| wrong thing | *That is a tag, but not one of ours* |
| not allowed | *This phone will not let the app use NFC* (with the Settings deep link) |
| cancelled / timed out | *Scan stopped — open Read again to retry* |

---

## 9. Making it simple to use

Everything in `ms-desktop-app` §9 applies. Additions:

- **One hand.** The primary action sits in the lower half. Nothing important
  lives in the top corners.
- **Gloves and sunlight.** 16 px minimum body text, 44 px targets, 4.5:1
  contrast — the gate enforces all three.
- **Status is a sentence with a colour, and a chip.** *Last check-in failed —
  weak signal* beats `SESSION: FAILED`. Protocol words (RSSI, ICCID, NDEF) go
  behind a fold labelled *Everything the unit reported*.
- **Say what the user will hear and see.** If the device has a buzzer or LED,
  the app carries the tone library and the LED table, and the instructions name
  them ("listen for the join melody; LED off").
- **Teach the vocabulary once.** Introduce each product term (TPM, VSM) with its
  plain name the first time, then use the term.

---

## 10. Controls and forms

`ms-desktop-app` §10 applies. The kit's `kit.css` describes every state for every
control it styles. Two mobile additions:

- **Native inputs, not custom ones.** `<select>`, `<input type=number>`, the OS
  keyboard. Custom pickers break accessibility and the share sheet.
- **One screen, one scroll.** Never nest a scrolling region inside the page
  except for a wide table (`overflow-x: auto` on the table alone).

---

## 11. If the app runs long or unattended

Rare on a phone. If it does (a timed capture, a walk-down): keep the screen on
with a wake-lock plugin, write each result as it arrives to `localStorage`,
resume on relaunch, and put a hard cap on anything open-ended. The desktop
rules on measurements that are not facts apply verbatim.

---

## 12. README, screenshots, and how to work on these

**The README describes the current release and shows it**: the four header
sections every Machine Saver repo carries (Scope / Owner / Ownership
boundaries / Development tracking), what it does with generated screenshots,
running it, building for Android, building for iPhone, the layout, versioning,
reporting a problem.

**Generate screenshots, do not take them.** `tools/screenshots.mjs` drives the
app through `window.ms.screens.go()` and the status examples at 390 × 844 @2×.
Then **look at them**, light and dark.

**When an issue arrives:** read the version and platform in the report first.
**Fix the class, not the case**: a bare `fetch` became a housekeeping check, an
unnamed screen became a check, a Lucide icon copied into an app became a check.

**When a new lesson arrives, ask whether it can be a test**, and prove the test
fails when the rule is broken.

---

## 13. The shared-skills repository

```
shared-skills/
├─ skills/ms-desktop-app/SKILL.md     desktop, 2.4.3
├─ skills/ms-mobile-app/SKILL.md      this file, 1.0.0
├─ packages/ms-appkit/                the desktop shell (Python)
└─ packages/ms-mobilekit/             the mobile shell (JavaScript), 1.0.0
   ├─ src/                            kit.css, kit.js, report.js, update.js, settings.js, icons/
   ├─ housekeeping/index.mjs          the checks
   ├─ tools/                          vendor_kit, apply_native, ui_gate, screenshots helper, release_notes, version_check
   ├─ template/                       a runnable three-tab app to copy
   └─ tests/                          the kit's own
```

**The two kits share the register and the rules, not the code.** A new row in
the desktop register gets its mark vendored into both kits in the same change.
A lesson that applies to both gets a check in both.

---

## What the repository enforces for you

`ms-mobilekit/housekeeping`, called from `tests/house_rules.test.mjs`:

| Rule | Why it exists |
| --- | --- |
| One version, in `version.js`; `package.json` and `CHANGELOG` agree; `appId` is `net.machinesaver.*` | desktop lesson, carried over |
| The changelog entry opens with a summary a user can read, free of repo jargon | a release page told a user how to install what they were running |
| Every button is built from the helper, asks for a mark the kit holds, and one label always carries one mark | one asked for `speed`, vendored as `gauge`, and rendered nothing |
| Every screen has a `data-screen` name | the first line of every report read *opened ?* |
| Tab bar present; signature present; version on screen; safe areas; light/dark | the shell is what makes it one family |
| Icons are the kit's, with the Lucide licence shipped; none copied into the app | two hand-drawn ones shipped illegible |
| `native.json` declares every capability with a usage string; the generated Info.plist / manifest carry it | an NFC read with no usage string crashes on iOS, silently on review |
| No `fetch` without a timeout | a dead network hung the Read screen |
| CI declares bash, proves inputs are tracked, runs the gate and screenshots; release refuses off-`main` tags, writes sums, composes the body | each cost a release |
| README has the four header sections and shows screenshots | the family's repos look alike |
| Status examples ship in the app | every state reachable without hardware |
| UI gate: no horizontal scroll, no clipping, ≥ 4.5:1 contrast, ≥ 44 px targets, 7 widths × 2 themes | gloves, sunlight, review rejections |

Still yours: read a CI run to completion, look at the screenshots, tell the
person Apple will phone.
