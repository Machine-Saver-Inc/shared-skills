// ms-mobilekit housekeeping — the rules a machine can check, as functions that
// fail an application's build. An app's tests/house_rules.test.mjs calls
// runAll(root) and asserts the list is empty. Each check returns [] or a list of
// plain-language failures. Each one exists because it was missed once.

import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { join, extname } from 'node:path';
import { marks, lucide } from '../src/icons.js';

const read = (p) => readFileSync(p, 'utf8');
const ex = (p) => existsSync(p);
function walk(dir, exts, out = []) {
  if (!ex(dir)) return out;
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (n === 'vendor' || n === 'node_modules') continue;
    if (statSync(p).isDirectory()) walk(p, exts, out); else if (exts.includes(extname(n))) out.push(p);
  }
  return out;
}
function versionOf(root) {
  const m = read(join(root, 'www/js/version.js')).match(/VERSION\s*=\s*['"]([^'"]+)['"]/);
  return m ? m[1] : null;
}

// ---- 1. one version, written once, everyone agrees ----
export function checkVersion(root) {
  const errs = [];
  const v = versionOf(root);
  if (!v) return ['www/js/version.js must export VERSION — it is the only place a version is written'];
  if (!/^\d+\.\d+\.\d+$/.test(v)) errs.push(`VERSION "${v}" is not MAJOR.MINOR.PATCH`);
  const pkg = JSON.parse(read(join(root, 'package.json')));
  if (pkg.version !== v) errs.push(`package.json version ${pkg.version} differs from version.js ${v}`);
  const cfg = JSON.parse(read(join(root, 'capacitor.config.json')));
  if (!/^net\.machinesaver\./.test(cfg.appId)) errs.push(`capacitor appId "${cfg.appId}" must start with net.machinesaver.`);
  if (!cfg.appName) errs.push('capacitor.config.json needs appName');
  return errs;
}

// ---- 2. the changelog has this version, with a summary a user can read ----
export function checkChangelog(root) {
  const v = versionOf(root); const log = read(join(root, 'CHANGELOG.md'));
  const i = log.indexOf(`## [${v}]`);
  if (i < 0) return [`CHANGELOG.md has no entry "## [${v}]"`];
  const lines = log.slice(i).split('\n').slice(1);
  const h = lines.findIndex(l => /^###/.test(l));
  const summary = lines.slice(0, h < 0 ? lines.length : h).join(' ').trim();
  const errs = [];
  if (summary.length < 20) errs.push(`CHANGELOG entry for ${v} must open with a plain-language summary before the first ###`);
  if (/\b(CI|workflow|pytest|\.mjs|\.cjs|\.js|refactor|lint)\b/.test(summary)) errs.push(`CHANGELOG summary for ${v} contains repo jargon; write it for the person using the app`);
  return errs;
}

// ---- 3. every button comes from the helper vocabulary: has a mark the kit holds, same label → same mark ----
export function checkButtons(root) {
  const errs = []; const byLabel = new Map();
  for (const f of walk(join(root, 'www'), ['.html'])) {
    const html = read(f);
    const re = /<button\b([^>]*)>([\s\S]*?)<\/button>/g; let m;
    while ((m = re.exec(html))) {
      const attrs = m[1]; const label = m[2].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
      const isBtn = /class="[^"]*\b(btn|ms-tab)\b/.test(attrs);
      if (!isBtn) { errs.push(`${f}: <button> "${label}" is not built from the helper (needs class "btn" or "ms-tab")`); continue; }
      const mark = (attrs.match(/data-mark="([^"]*)"/) || [])[1];
      if (mark === undefined) { errs.push(`${f}: button "${label}" has no data-mark`); continue; }
      if (mark && !marks.includes(mark)) errs.push(`${f}: button "${label}" asks for mark "${mark}", which the kit does not hold`);
      if (/class="[^"]*\bbtn\b/.test(attrs) && /class="[^"]*\b(primary|danger)\b/.test(attrs) === false && /data-role="(primary|danger)"/.test(attrs)) errs.push(`${f}: button "${label}" declares a role it does not style`);
      const key = label.toLowerCase();
      if (byLabel.has(key) && byLabel.get(key) !== mark) errs.push(`label "${label}" carries mark "${mark}" here and "${byLabel.get(key)}" elsewhere — one label, one mark`);
      byLabel.set(key, mark);
    }
  }
  for (const f of walk(join(root, 'www/js'), ['.js'])) {
    const js = read(f);
    for (const mm of js.matchAll(/mark:\s*['"]([^'"]+)['"]/g)) if (!marks.includes(mm[1])) errs.push(`${f}: asks for mark "${mm[1]}", which the kit does not hold`);
  }
  return errs;
}

// ---- 4. every screen has a name a report can use; the shell parts are present ----
export function checkShell(root) {
  const errs = []; const html = read(join(root, 'www/index.html'));
  if (!/class="[^"]*ms-screen/.test(html)) errs.push('index.html has no .ms-screen screens');
  for (const m of html.matchAll(/<section\b([^>]*)class="[^"]*ms-screen[^"]*"([^>]*)>/g)) {
    if (!/data-screen="[^"]+"/.test(m[1] + m[2])) errs.push('a .ms-screen has no data-screen name — the first line of every report would read "opened ?"');
  }
  if (!/nav class="ms-tabs"/.test(html)) errs.push('index.html has no tab bar (nav.ms-tabs) — it is how every screen reaches Home and More');
  if (!/data-ms-signature|signature\(/.test(html + walk(join(root, 'www/js'), ['.js']).map(read).join(''))) errs.push('no signature (Report a problem · Created by Machine Saver · version) — the family\'s footer is missing');
  const js = walk(join(root, 'www/js'), ['.js']).map(read).join('');
  if (!/data-ms-version|appVersion/.test(html) && !/signature\(/.test(js)) errs.push('the version is not shown on screen');
  if (!/viewport-fit=cover/.test(html)) errs.push('viewport meta must include viewport-fit=cover (safe areas)');
  if (!/prefers-color-scheme|data-theme/.test(html + (ex(join(root, 'www/vendor/ms-mobilekit/kit.css')) ? 'data-theme' : ''))) errs.push('no dark/light handling');
  return errs;
}

// ---- 5. icons are the kit's, with their licence shipped ----
export function checkIcons(root) {
  const errs = [];
  const v = join(root, 'www/vendor/ms-mobilekit');
  if (!ex(v)) return ['www/vendor/ms-mobilekit is missing — run tools/vendor_kit.mjs; the app must ship the kit, not reference it'];
  if (!ex(join(v, 'icons/LICENSE'))) errs.push('icons/LICENSE (Lucide, ISC) must ship with the app');
  if (!ex(join(v, 'icons/SOURCE.md'))) errs.push('icons/SOURCE.md must ship with the app');
  for (const f of walk(join(root, 'www/assets'), ['.svg'])) {
    const s = read(f);
    if (/lucide/i.test(s) && !/brand/.test(f)) errs.push(`${f}: a Lucide icon vendored into the app — icons come from the kit`);
  }
  return errs;
}

// ---- 6. native declarations: every capability the app uses has a usage string a user can read ----
export function checkNative(root) {
  const p = join(root, 'native.json');
  if (!ex(p)) return ['native.json is missing — declare the capabilities (nfc, camera, bluetooth, location…) with their usage strings'];
  const n = JSON.parse(read(p)); const errs = [];
  for (const [cap, cfg] of Object.entries(n.capabilities || {})) {
    if (!cfg.usage || cfg.usage.length < 20) errs.push(`native.json: capability "${cap}" needs a usage string the OS shows the user (≥20 chars)`);
    if (!cfg.ios && !cfg.android) errs.push(`native.json: capability "${cap}" declares no platform keys`);
  }
  const js = walk(join(root, 'www/js'), ['.js']).map(read).join('\n');
  if (/NDEFReader|CapacitorNfc/.test(js) && !(n.capabilities || {}).nfc) errs.push('the app reads NFC but native.json does not declare the nfc capability');
  if (ex(join(root, 'ios/App/App/Info.plist'))) {
    const plist = read(join(root, 'ios/App/App/Info.plist'));
    for (const [cap, cfg] of Object.entries(n.capabilities || {})) for (const k of (cfg.ios && cfg.ios.plist) || []) if (!plist.includes(`<key>${k}</key>`)) errs.push(`Info.plist lacks ${k} for ${cap} — run tools/apply_native.mjs`);
  }
  if (ex(join(root, 'android/app/src/main/AndroidManifest.xml'))) {
    const man = read(join(root, 'android/app/src/main/AndroidManifest.xml'));
    for (const [cap, cfg] of Object.entries(n.capabilities || {})) for (const perm of (cfg.android && cfg.android.permissions) || []) if (!man.includes(perm)) errs.push(`AndroidManifest.xml lacks ${perm} for ${cap} — run tools/apply_native.mjs`);
  }
  return errs;
}

// ---- 7. no bare fetch: every network call carries a timeout, so a dead network never hangs a screen ----
export function checkNetwork(root) {
  const errs = [];
  for (const f of walk(join(root, 'www/js'), ['.js'])) {
    const js = read(f);
    for (const m of js.matchAll(/\bfetch\(([^)]*)\)/g)) {
      if (/signal/.test(m[1])) continue;
      if (/new URL\([^)]*import\.meta\.url/.test(m[1])) continue; // local asset
      errs.push(`${f}: fetch(${m[1].slice(0, 40)}…) has no AbortSignal — explain network failures, never hang on them`);
    }
  }
  return errs;
}

// ---- 8. CI: bash declared, packaging inputs tracked, UI gate and screenshots present ----
export function checkCI(root) {
  const errs = []; const ci = join(root, '.github/workflows/ci.yml');
  if (!ex(ci)) return ['.github/workflows/ci.yml is missing'];
  const y = read(ci);
  if (!/shell:\s*bash/.test(y)) errs.push('ci.yml must declare shell: bash once in defaults');
  if (!/git ls-files/.test(y)) errs.push('ci.yml must prove the packaging inputs are tracked by git (git ls-files --error-unmatch)');
  if (!/ui_gate|test:ui/.test(y)) errs.push('ci.yml must run the UI gate (tests/ui_gate.cjs)');
  if (!/screenshots/.test(y)) errs.push('ci.yml must generate the screenshots');
  if (!/house_rules|--test|npm test/.test(y)) errs.push('ci.yml must run the house-rules tests');
  const rel = join(root, '.github/workflows/release.yml');
  if (ex(rel)) {
    const r = read(rel);
    if (!/merge-base --is-ancestor/.test(r)) errs.push('release.yml must refuse a tag that is not on main');
    if (!/sha256sum/.test(r)) errs.push('release.yml must write SHA256SUMS');
    if (!/release[_-]notes/.test(r)) errs.push('release.yml must compose the body with tools/release_notes.mjs');
  }
  return errs;
}

// ---- 9. README carries the four header sections every Machine Saver repo has ----
export function checkReadme(root) {
  const r = read(join(root, 'README.md')); const errs = [];
  for (const h of ['## Scope', '## Ownership boundaries', '## Development tracking']) if (!r.includes(h)) errs.push(`README.md lacks "${h}"`);
  if (!/\*\*Owner:\*\*\s*Machine-Saver-Inc/.test(r)) errs.push('README.md Scope must name **Owner:** Machine-Saver-Inc');
  if (!/screenshots\//.test(r)) errs.push('README.md should show the generated screenshots');
  return errs;
}

// ---- 10. the simulator ships: every state the app can show is reachable without hardware ----
export function checkSimulator(root) {
  const html = read(join(root, 'www/index.html'));
  if (!/data-ex=|data-sim=/.test(html)) return ['no worked examples / simulator on screen — every state must be reachable without hardware (SKILL §8)'];
  return [];
}

export const CHECKS = { checkVersion, checkChangelog, checkButtons, checkShell, checkIcons, checkNative, checkNetwork, checkCI, checkReadme, checkSimulator };

export function runAll(root) {
  const out = [];
  for (const [name, fn] of Object.entries(CHECKS)) {
    try { for (const e of fn(root)) out.push(`${name}: ${e}`); }
    catch (e) { out.push(`${name}: could not run — ${e.message}`); }
  }
  return out;
}
