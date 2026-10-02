# Changelog — ms-mobilekit

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
