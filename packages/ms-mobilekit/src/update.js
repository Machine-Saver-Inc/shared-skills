// Updates. A phone cannot install a build itself; the store does. So the kit
// does the two things it can: find out whether a newer version exists, and
// take the user to where it is. Three outcomes, never "up to date" on failure.
//
//   checkForUpdate({ version, source: 'https://github.com/Machine-Saver-Inc/<repo>', store: { ios: 'https://apps.apple.com/...', android: 'https://play.google.com/...' } })
//   → { status: 'newer' | 'current' | 'unknown', latest?, notes?, url, reason? }

export function compareVersions(a, b) {
  const pa = String(a).replace(/^v/, '').split('.').map(n => parseInt(n, 10) || 0);
  const pb = String(b).replace(/^v/, '').split('.').map(n => parseInt(n, 10) || 0);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) { const d = (pa[i] || 0) - (pb[i] || 0); if (d) return d > 0 ? 1 : -1; }
  return 0;
}

export function explainNetworkError(e) {
  const m = String(e && e.message || e);
  if (/abort|timeout/i.test(m)) return 'The update server took too long to answer.';
  if (/cert|ssl|tls/i.test(m)) return 'This phone could not verify the update server\u2019s certificate.';
  if (/failed to fetch|network|dns|ENOTFOUND/i.test(m)) return 'No internet connection, or the update server could not be reached.';
  if (/403|rate/i.test(m)) return 'The update server is rate-limiting requests; try again in a few minutes.';
  return 'Could not check for updates.';
}

export async function checkForUpdate({ version, source, store = {}, platform = 'web', timeoutMs = 8000 }) {
  const url = pickStore(store, platform) || `${source}/releases/latest`;
  try {
    const api = source.replace('https://github.com/', 'https://api.github.com/repos/') + '/releases/latest';
    const r = await fetch(api, { signal: AbortSignal.timeout(timeoutMs), headers: { Accept: 'application/vnd.github+json' } });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    const latest = String(j.tag_name || '').replace(/^v/, '');
    if (!latest) return { status: 'unknown', url, reason: 'The release page had no version on it.' };
    const cmp = compareVersions(latest, version);
    return { status: cmp > 0 ? 'newer' : 'current', latest, notes: j.body || '', url, releaseUrl: j.html_url };
  } catch (e) {
    return { status: 'unknown', url, reason: explainNetworkError(e), raw: String(e && e.message || e) };
  }
}

export function pickStore(store, platform) {
  if (platform === 'ios' && store.ios) return store.ios;
  if (platform === 'android' && store.android) return store.android;
  return store.web || null;
}
