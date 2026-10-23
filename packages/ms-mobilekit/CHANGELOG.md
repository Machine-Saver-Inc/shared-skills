# Changelog — ms-mobilekit

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
