// ms-mobilekit — the shell. An app imports this and never rebuilds any of it.
//
//   import { shell, button, actionBar, icon, trail } from 'ms-mobilekit';
//
// No framework, no build step: ES modules served from www/. The kit is loaded
// into www/vendor/ms-mobilekit by `tools/vendor_kit.mjs` so the app ships
// self-contained (Capacitor copies www/ as-is).

import { marks } from './icons.js';

const BASE = new URL('.', import.meta.url);

// ---------- icons: the mark is the name an idea has, never the Lucide drawing ----------
const cache = new Map();
export async function icon(mark) {
  if (!marks.includes(mark)) throw new Error(`icon: "${mark}" is not in the kit (see icons/SOURCE.md)`);
  if (!cache.has(mark)) {
    cache.set(mark, fetch(new URL(`icons/${mark}.svg`, BASE)).then(r => r.text()).then(svg => svg.replace('<svg', '<svg class="ms-icon" aria-hidden="true" focusable="false"')));
  }
  return cache.get(mark);
}

// ---------- the action trail: screens opened and buttons pressed, labels only ----------
const RING = 15;
const _trail = [];
export const trail = {
  push(kind, label) {
    const last = _trail[_trail.length - 1];
    if (last && last.kind === kind && last.label === label) { last.count++; return; }
    _trail.push({ kind, label, count: 1, at: Date.now() });
    if (_trail.length > RING) _trail.shift();
  },
  lines() { return _trail.map(e => `${e.kind} ${e.label}${e.count > 1 ? ` ×${e.count}` : ''}`); },
  clear() { _trail.length = 0; },
};

// ---------- buttons: one helper, three roles; this is where a press is recorded ----------
const ROLES = new Set(['primary', 'secondary', 'danger']);
export function button({ label, mark, role = 'secondary', onClick, block = false, attrs = {} }) {
  if (!ROLES.has(role)) throw new Error(`button: role must be primary|secondary|danger, got ${role}`);
  const b = document.createElement('button');
  b.type = 'button';
  b.className = `btn ${role === 'secondary' ? '' : role}${block ? ' block' : ''}`.trim();
  b.dataset.mark = mark; b.dataset.role = role;
  b.textContent = label;
  for (const [k, v] of Object.entries(attrs)) b.setAttribute(k, v);
  if (mark) icon(mark).then(svg => b.insertAdjacentHTML('afterbegin', svg));
  b.addEventListener('click', (e) => { trail.push('pressed', label); onClick && onClick(e); });
  return b;
}
export const primary = (o) => button({ ...o, role: 'primary' });
export const danger = (o) => button({ ...o, role: 'danger' });

// Enhance buttons written in HTML: <button class="btn" data-mark="back">Back</button>
export function enhance(root = document) {
  root.querySelectorAll('button.btn[data-mark], button.ms-tab[data-mark]').forEach(b => {
    if (b._ms) return; b._ms = 1;
    icon(b.dataset.mark).then(svg => b.insertAdjacentHTML('afterbegin', svg));
    b.addEventListener('click', () => trail.push('pressed', b.textContent.trim()));
  });
}

// ---------- action bar: Back is LEFT, the forward action is RIGHT. Decided here only. ----------
export function actionBar({ back, forward, extras = [] }) {
  const bar = document.createElement('div');
  bar.className = 'ms-actions';
  if (back) { back.classList.add('ms-actions-back'); bar.appendChild(back); }
  for (const x of extras) bar.appendChild(x);
  if (forward) { forward.classList.add('ms-actions-forward'); bar.appendChild(forward); }
  return bar;
}

// ---------- screens: a named stack; opening one writes the trail ----------
export const screens = {
  current: null,
  go(name) {
    const target = document.querySelector(`.ms-screen[data-screen="${name}"]`);
    if (!target) throw new Error(`screens.go: no screen named "${name}"`);
    document.querySelectorAll('.ms-screen').forEach(s => s.classList.toggle('on', s === target));
    document.querySelectorAll('.ms-tab').forEach(t => t.classList.toggle('on', t.dataset.go === name || t.dataset.also === name));
    const prev = this.current; this.current = name;
    trail.push('opened', target.dataset.title || name);
    window.scrollTo({ top: 0 });
    // The OS back gesture / Android back button must do what Back does: each screen is a history entry.
    if (!fromHistory && prev && prev !== name) { try { history.pushState({ ms: name }, ''); } catch (e) {} }
    document.dispatchEvent(new CustomEvent('ms:screen', { detail: { name } }));
  },
};
let fromHistory = false;
if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') window.addEventListener('popstate', (e) => {
  const name = (e.state && e.state.ms) || screens.home || 'home';
  fromHistory = true; try { screens.go(name); } finally { fromHistory = false; }
});

// ---------- signature: the family's footer ----------
export function signature({ app, version, maker = 'Machine Saver Inc', onReport, onCheck, lastChecked }) {
  const el = document.createElement('div');
  el.className = 'ms-signature'; el.dataset.msSignature = '1';
  const row1 = document.createElement('div'); row1.className = 'ms-row';
  row1.appendChild(button({ label: 'Report a problem', mark: 'report', onClick: onReport }));
  if (onCheck) row1.appendChild(button({ label: 'Check for updates', mark: 'refresh', onClick: onCheck }));
  const maker_ = document.createElement('div'); maker_.className = 'ms-maker';
  maker_.innerHTML = `<img src="${new URL('ms-mark.svg', BASE)}" alt=""> <span>Created by ${maker}</span>`;
  const ver = document.createElement('div'); ver.className = 'ms-version';
  ver.textContent = `${app} ${version}` + (lastChecked ? ` · last checked ${lastChecked}` : '');
  el.append(row1, maker_, ver);
  return el;
}

// ---------- update banner: same wording everywhere ----------
export function banner({ version, onWhatsNew, onUpdate, onLater }) {
  const el = document.createElement('div');
  el.className = 'ms-banner on'; el.setAttribute('role', 'status');
  const text = document.createElement('span'); text.textContent = `Version ${version} is available.`;
  el.append(text,
    button({ label: "What's new", mark: 'notes', onClick: onWhatsNew }),
    primary({ label: 'Update now', mark: 'download', onClick: onUpdate }),
    button({ label: 'Later', mark: 'later', onClick: () => { el.remove(); onLater && onLater(); } }));
  return el;
}

// ---------- theme: Auto / Light / Dark, remembered per device ----------
export function theme(btn, key = 'ms-theme') {
  const html = document.documentElement; const order = ['auto', 'light', 'dark']; let cur = 'auto';
  try { cur = localStorage.getItem(key) || 'auto'; } catch (e) {}
  const apply = () => { if (cur === 'auto') html.removeAttribute('data-theme'); else html.setAttribute('data-theme', cur);
    btn.textContent = cur[0].toUpperCase() + cur.slice(1); btn.setAttribute('aria-label', 'Theme: ' + cur); };
  btn.addEventListener('click', () => { cur = order[(order.indexOf(cur) + 1) % 3]; try { localStorage.setItem(key, cur); } catch (e) {} apply(); });
  apply();
}

// ---------- shell: wire the page ----------
export function shell({ app, version, home = 'home' }) {
  document.querySelectorAll('.ms-tab[data-go]').forEach(t => t.addEventListener('click', () => screens.go(t.dataset.go)));
  document.querySelectorAll('[data-go]:not(.ms-tab)').forEach(el => el.addEventListener('click', () => screens.go(el.dataset.go)));
  enhance();
  const t = document.querySelector('[data-ms-theme]'); if (t) theme(t);
  document.querySelectorAll('[data-ms-version]').forEach(el => el.textContent = version);
  document.title = `${app}`;
  screens.home = home;
  try { history.replaceState({ ms: home }, ''); } catch (e) {}
  // Long-press the title: "<App> X.Y.Z" — for the phone call that asks which version.
  const title = document.querySelector('.ms-top .ms-title');
  if (title) { let t; const show = () => { const n = document.createElement('div'); n.className = 'ms-note'; n.style.cssText = 'position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);z-index:9;font-family:var(--ms-mono)'; n.textContent = `${app} ${version}`; document.body.appendChild(n); setTimeout(() => n.remove(), 2500); };
    title.addEventListener('pointerdown', () => { t = setTimeout(show, 600); }); ['pointerup', 'pointerleave', 'pointercancel'].forEach(ev => title.addEventListener(ev, () => clearTimeout(t))); }
  screens.go(home);
  return { app, version, screens, trail };
}

export { marks };
