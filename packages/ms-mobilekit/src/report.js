// Report a problem. The app supplies reportContext() and a target; the kit
// gathers everything else from what is already on the screen and in the trail.
//
//   openReport({ app, version, repo: 'Machine-Saver-Inc/airvibe-cellular-app', email: 'support@machinesaver.net',
//                context: () => ({ screen, connected, settings, lastSeen }) })
//
// Public repo  → "Open GitHub to post it" with a pre-filled issue (under ~6000 chars; log dropped).
// Private repo → "Send by email" (mailto) with the same body; GitHub is not offered.
// Always       → "Copy to clipboard" and, where the OS has it, the native share sheet.
// Nothing is ever posted on the user's behalf.

import { trail, button, primary, screens } from './kit.js';

export function buildReport({ app, version, kind = 'bug', summary = '', description = '', context = {}, platform = {} }) {
  const rows = [
    ['App', `${app} ${version}`],
    ['Platform', platform.name || 'unknown'],
    ['Device', platform.device || (typeof navigator !== 'undefined' ? navigator.userAgent : '')],
    ['Screen', context.screen || screens.current || '?'],
    ...Object.entries(context).filter(([k]) => !['screen', 'settings', 'lastSeen'].includes(k)).map(([k, v]) => [k, String(v)]),
  ];
  const table = '| | |\n|---|---|\n' + rows.map(([k, v]) => `| ${k} | ${String(v).replace(/\n/g, ' ').replace(/\|/g, '\\|')} |`).join('\n');
  const steps = trail.lines(); const stepsMd = steps.length ? steps.map(s => `1. ${s}`).join('\n') : '_no actions recorded_';
  const settings = context.settings ? '```json\n' + JSON.stringify(context.settings, null, 1) + '\n```' : '_none_';
  const lastSeen = context.lastSeen ? '```\n' + String(context.lastSeen).slice(0, 1500) + '\n```' : '_none_';
  return {
    title: `[${kind}] ${summary || '(no summary)'}`,
    body: `## What happened\n${description || '(describe what you expected and what you saw)'}\n\n## State\n${table}\n\n## What they did\n${stepsMd}\n\n## Last thing seen\n${lastSeen}\n\n## Settings\n${settings}\n`,
  };
}

export function issueUrl(repo, { title, body }) {
  const base = `https://github.com/${repo}/issues/new?title=${encodeURIComponent(title)}&body=`;
  let b = body;
  while ((base + encodeURIComponent(b)).length > 6000) b = b.slice(0, Math.floor(b.length * 0.8)) + '\n\n_(trimmed — the full report is on the clipboard; paste it here)_';
  return base + encodeURIComponent(b);
}

export function mailtoUrl(email, { title, body }) {
  return `mailto:${email}?subject=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`;
}

export function openReport(opts) {
  const { app, version, repo, email, context = () => ({}), platform = {} } = opts;
  let ctx = {}; try { ctx = context() || {}; } catch (e) { ctx = { contextError: String(e) }; }
  const dlg = document.createElement('dialog'); dlg.className = 'ms-card ms-report'; dlg.style.cssText = 'max-width:430px;width:92vw;border:1px solid var(--ms-line);background:var(--ms-panel);color:var(--ms-ink)';
  dlg.innerHTML = `
    <h2>Report a problem</h2>
    <label class="ms-small ms-muted">What kind of report?
      <select id="ms-kind" style="display:block;min-height:44px;width:100%;margin-top:6px;border-radius:10px;border:1px solid var(--ms-line);background:var(--ms-panel);color:var(--ms-ink);padding:0 10px;font:inherit">
        <option value="bug">Something went wrong</option><option value="improvement">Something could be better</option></select></label>
    <label class="ms-small ms-muted">Summary<input id="ms-summary" style="display:block;min-height:44px;width:100%;margin-top:6px;border-radius:10px;border:1px solid var(--ms-line);background:var(--ms-panel);color:var(--ms-ink);padding:0 10px;font:inherit"></label>
    <label class="ms-small ms-muted">What happened<textarea id="ms-desc" rows="3" style="display:block;width:100%;margin-top:6px;border-radius:10px;border:1px solid var(--ms-line);background:var(--ms-panel);color:var(--ms-ink);padding:10px;font:inherit"></textarea></label>
    <details class="ms-fold"><summary>Preview (editable — what you see is what is sent)</summary><div><textarea id="ms-preview" rows="10" style="width:100%;font-family:var(--ms-mono);font-size:12px;border-radius:10px;border:1px solid var(--ms-line);background:var(--ms-bg);color:var(--ms-ink);padding:10px"></textarea></div></details>
    <div class="ms-row" id="ms-report-actions"></div>`;
  const q = (s) => dlg.querySelector(s);
  const compose = () => buildReport({ app, version, kind: q('#ms-kind').value, summary: q('#ms-summary').value, description: q('#ms-desc').value, context: ctx, platform });
  const refresh = () => { const r = compose(); q('#ms-preview').value = `${r.title}\n\n${r.body}`; };
  ['#ms-kind', '#ms-summary', '#ms-desc'].forEach(s => q(s).addEventListener('input', refresh)); refresh();
  const current = () => { const [title, ...rest] = q('#ms-preview').value.split('\n'); return { title, body: rest.join('\n').trim() }; };
  const copy = async () => { try { await navigator.clipboard.writeText(q('#ms-preview').value); } catch (e) {} };
  const actions = q('#ms-report-actions');
  if (repo) actions.appendChild(primary({ label: 'Open GitHub to post it', mark: 'open', onClick: async () => { await copy(); window.open(issueUrl(repo, current()), '_blank'); } }));
  else if (email) actions.appendChild(primary({ label: 'Send by email', mark: 'mail', onClick: async () => { await copy(); window.location.href = mailtoUrl(email, current()); } }));
  if (typeof navigator !== 'undefined' && navigator.share) actions.appendChild(button({ label: 'Share', mark: 'share', onClick: () => navigator.share({ title: current().title, text: q('#ms-preview').value }).catch(() => {}) }));
  actions.appendChild(button({ label: 'Copy to clipboard', mark: 'copy', onClick: copy }));
  actions.appendChild(button({ label: 'Cancel', mark: 'cancel', onClick: () => dlg.close() }));
  document.body.appendChild(dlg);
  dlg.addEventListener('close', () => dlg.remove());
  try { dlg.showModal(); } catch (e) { dlg.setAttribute('open', ''); }
  return dlg;
}
