# Changelog — ms-mobilekit

## [1.5.0] — 2026-11-25

**Sign-in buttons**, for every app that offers single sign-on (airvibe-cellular-mobile-app#19):

- **`mountSignIn(el, { onPick })`** (`src/signin.js`) draws one stack: **Sign in with
  Google**, **Sign in with Apple**, **Sign in with Microsoft**, each with the
  provider's own logo. Light theme is the "Unified Brand" stack, dark theme
  "Sleek Dark" (`.ms-sso` in `kit.css`); in dark the Apple button stays pure
  black, as Apple allows only black or white. `only([...])` hides providers a
  service has not set up; `busy(true)` disables the stack while one opens.
- **House rule 16, `checkSignIn`**: an app that starts a sign-in
  (`/auth/start`) draws the buttons with `mountSignIn`, and no page carries a
  hand-made "Continue with …" or "Sign in with …" button.

## [1.4.0] — 2026-11-24

**Report a problem**, from Leo's TestFlight feedback on build 12:

- **Three kinds:** Bug, Improvement or feature request, Question (was:
  Something is broken, An improvement or question). The report service
  accepts and labels `question` from ms-report-intake #1 on
  (airvibe-cellular-mobile-app#65).
- **Done:** once a report is received, the one button left reads **Done**,
  not Cancel (airvibe-cellular-mobile-app#64).
- **Signed-in email:** `openReport({ reporterEmail })` fills the email in,
  hides the box and says where replies go. Apps pass the address of the
  Google or Microsoft account the person signed in with
  (airvibe-cellular-mobile-app#68).
- **What they did:** numbered in the text itself (a shared or copied report
  showed every step as 1), each step with its time, up to 40 steps (was 15),
  a tab press and the screen it opens counted once, and a line that says
  whether the list is complete (airvibe-cellular-mobile-app#69).

## [1.3.5] — 2026-11-24

**Report a problem**, from the first reports sent on 0.5.7:

- **Your email** is checked in the dialog, by the same rule the service uses.
  When the box is left with an address that is not complete, a sentence says
  so under the box and **Send to Machine Saver** stays off until it is fixed
  or emptied. Before, the report was refused only after Send
  (airvibe-cellular-mobile-app#60).
- When the service refuses a report, the message names what it refused, for
  example "invalid report: email: email does not look like an address",
  instead of only "invalid report".
- **Share** and **Copy to clipboard** carry what the filed report carries: the
  kind, the app and version and the email (which the service turns into
  labels), the whole report, and the names of the attached files. Share also
  attaches the files themselves where the phone allows it. Before, a shared
  report had none of these.
- The Share button's label comes from the form file like every other word.

## [1.3.4] — 2026-11-24

**Report a problem** now waits up to 45 seconds for Machine Saver to
answer before it says the report could not be sent. It waited 10 seconds.
The service needs longer than that when it has been idle, so the app said
"could not be reached" for reports that had in fact arrived. The detail
line added in 1.3.3 showed it on an Android tablet: "native:
SocketTimeoutException timeout", while the report was filed
(airvibe-cellular-mobile-app#44).

## [1.3.3] — 2026-11-24

**Report a problem**: the one-line field is now labelled **Title**, and a
report needs one. **Send to Machine Saver** stays off until the title has
text.

When a report cannot be sent, the message now ends with a short technical
line, "Detail for support: ...", naming what was tried and why it did not
work (the phone's own networking, then the web view, or the code the
service answered with). Until now every failure read the same, so the cause
of a failed send on an iPhone could not be told from the screen
(airvibe-cellular-mobile-app#44).

## [1.3.2] — 2026-11-23

**Report a problem** no longer sends an empty report. **Send to Machine
Saver** stays off until you have written something in the one line or in the
description (airvibe-cellular-mobile-app#43, found on an iPhone in TestFlight).

## [1.3.1] — 2026-11-23

**Report a problem** now reaches Machine Saver from an iPhone or Android
phone. Until now a report sent from the phone app could fail every time with
"Machine Saver could not be reached", whatever was written in it
(airvibe-cellular-mobile-app#44, found on an iPhone 16 in TestFlight).

- The report is sent with the phone's own networking. The kit looked for it in
  a place that only exists in apps built with a bundler; the family's apps have
  none, so the report went out through the web view and the report service,
  which does not answer web pages it does not know, refused it.
- If the phone's networking cannot be used, the kit still tries the web view
  before it says the report was not sent.

## [1.3.0] — 2026-10-26

The app now looks for a newer version by itself: when it opens, whenever you
come back to it, and when the connection returns, at most once an hour and
never when offline. When there is one, the banner appears. On an Android phone
**Update now** downloads the new version, shows the progress, checks the file
against its published checksum and opens the phone's installer, which replaces
the old version and keeps your data; the downloaded file is removed the next
time the app opens. On an iPhone **Update now** opens TestFlight or the App
Store and says so. The **Check for updates** button still asks at once and
answers with one of three sentences: a newer version, the latest version, or
could not tell (and why). Until now the check ran only from the button and, for
a private app, always said it could not tell.

- The version source is the family's mobile release store,
  `https://storage.googleapis.com/machinesaver-mobile-releases/<slug>/latest.json`,
  one small world-readable file per app that the app's `release.yml` writes
  last with `tools/publish_feed.mjs` (version, tag, notes, release page,
  `android.apk` + `sha256` + `size` when the APK is signed, `android.store`,
  `ios.testflight`, `ios.store` from `package.json` `msStores`). The GitHub
  Releases API is gone from the kit: a private repository answers 404 to a
  phone (shared-skills issue 9). Skill §4 says why the store, and why a
  sibling bucket rather than the desktop one.
- `watchForUpdates({ version, feed, onResult })`: launch (after the first idle
  second), `visibilitychange`, Capacitor `appStateChange`, `online`; hourly at
  most through a `localStorage` timestamp that a failed check does not set;
  skipped offline; `check(true)` from the footer button always asks.
  `onResult(result, { forced })` so the app shows the banner on newer and the
  other two sentences only when asked. `describeOutcome` gives the sentence.
- `installUpdate(result, { onStatus })`: Android downloads with
  `@capacitor/file-transfer` into the app's cache (`ms-updates/`), reads the
  file back, compares its SHA-256 with the feed's, and hands it to the system
  installer through `@capacitor-community/file-opener`; a mismatch deletes the
  file and installs nothing; `cleanUpDownloads` empties the folder at every
  launch. iPhone opens TestFlight or the App Store; the web the release page.
  A browser, or a feed with no signed APK, falls back to the release page and
  says why. The plugins are reached through the Capacitor bridge, so the kit
  stays a plain module with no imports of its own.
- `banner()` passes the banner element to `onUpdate` and gives it `say()`, so
  the install's sentences replace the buttons while it runs.
- `tools/publish_feed.mjs` builds `latest.json` from `version.js`,
  `CHANGELOG.md`, `package.json`, `ms-app.json` and `dist/SHA256SUMS`, and
  lists the APK only when it is signed (a file named `unsigned` is skipped).
- Template: `release.yml` signs the APK when `ANDROID_KEYSTORE_BASE64`,
  `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` and `ANDROID_KEY_PASSWORD`
  exist, signs in to Google keylessly (`MS_RELEASE_WIF_PROVIDER`, `MS_RELEASE_SA`),
  uploads the files to the store and the feed last, then reads the feed back
  anonymously and checks the APK against `SHA256SUMS`; `native.json` declares
  the `update` capability with `android.permission.REQUEST_INSTALL_PACKAGES`;
  `package.json` adds the three plugins and `msStores`. Template v3.
- Housekeeping `checkUpdateFeed`: `www/js` calls `watchForUpdates` with
  `feedUrl('<slug>')` for the manifest's slug, calls `installUpdate`, builds
  the signature with `onCheck`, never asks GitHub's API; `native.json`
  declares the install permission; `release.yml` runs `publish_feed`, uploads
  to `machinesaver-mobile-releases` through `google-github-actions/auth` with
  `id-token: write`, files before feed. Proved red then green in
  `tests/housekeeping.test.mjs`.
- `tests/update.test.mjs`: the three outcomes, the install path per platform,
  the automatic check's triggers and hourly limit with a fake page, the
  Android install with fake plugins (progress, checksum mismatch refused and
  deleted, failed download explained, browser fallback), and the feed the tool
  writes being what the phone installs from.

## [1.2.0] — 2026-10-23

Report a problem is now the same form as on a Machine Saver PC program and on
apps.machinesaver.com, and the report goes straight to Machine Saver: paste a
screenshot or attach files, press **Send to Machine Saver**, and the report is
filed for the team with its number shown. No GitHub page and no mail client
open any more; if Machine Saver cannot be reached the whole report is left on
the clipboard with the support address.

- `src/report.js` draws the dialog from `src/report_form.json`, the kit's copy
  of `registry/report-form.json` (every label, hint and sentence; no wording in
  code). File picker, drop zone and paste (`paste-1.png`, `paste-2.png`, …),
  thumbnails, sizes, a remove control; the limits (5 files, 5 MB each, 10 MB,
  by extension) are enforced before anything is sent, with the form's
  `refused_prefix` wording. The collected details (platform, screen, trail,
  last seen, settings) stay as an editable box, appended to the body.
- `sendReport` posts JSON with base64 attachments to `intake_url + /v1/reports`
  with the app's slug; `received_private` / `received_public` by the
  repository's visibility; `failed` with the support address otherwise. Inside
  Capacitor it uses the native `CapacitorHttp` plugin (the intake's CORS is
  for apps.machinesaver.com only); in a browser, `fetch` with a 10 s timeout.
- `shell()` takes `slug` and `visibility` (as in `ms-app.json`) so the kit's
  dialogs know the app; `openReport` reads them from there or from its options.
- `issueUrl` and `mailtoUrl` are gone; `buildReport` returns the title as
  typed and the details separately.
- Housekeeping `checkReportForm`: the vendored `report_form.json` is the kit's
  byte for byte; `www/js` calls neither `issueUrl`/`mailtoUrl` nor builds an
  issue or mailto link, draws no dialog of its own, builds the signature with
  `onReport`, calls `openReport`, and passes the manifest's slug. Proved red
  then green in `tests/housekeeping.test.mjs`. Template v2 carries it.
- `tests/report.test.mjs`: limits refused, paste becomes a file, the JSON
  shape posted, success and failure wording, all with a fake fetch.

## [1.1.1] — 2026-10-22

Nothing changes on screen. `checkCI` now insists on a `schedule:` trigger, as
the desktop kit does, so an app nobody has touched is still found broken by a
kit or runner change before its next release; the checks added in 1.1.0 have
tests of their own (`tests/housekeeping.test.mjs`), each shown to fail on a
broken copy of the template.

## [1.1.0] — 2026-10-22

Nothing changes on screen. The app is now part of a family that can be kept
in step: it says what it was built from, pins the kit to a tag, and its copies
of the kit's files are checked for drift.

- `ms-app.json` in the template and `checkManifest`: slug, name, appId,
  visibility, skill and kit versions agree with the code, and `msKit.ref` is a
  kit tag (`ms-mobilekit/vX.Y.Z`), never `main`.
- `checkSupportEmail`: a report address in `www/js` is the family's,
  `software-support@machinesaver.net`.
- `checkTemplateDrift`: `tests/house_rules.test.mjs` and `ci.yml` carry an
  `ms-mobilekit template vN` marker matching the kit's; the family sweep
  refreshes them. The template's `ci.yml` gains a monthly schedule.
- `tools/check_template.mjs` runs every check over the template, in the
  shared-skills CI.

## [1.0.1] — 2026-10-02

Nothing changes on screen. The first consumer's first three CI runs each failed
on something the template had wrong, and all three are now fixed in the
template so the next app does not inherit them.

- `npm` cannot install a subfolder of a git repository; the pip-style
  `#subdirectory=` line never worked. The template now ships
  `tools/fetch_kit.mjs`, run from `postinstall`, which downloads the
  shared-skills tarball at `msKit.ref` and extracts `packages/ms-mobilekit`
  into `node_modules/`, then vendors it. Pin `ref` to a tag to reproduce a build.
- `ci.yml`: the artifact step used a one-line `{ … }` map containing
  `${{ matrix.node }}`, which YAML parses as a nested map — invalid workflow,
  zero steps run. Expanded to block form.
- `npm ci` requires a lockfile the template does not carry; `npm install`.
- `release.yml`: the download-and-verify step used an anonymous `curl`, which
  cannot reach a private repo's assets. Now `gh release download` with the
  workflow token.

## [1.0.0] — 2026-10-02

First release. Shell (tab bar, signature, action bar with Back on the left,
update banner, theme), the button helper with the action trail, the problem
report with GitHub / email / share targets, the update check that sends the user
to the store, settings, 74 Lucide marks, ten housekeeping checks each proved to
fail against its own violation, the UI gate with touch-target measurement, and a
three-tab template.
