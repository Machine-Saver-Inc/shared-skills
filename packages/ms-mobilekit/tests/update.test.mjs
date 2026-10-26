// The update path, DOM-free: the feed read with its three outcomes, where
// "Update now" goes on each platform, the automatic check's triggers and
// hourly limit, and the Android install with fake plugins — including the
// download that does not match its checksum, which is deleted and refused.
import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { checkForUpdate, installPath, watchForUpdates, installUpdate, feedUrl, describeOutcome, cleanUpDownloads, DOWNLOAD_DIR, MOBILE_RELEASE_STORE, CHECK_EVERY_MS } from '../src/update.js';
import { buildFeed } from '../tools/publish_feed.mjs';
import { mkdtempSync, writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const FEED = {
  schema: 1, slug: 'example-tool', name: 'Example Tool', version: '1.3.0', tag: 'v1.3.0', notes: 'Faster.',
  release_page: 'https://github.com/Machine-Saver-Inc/example-tool/releases/tag/v1.3.0',
  android: { apk: 'https://storage.googleapis.com/machinesaver-mobile-releases/example-tool/v1.3.0/example-tool-1.3.0.apk', sha256: 'ab'.repeat(32), size: 10, store: null },
  ios: { testflight: 'https://testflight.apple.com/join/abc', store: null },
};
const okFetch = (j = FEED) => async () => ({ ok: true, status: 200, json: async () => j });
const failFetch = (status) => async () => ({ ok: false, status, json: async () => ({}) });

test('the feed URL is the store, per slug', () => {
  assert.equal(feedUrl('example-tool'), `${MOBILE_RELEASE_STORE}/example-tool/latest.json`);
  assert.throws(() => feedUrl('Not A Slug'));
});

test('three outcomes: newer, current, could not tell — never "current" on a failure', async () => {
  const newer = await checkForUpdate({ version: '1.2.0', feed: 'x', platform: 'android', fetchFn: okFetch() });
  assert.equal(newer.status, 'newer'); assert.equal(newer.latest, '1.3.0'); assert.equal(newer.install.kind, 'apk');
  const current = await checkForUpdate({ version: '1.3.0', feed: 'x', platform: 'android', fetchFn: okFetch() });
  assert.equal(current.status, 'current');
  const missing = await checkForUpdate({ version: '1.2.0', feed: 'x', fetchFn: failFetch(404) });
  assert.equal(missing.status, 'unknown'); assert.match(missing.reason, /no published version/);
  const dead = await checkForUpdate({ version: '1.2.0', feed: 'x', fetchFn: async () => { throw new TypeError('Failed to fetch'); } });
  assert.equal(dead.status, 'unknown'); assert.match(dead.reason, /No internet/);
  const empty = await checkForUpdate({ version: '1.2.0', feed: 'x', fetchFn: okFetch({ notes: 'x' }) });
  assert.equal(empty.status, 'unknown'); assert.match(empty.reason, /no version/);
  const none = await checkForUpdate({ version: '1.2.0' });
  assert.equal(none.status, 'unknown'); assert.match(none.reason, /no update feed/);
  assert.match(describeOutcome(current, '1.3.0'), /latest version \(1.3.0\)/);
  assert.match(describeOutcome(missing, '1.2.0'), /no published version/);
});

test('where Update now goes, per platform, and what it says when it cannot install', () => {
  assert.equal(installPath(FEED, 'android').kind, 'apk');
  assert.equal(installPath(FEED, 'ios').kind, 'testflight');
  assert.equal(installPath(FEED, 'web').kind, 'page');
  const unsigned = { ...FEED, android: { apk: null, sha256: null, size: null, store: null } };
  const p = installPath(unsigned, 'android');
  assert.equal(p.kind, 'page'); assert.equal(p.url, FEED.release_page); assert.match(p.reason, /No installable Android build/);
  const noSum = installPath({ ...FEED, android: { ...FEED.android, sha256: null } }, 'android');
  assert.equal(noSum.kind, 'page'); assert.match(noSum.reason, /checksum/);
  assert.equal(installPath({ ...FEED, android: { store: 'https://play.google.com/x' } }, 'android').kind, 'store');
  assert.equal(installPath({ ...FEED, ios: { store: 'https://apps.apple.com/x' } }, 'ios').kind, 'store');
  assert.equal(installPath({ ...FEED, ios: {} }, 'ios').kind, 'page');
});

// A fake page: storage, visibility, online state and a Capacitor App plugin whose listener we can fire.
function page() {
  const listeners = {};
  const store = new Map();
  const doc = { visibilityState: 'visible', addEventListener: (e, f) => (listeners['doc:' + e] = f), removeEventListener() {} };
  const win = { navigator: { onLine: true }, addEventListener: (e, f) => (listeners['win:' + e] = f), removeEventListener() {},
    Capacitor: { getPlatform: () => 'android', registerPlugin: (n) => n === 'App' ? { addListener: (e, f) => { listeners['app:' + e] = f; return { remove() {} }; } } : null } };
  const storage = { getItem: (k) => store.has(k) ? store.get(k) : null, setItem: (k, v) => store.set(k, v) };
  return { listeners, doc, win, storage };
}

test('the automatic check: at launch, on foreground, when online; hourly at most; forced from the button', async () => {
  const { listeners, doc, win, storage } = page();
  let t = 1_000_000; const now = () => t;
  let calls = 0; const results = [];
  const fetchFn = async () => { calls++; return { ok: true, status: 200, json: async () => FEED }; };
  const w = watchForUpdates({ version: '1.2.0', feed: 'x', win, doc, storage, now, fetchFn, delayMs: 0, onResult: (r, m) => results.push([r.status, m.forced]) });
  await new Promise(r => setTimeout(r, 5));
  assert.equal(calls, 1, 'checked at launch'); assert.deepEqual(results[0], ['newer', false]);
  await listeners['doc:visibilitychange']();
  await listeners['app:appStateChange']({ isActive: true });
  await listeners['win:online']();
  assert.equal(calls, 1, 'within the hour, no second request');
  t += CHECK_EVERY_MS + 1;
  await listeners['app:appStateChange']({ isActive: true });
  assert.equal(calls, 2, 'after an hour, the foreground return checks again');
  await listeners['app:appStateChange']({ isActive: false });
  assert.equal(calls, 2, 'going to the background does not check');
  await new Promise(r => setTimeout(r, 5));
  win.navigator.onLine = false; t += CHECK_EVERY_MS + 1;
  const skipped = await w.check();
  assert.equal(skipped.status, 'skipped'); assert.equal(calls, 2, 'offline: nothing asked');
  win.navigator.onLine = true;
  const forced = await w.check(true);
  assert.equal(forced.status, 'newer'); assert.equal(calls, 3);
  assert.deepEqual(results[results.length - 1], ['newer', true]);
  const again = await w.check(true);
  assert.equal(calls, 4, 'the button always asks');
  assert.ok(again.status);
  w.stop();
});

test('a failed check does not count as checked, so the next return tries again', async () => {
  const { listeners, doc, win, storage } = page();
  let t = 5_000_000; let calls = 0;
  const w = watchForUpdates({ version: '1.2.0', feed: 'x', win, doc, storage, now: () => t, delayMs: 0, fetchFn: async () => { calls++; throw new TypeError('Failed to fetch'); } });
  await new Promise(r => setTimeout(r, 5));
  assert.equal(calls, 1);
  await listeners['doc:visibilitychange']();
  assert.equal(calls, 2, 'unknown outcome leaves no timestamp');
  w.stop();
});

// Fake Capacitor plugins that behave like Filesystem, FileTransfer and FileOpener on Android.
function plugins(apkBytes, { downloadFails } = {}) {
  const log = []; let files = {};
  const Filesystem = {
    rmdir: async ({ path }) => { log.push(`rmdir ${path}`); for (const k of Object.keys(files)) if (k.startsWith(path + '/')) delete files[k]; },
    mkdir: async ({ path }) => log.push(`mkdir ${path}`),
    getUri: async ({ path }) => ({ uri: `file:///data/user/0/net.machinesaver.example/cache/${path}` }),
    readFile: async ({ path }) => ({ data: Buffer.from(files[path]).toString('base64') }),
  };
  const FileTransfer = {
    addListener: async (ev, fn) => { FileTransfer._fn = fn; return { remove: async () => log.push('listener removed') }; },
    downloadFile: async ({ url, path, progress }) => {
      log.push(`download ${url} -> ${path} progress=${progress}`);
      if (downloadFails) { const e = new Error('Failed to connect to server.'); e.code = 'OS-PLUG-FLTR-0008'; throw e; }
      FileTransfer._fn && FileTransfer._fn({ type: 'download', url, bytes: 5, contentLength: apkBytes.length, lengthComputable: true });
      files[path.split('/cache/')[1]] = apkBytes; return { path };
    },
  };
  const FileOpener = { open: async (o) => log.push(`open ${o.filePath} as ${o.contentType}`) };
  return { Filesystem, FileTransfer, FileOpener, log, files: () => files };
}
const sha = (b) => createHash('sha256').update(b).digest('hex');

test('Android: download with progress, verify, hand to the installer; the file is not deleted under the installer', async () => {
  const apk = Buffer.from('not really an apk but ten bytes long enough');
  const feed = { ...FEED, android: { ...FEED.android, sha256: sha(apk), size: apk.length } };
  const r = await checkForUpdate({ version: '1.2.0', feed: 'x', platform: 'android', fetchFn: okFetch(feed) });
  const p = plugins(apk); const said = [];
  const out = await installUpdate(r, { plugins: p, onStatus: (s) => said.push(s), win: {} });
  assert.equal(out.done, 'handed-over');
  assert.ok(said.some(s => /Downloading version 1.3.0/.test(s)));
  assert.ok(said.some(s => /%/.test(s)), 'progress is shown as a percentage');
  assert.ok(said.some(s => /Checking the download/.test(s)));
  assert.match(said[said.length - 1], /Opening the installer/);
  assert.match(said[said.length - 1], /allow installs from this app/);
  assert.ok(p.log.some(l => l.startsWith(`download ${feed.android.apk} -> file:///`) && /progress=true/.test(l)));
  assert.ok(p.log.some(l => /open file:.*\.apk as application\/vnd\.android\.package-archive/.test(l)));
  assert.equal(Object.keys(p.files()).length, 1, 'the APK is still there for the installer to read');
  assert.ok(p.log.includes('listener removed'));
  // the next launch empties the folder
  assert.equal(await cleanUpDownloads({}, p), true);
  assert.equal(Object.keys(p.files()).length, 0);
  assert.ok(p.log.includes(`rmdir ${DOWNLOAD_DIR}`));
});

test('Android: a download that does not match the published checksum is deleted and refused', async () => {
  const apk = Buffer.from('tampered');
  const r = await checkForUpdate({ version: '1.2.0', feed: 'x', platform: 'android', fetchFn: okFetch(FEED) });   // FEED's sha256 is not this file's
  const p = plugins(apk); const said = [];
  const out = await installUpdate(r, { plugins: p, onStatus: (s) => said.push(s), win: {} });
  assert.equal(out.done, 'refused'); assert.equal(out.reason, 'checksum');
  assert.match(said[said.length - 1], /did not match its checksum and was deleted. Nothing was installed/);
  assert.ok(!p.log.some(l => l.startsWith('open ')), 'the installer never saw it');
  assert.equal(Object.keys(p.files()).length, 0);
});

test('Android: a failed download is explained and leaves nothing behind', async () => {
  const r = await checkForUpdate({ version: '1.2.0', feed: 'x', platform: 'android', fetchFn: okFetch(FEED) });
  const p = plugins(Buffer.from('x'), { downloadFails: true }); const said = [];
  const out = await installUpdate(r, { plugins: p, onStatus: (s) => said.push(s), win: {} });
  assert.equal(out.done, 'failed');
  assert.match(said[said.length - 1], /could not reach the release store. Nothing was installed/);
});

test('Android without the plugins (a browser) and an unsigned release fall back to the release page, and say so', async () => {
  const r = await checkForUpdate({ version: '1.2.0', feed: 'x', platform: 'android', fetchFn: okFetch(FEED) });
  const opened = []; const said = [];
  await installUpdate(r, { plugins: { Filesystem: null, FileTransfer: null, FileOpener: null }, onStatus: (s) => said.push(s), win: { open: (u) => opened.push(u) } });
  assert.deepEqual(opened, [FEED.release_page]); assert.match(said[0], /cannot install updates itself/);
  const unsigned = await checkForUpdate({ version: '1.2.0', feed: 'x', platform: 'android', fetchFn: okFetch({ ...FEED, android: { apk: null, sha256: null } }) });
  const opened2 = []; const said2 = [];
  const out = await installUpdate(unsigned, { onStatus: (s) => said2.push(s), open: (u) => opened2.push(u) });
  assert.equal(out.kind, 'page'); assert.deepEqual(opened2, [FEED.release_page]); assert.match(said2[0], /No installable Android build.*release page/);
});

test('iPhone: Update now opens TestFlight (or the App Store) and says so; web opens the release page', async () => {
  const ios = await checkForUpdate({ version: '1.2.0', feed: 'x', platform: 'ios', fetchFn: okFetch(FEED) });
  const opened = []; const said = [];
  const out = await installUpdate(ios, { onStatus: (s) => said.push(s), open: (u) => opened.push(u) });
  assert.equal(out.kind, 'testflight'); assert.deepEqual(opened, [FEED.ios.testflight]); assert.match(said[0], /Opening TestFlight/);
  const store = await checkForUpdate({ version: '1.2.0', feed: 'x', platform: 'ios', fetchFn: okFetch({ ...FEED, ios: { store: 'https://apps.apple.com/x' } }) });
  const said2 = []; await installUpdate(store, { onStatus: (s) => said2.push(s), open: () => {} });
  assert.match(said2[0], /Opening the App Store/);
  const web = await checkForUpdate({ version: '1.2.0', feed: 'x', platform: 'web', fetchFn: okFetch(FEED) });
  const opened3 = []; const out3 = await installUpdate(web, { onStatus: () => {}, open: (u) => opened3.push(u) });
  assert.equal(out3.kind, 'page'); assert.deepEqual(opened3, [FEED.release_page]);
});

test('publish_feed builds the feed from the app files, listing the APK only when it is signed and summed', () => {
  const root = mkdtempSync(join(tmpdir(), 'ms-feed-'));
  try {
    mkdirSync(join(root, 'www/js'), { recursive: true }); mkdirSync(join(root, 'dist'));
    writeFileSync(join(root, 'www/js/version.js'), "export const VERSION = '1.3.0';\n");
    writeFileSync(join(root, 'package.json'), JSON.stringify({ name: 'x', repository: { url: 'https://github.com/Machine-Saver-Inc/example-tool.git' }, msStores: { testflight: 'https://testflight.apple.com/join/abc' } }));
    writeFileSync(join(root, 'ms-app.json'), JSON.stringify({ slug: 'example-tool', name: 'Example Tool' }));
    writeFileSync(join(root, 'CHANGELOG.md'), '# Changelog\n\n## [1.3.0] — 2026-10-23\n\nFaster, and it updates itself.\n\n## [1.2.0]\n\nOld.\n');
    const apk = Buffer.from('apk bytes'); writeFileSync(join(root, 'dist/example-tool-1.3.0.apk'), apk);
    writeFileSync(join(root, 'dist/app-release.aab'), 'aab');
    writeFileSync(join(root, 'dist/SHA256SUMS'), `${sha(apk)}  example-tool-1.3.0.apk\n${sha(Buffer.from('aab'))}  app-release.aab\n`);
    const base = 'https://storage.googleapis.com/machinesaver-mobile-releases/example-tool/v1.3.0';
    const f = buildFeed({ root, base, now: new Date('2026-10-23T12:00:00Z') });
    assert.equal(f.version, '1.3.0'); assert.equal(f.tag, 'v1.3.0'); assert.equal(f.slug, 'example-tool'); assert.equal(f.name, 'Example Tool');
    assert.equal(f.notes, 'Faster, and it updates itself.');
    assert.equal(f.release_page, 'https://github.com/Machine-Saver-Inc/example-tool/releases/tag/v1.3.0');
    assert.deepEqual(f.android, { apk: `${base}/example-tool-1.3.0.apk`, sha256: sha(apk), size: apk.length, store: null });
    assert.deepEqual(f.ios, { testflight: 'https://testflight.apple.com/join/abc', store: null });
    assert.equal(installPath(f, 'android').kind, 'apk', 'what the tool writes is what the phone installs from');
    // unsigned build: no install link
    rmSync(join(root, 'dist/example-tool-1.3.0.apk')); writeFileSync(join(root, 'dist/app-release-unsigned.apk'), apk);
    const u = buildFeed({ root, base });
    assert.equal(u.android.apk, null); assert.equal(installPath(u, 'android').kind, 'page');
  } finally { rmSync(root, { recursive: true, force: true }); }
});
