#!/usr/bin/env node
// Writes the app's update feed, latest.json, for the family's mobile release
// store. release.yml runs it after the build files are in dist/ and uploads the
// result LAST, so no phone is ever offered a version whose file is not there.
//
//   node node_modules/ms-mobilekit/tools/publish_feed.mjs --dist dist --base <url of this version's folder> [--apk <file in dist>] [--root <app root>]
//
// Reads www/js/version.js, CHANGELOG.md (the entry is the notes), package.json
// (repository, msStores: { android, ios, testflight }), ms-app.json (slug, name)
// and dist/SHA256SUMS. The Android build is listed only when it is signed: an
// unsigned APK cannot be installed by any phone, and the file name says
// "unsigned" when Gradle produced one. The feed then carries no apk and the app
// offers the release page instead.
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { join, basename } from 'node:path';

export function buildFeed({ root = process.cwd(), dist = 'dist', base, apk, now = new Date() } = {}) {
  const read = (p) => readFileSync(join(root, p), 'utf8');
  const version = read('www/js/version.js').match(/VERSION\s*=\s*['"]([^'"]+)['"]/)[1];
  const pkg = JSON.parse(read('package.json'));
  const manifest = existsSync(join(root, 'ms-app.json')) ? JSON.parse(read('ms-app.json')) : {};
  const log = read('CHANGELOG.md');
  const start = log.indexOf(`## [${version}]`);
  if (start < 0) throw new Error(`CHANGELOG.md has no entry "## [${version}]"`);
  const end = log.indexOf('\n## [', start + 1);
  const notes = log.slice(start, end < 0 ? undefined : end).split('\n').slice(1).join('\n').trim();
  const repoUrl = pkg.repository && pkg.repository.url ? pkg.repository.url.replace(/\.git$/, '').replace(/^git\+/, '') : null;
  const stores = pkg.msStores || {};
  const distDir = join(root, dist);
  const sums = existsSync(join(distDir, 'SHA256SUMS')) ? Object.fromEntries(readFileSync(join(distDir, 'SHA256SUMS'), 'utf8').split('\n').filter(Boolean).map(l => { const [h, ...n] = l.trim().split(/\s+\*?/); return [n.join(' '), h.toLowerCase()]; })) : {};
  let apkName = apk || null;
  if (!apkName && existsSync(distDir)) { const c = readdirSync(distDir).filter(n => n.endsWith('.apk') && !/unsigned/i.test(n)); if (c.length === 1) apkName = c[0]; }
  if (apkName && /unsigned/i.test(apkName)) apkName = null;
  let android = { apk: null, sha256: null, size: null, store: stores.android || null };
  if (apkName) {
    if (!base) throw new Error('--base is needed to publish an APK link');
    if (!sums[apkName]) throw new Error(`${apkName} is not in SHA256SUMS`);
    android = { apk: `${base.replace(/\/$/, '')}/${encodeURIComponent(apkName)}`, sha256: sums[apkName], size: statSync(join(distDir, apkName)).size, store: stores.android || null };
  }
  return {
    schema: 1,
    slug: manifest.slug || pkg.name,
    name: manifest.name || pkg.name,
    version,
    tag: `v${version}`,
    published: now.toISOString(),
    notes,
    release_page: repoUrl ? `${repoUrl}/releases/tag/v${version}` : null,
    android,
    ios: { testflight: stores.testflight || null, store: stores.ios || null },
  };
}

if (process.argv[1] && basename(process.argv[1]) === 'publish_feed.mjs') {
  const arg = (name) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : undefined; };
  try {
    process.stdout.write(JSON.stringify(buildFeed({ root: arg('--root'), dist: arg('--dist'), base: arg('--base'), apk: arg('--apk') }), null, 2) + '\n');
  } catch (e) { console.error(`publish_feed: ${e.message}`); process.exit(1); }
}
