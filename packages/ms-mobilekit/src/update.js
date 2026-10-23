// Updates. The desktop bar is: check at launch and while the program stays
// open, download, verify, install, tidy up. A phone allows most of that, with
// one concession per platform, and this module does exactly as much as each
// allows and says so plainly.
//
// The version source is the family's mobile release store, one small file per
// app that the app's release workflow writes last:
//
//   https://storage.googleapis.com/machinesaver-mobile-releases/<slug>/latest.json
//
//   { "schema": 1, "slug", "name", "version", "tag", "published", "notes",
//     "release_page": "https://github.com/.../releases/tag/vX.Y.Z",
//     "android": { "apk": url|null, "sha256": hex|null, "size": bytes|null, "store": url|null },
//     "ios": { "testflight": url|null, "store": url|null } }
//
// Why the store and not GitHub: an app repository is private, so the Releases
// API answers 404 to a phone, and a token in a phone is a token lost. The feed
// and the APK are world-readable, written keylessly by the release workflow
// through the same Workload Identity provider the desktop store uses. (The
// desktop bucket itself stays private: its installers are for machinesaver.net
// accounts; phones have no such sign-in.)
//
//   checkForUpdate({ version, feed, platform })
//   → { status: 'newer' | 'current' | 'unknown', latest?, notes?, install: { kind, url, sha256?, size? }, url, releaseUrl?, reason? }
//   watchForUpdates({ version, feed, platform, onResult })   automatic: launch, foreground, online; hourly at most
//   installUpdate(result, { onStatus })                      Android: download, verify, hand to the installer; iOS: TestFlight / App Store; web: release page

export const MOBILE_RELEASE_STORE = 'https://storage.googleapis.com/machinesaver-mobile-releases';
export const CHECK_EVERY_MS = 60 * 60 * 1000;
export const DOWNLOAD_DIR = 'ms-updates';   // inside the app's cache; emptied at every launch

export function feedUrl(slug) {
  if (!/^[a-z0-9][a-z0-9-]+$/.test(slug || '')) throw new Error(`feedUrl: "${slug}" is not an app slug`);
  return `${MOBILE_RELEASE_STORE}/${slug}/latest.json`;
}

export function compareVersions(a, b) {
  const pa = String(a).replace(/^v/, '').split('.').map(n => parseInt(n, 10) || 0);
  const pb = String(b).replace(/^v/, '').split('.').map(n => parseInt(n, 10) || 0);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) { const d = (pa[i] || 0) - (pb[i] || 0); if (d) return d > 0 ? 1 : -1; }
  return 0;
}

export function explainNetworkError(e) {
  const m = String(e && e.message || e);
  if (/abort|timeout/i.test(m)) return 'The update server took too long to answer.';
  if (/cert|ssl|tls/i.test(m)) return 'This phone could not verify the update server’s certificate.';
  if (/failed to fetch|network|dns|ENOTFOUND|load failed/i.test(m)) return 'No internet connection, or the update server could not be reached.';
  if (/404/.test(m)) return 'This app has no published version yet.';
  if (/403|rate/i.test(m)) return 'The update server refused the request; try again in a few minutes.';
  return 'Could not check for updates.';
}

// ios | android | web, from the Capacitor bridge when there is one.
export function detectPlatform(win = typeof window !== 'undefined' ? window : null) {
  try { const p = win && win.Capacitor && win.Capacitor.getPlatform && win.Capacitor.getPlatform(); if (p === 'ios' || p === 'android') return p; } catch (e) {}
  return 'web';
}

// Where "Update now" goes on this platform, from the feed. The kind says what
// the button will do, so the sentence shown can be honest about it.
export function installPath(feed, platform) {
  const page = feed.release_page || null;
  const a = feed.android || {}; const i = feed.ios || {};
  if (platform === 'android') {
    if (a.apk && a.sha256) return { kind: 'apk', url: a.apk, sha256: String(a.sha256).toLowerCase(), size: a.size || null };
    if (a.store) return { kind: 'store', url: a.store };
    return { kind: 'page', url: page, reason: a.apk ? 'The published Android build carries no checksum, so it cannot be installed from here.' : 'No installable Android build is published for this version.' };
  }
  if (platform === 'ios') {
    if (i.testflight) return { kind: 'testflight', url: i.testflight };
    if (i.store) return { kind: 'store', url: i.store };
    return { kind: 'page', url: page, reason: 'This version is not on TestFlight or the App Store yet.' };
  }
  return { kind: 'page', url: page };
}

export async function checkForUpdate({ version, feed, platform = detectPlatform(), timeoutMs = 8000, fetchFn } = {}) {
  if (!feed) return { status: 'unknown', url: null, install: { kind: 'page', url: null }, reason: 'This app has no update feed configured.' };
  const f = fetchFn || globalThis.fetch;
  try {
    const r = await f(feed, { signal: AbortSignal.timeout(timeoutMs), cache: 'no-store', headers: { Accept: 'application/json' } });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    const latest = String(j.version || '').replace(/^v/, '');
    const install = installPath(j, platform);
    if (!/^\d+\.\d+\.\d+/.test(latest)) return { status: 'unknown', url: install.url, install, reason: 'The update feed had no version in it.' };
    const cmp = compareVersions(latest, version);
    return { status: cmp > 0 ? 'newer' : 'current', latest, notes: j.notes || '', url: install.url, install, releaseUrl: j.release_page || null, feed: j, platform };
  } catch (e) {
    return { status: 'unknown', url: null, install: { kind: 'page', url: null }, reason: explainNetworkError(e), raw: String(e && e.message || e) };
  }
}

// One sentence for a non-newer outcome, for the footer button's reply.
export function describeOutcome(r, version) {
  if (r.status === 'current') return `You have the latest version (${version}).`;
  if (r.status === 'newer') return `Version ${r.latest} is available.`;
  return r.reason || 'Could not check for updates.';
}

// ---------- the automatic check ----------
// Runs when the app opens, whenever it comes back to the foreground, and when
// the connection returns; never more than once an hour unless forced; never
// while offline. Each outcome goes to onResult(result, { forced }) so the app
// shows the banner on "newer" and, when the person pressed the button, the
// sentence for the other two. Quiet otherwise: nobody wants "you are current"
// every time they switch apps.
export function watchForUpdates({ version, feed, platform = detectPlatform(), every = CHECK_EVERY_MS, key = 'ms-update-checked-at', onResult, win = typeof window !== 'undefined' ? window : null, doc = typeof document !== 'undefined' ? document : null, storage = typeof localStorage !== 'undefined' ? localStorage : null, now = () => Date.now(), fetchFn, delayMs = 1000 } = {}) {
  let busy = null; const handles = [];
  const online = () => !(win && win.navigator && win.navigator.onLine === false);
  const lastAt = () => { try { return Number(storage && storage.getItem(key)) || 0; } catch (e) { return 0; } };
  const stamp = () => { try { storage && storage.setItem(key, String(now())); } catch (e) {} };
  const w = {
    lastChecked: lastAt() || null,
    async check(force = false) {
      if (busy) return busy;
      if (!force) {
        if (!online()) return { status: 'skipped', reason: 'offline' };
        const last = lastAt(); if (last && now() - last < every) return { status: 'skipped', reason: 'checked within the hour' };
      }
      busy = (async () => {
        const r = await checkForUpdate({ version, feed, platform, fetchFn });
        if (r.status !== 'unknown') { stamp(); w.lastChecked = now(); }
        try { onResult && await onResult(r, { forced: force }); } catch (e) {}
        return r;
      })();
      try { return await busy; } finally { busy = null; }
    },
    stop() { for (const off of handles) { try { off(); } catch (e) {} } handles.length = 0; },
  };
  const on = (target, ev, fn) => { if (!target || !target.addEventListener) return; target.addEventListener(ev, fn); handles.push(() => target.removeEventListener(ev, fn)); };
  const soon = () => { if (delayMs === 0) w.check(); else setTimeout(() => w.check(), delayMs); };
  if (doc) on(doc, 'visibilitychange', () => doc.visibilityState === 'visible' ? w.check() : undefined);
  if (win) on(win, 'online', () => w.check());
  // Capacitor: the WebView gets no visibility event when the app returns from the background
  try {
    const C = win && win.Capacitor; const A = C && C.registerPlugin && C.registerPlugin('App');
    if (A && A.addListener) { const h = A.addListener('appStateChange', ({ isActive }) => isActive ? w.check() : undefined); handles.push(() => Promise.resolve(h).then(x => x && x.remove && x.remove())); }
  } catch (e) {}
  cleanUpDownloads(win).catch(() => {});
  soon();   // at launch, after the first idle second
  return w;
}

// ---------- installing ----------
function plugin(win, name) {
  const C = win && win.Capacitor;
  if (!C) return null;
  try { if (C.registerPlugin) return C.registerPlugin(name); } catch (e) {}
  return (C.Plugins && C.Plugins[name]) || null;
}
export function nativePlugins(win = typeof window !== 'undefined' ? window : null) {
  return { Filesystem: plugin(win, 'Filesystem'), FileTransfer: plugin(win, 'FileTransfer'), FileOpener: plugin(win, 'FileOpener') };
}

export async function sha256Hex(bytes) {
  const d = await (globalThis.crypto && globalThis.crypto.subtle).digest('SHA-256', bytes);
  return Array.from(new Uint8Array(d)).map(b => b.toString(16).padStart(2, '0')).join('');
}
function fromBase64(s) {
  const bin = atob(String(s).replace(/\s+/g, ''));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}
const mb = (n) => `${(n / 1048576).toFixed(1)} MB`;

// Yesterday's APK, left when the installer had it or when the person cancelled:
// the next launch (the new version's first) removes the whole folder.
export async function cleanUpDownloads(win = typeof window !== 'undefined' ? window : null, plugins = nativePlugins(win)) {
  const fs = plugins.Filesystem;
  if (!fs || !fs.rmdir) return false;
  try { await fs.rmdir({ path: DOWNLOAD_DIR, directory: 'CACHE', recursive: true }); return true; } catch (e) { return false; }
}

// result: what checkForUpdate returned (status 'newer'). onStatus(sentence) is
// called with each step so the banner can say it; opener(url) opens a page.
export async function installUpdate(result, { platform = result.platform || detectPlatform(), onStatus = () => {}, open = (u) => window.open(u, '_blank'), win = typeof window !== 'undefined' ? window : null, plugins } = {}) {
  const inst = result.install || installPath(result.feed || {}, platform);
  if (inst.kind === 'apk') return installApk(result, inst, { onStatus, win, plugins: plugins || nativePlugins(win) });
  if (inst.kind === 'testflight') { onStatus('Opening TestFlight. Install the update there, then come back.'); if (inst.url) open(inst.url); return { done: 'opened', kind: inst.kind }; }
  if (inst.kind === 'store') { onStatus(platform === 'ios' ? 'Opening the App Store. Install the update there, then come back.' : 'Opening Google Play. Install the update there, then come back.'); if (inst.url) open(inst.url); return { done: 'opened', kind: inst.kind }; }
  if (!inst.url) { onStatus(inst.reason || 'There is nothing to open for this version.'); return { done: 'nothing', kind: inst.kind, reason: inst.reason }; }
  onStatus(inst.reason ? `${inst.reason} Opening the release page instead.` : 'Opening the release page.');
  open(inst.url);
  return { done: 'opened', kind: 'page' };
}

async function installApk(result, inst, { onStatus, win, plugins }) {
  const { Filesystem, FileTransfer, FileOpener } = plugins;
  if (!Filesystem || !FileTransfer || !FileOpener) { onStatus('This build of the app cannot install updates itself. Opening the release page.'); if (result.releaseUrl && win) win.open(result.releaseUrl, '_blank'); return { done: 'nothing', kind: 'apk', reason: 'plugins missing' }; }
  const name = `${(result.feed && result.feed.slug) || 'app'}-${result.latest}.apk`;
  const path = `${DOWNLOAD_DIR}/${name}`;
  let handle = null;
  try {
    await cleanUpDownloads(win, plugins);
    try { await Filesystem.mkdir({ path: DOWNLOAD_DIR, directory: 'CACHE', recursive: true }); } catch (e) {}
    const { uri } = await Filesystem.getUri({ path, directory: 'CACHE' });
    onStatus(`Downloading version ${result.latest}…`);
    if (FileTransfer.addListener) handle = await FileTransfer.addListener('progress', (p) => {
      if (p.contentLength && p.lengthComputable !== false) onStatus(`Downloading version ${result.latest}… ${Math.min(100, Math.round(p.bytes / p.contentLength * 100))}% of ${mb(p.contentLength)}`);
      else onStatus(`Downloading version ${result.latest}… ${mb(p.bytes)}`);
    });
    await FileTransfer.downloadFile({ url: inst.url, path: uri, progress: true });
    onStatus('Checking the download…');
    const { data } = await Filesystem.readFile({ path, directory: 'CACHE' });
    const bytes = typeof data === 'string' ? fromBase64(data) : new Uint8Array(await data.arrayBuffer());
    const sum = await sha256Hex(bytes);
    if (sum !== inst.sha256) {
      await cleanUpDownloads(win, plugins);
      onStatus('The download did not match its checksum and was deleted. Nothing was installed; try again later.');
      return { done: 'refused', kind: 'apk', reason: 'checksum' };
    }
    onStatus('Opening the installer. Confirm there; the app will close and come back as the new version. If the phone asks, allow installs from this app.');
    await FileOpener.open({ filePath: uri, contentType: 'application/vnd.android.package-archive', openWithDefault: true });
    return { done: 'handed-over', kind: 'apk', path: uri };
  } catch (e) {
    await cleanUpDownloads(win, plugins);
    onStatus(`${explainDownloadError(e)} Nothing was installed.`);
    return { done: 'failed', kind: 'apk', reason: String(e && e.message || e) };
  } finally {
    try { handle && handle.remove && await handle.remove(); } catch (e) {}
  }
}

export function explainDownloadError(e) {
  const m = String(e && e.message || e); const code = String(e && e.code || '');
  if (/0008|connect|network|failed to fetch/i.test(m + code)) return 'The download could not reach the release store.';
  if (/0010|HTTP/i.test(m + code)) return 'The release store refused the download.';
  if (/Activity not found|"8"/.test(m + code) || code === '8') return 'This phone has no installer for an app file.';
  if (/space|ENOSPC/i.test(m)) return 'There is not enough room on this phone for the download.';
  return 'The update could not be downloaded.';
}

// Kept for apps written against 1.2: the store link for a platform.
export function pickStore(store, platform) {
  if (platform === 'ios' && store.ios) return store.ios;
  if (platform === 'android' && store.android) return store.android;
  return store.web || null;
}
