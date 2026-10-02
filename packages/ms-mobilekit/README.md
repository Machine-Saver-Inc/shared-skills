# ms-mobilekit

The shell every Machine Saver iPhone/Android application is built from. The
mobile counterpart of `ms-appkit`; read `skills/ms-mobile-app/SKILL.md` first.

```
npm i git+https://github.com/Machine-Saver-Inc/shared-skills.git#subdirectory=packages/ms-mobilekit
```

`postinstall` → `tools/vendor_kit.mjs` copies `src/` into `www/vendor/ms-mobilekit/`.

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
