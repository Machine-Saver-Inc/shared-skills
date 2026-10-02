# ms-mobilekit

The shell every Machine Saver iPhone/Android application is built from. The
mobile counterpart of `ms-appkit`; read `skills/ms-mobile-app/SKILL.md` first.

npm cannot install a subfolder of a git repository, so an app does not list the
kit as a dependency. It copies `template/tools/fetch_kit.mjs` and sets, in
`package.json`:

```json
"scripts": { "postinstall": "node tools/fetch_kit.mjs" },
"msKit": { "repo": "Machine-Saver-Inc/shared-skills", "ref": "main" }
```

`npm install` then downloads the repo tarball at `ref`, extracts
`packages/ms-mobilekit` into `node_modules/`, and runs `tools/vendor_kit.mjs`,
which copies `src/` into `www/vendor/ms-mobilekit/`. Pin `ref` to a tag for a
reproducible build.

| | |
| --- | --- |
| `src/kit.css` | tokens, the three button roles with every state, shell layout, tab bar, signature, banner |
| `src/kit.js` | `shell`, `screens`, `button/primary/danger`, `actionBar`, `signature`, `banner`, `theme`, `trail`, `icon` |
| `src/report.js` | `openReport`, `buildReport`, `issueUrl`, `mailtoUrl` |
| `src/update.js` | `checkForUpdate`, `compareVersions`, `explainNetworkError` |
| `src/settings.js` | `settings(key, defaults)` with `export()` for reports |
| `src/icons/` | 74 Lucide marks, `LICENSE`, `SOURCE.md`, `marks.json` |
| `housekeeping/` | the checks an app's `tests/house_rules.test.mjs` runs |
| `tools/` | `vendor_kit`, `apply_native`, `ui_gate`, `static`, `release_notes`, `version_check` |
| `template/` | a runnable three-tab app to copy |

Run the kit's tests with `npm test`; run the template's house rules from
`template/` after `npm i`.
