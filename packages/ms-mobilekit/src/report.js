// Report a problem: the family's one form, drawn from report_form.json (a copy
// of registry/report-form.json; tools/check_report_form.py refuses a copy that
// differs). The desktop kit and apps.machinesaver.com draw the same file, so a
// person who has reported a problem from one of them has reported from all.
//
//   openReport({ app, version, slug, visibility, email, platform,
//                context: () => ({ screen, connected, settings, lastSeen }) })
//
// The report is posted as JSON, attachments base64-encoded, to the report
// intake, which files the GitHub issue. Nothing opens GitHub or a mail client.
// When the intake cannot be reached the whole report is left on the clipboard
// and the person is told the support address. Every label and sentence on the
// dialog comes from the JSON file; none is written here.

import { trail, button, primary, screens, appConfig } from './kit.js';

export const FAMILY_SUPPORT_EMAIL = 'software-support@machinesaver.net';
export const INTAKE_TIMEOUT_MS = 10000;
const FORM_URL = new URL('report_form.json', import.meta.url);

// ---------- the form definition ----------
let formPromise = null;
export function loadForm() {
  if (!formPromise) {
    formPromise = fetch(FORM_URL, { signal: AbortSignal.timeout(INTAKE_TIMEOUT_MS) }).then(r => {
      if (!r.ok) throw new Error(`report_form.json: HTTP ${r.status}`);
      return r.json();
    }).catch(e => { formPromise = null; throw e; });
  }
  return formPromise;
}

export const fill = (text, vars) => String(text).replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m));

// ---------- the body: what happened, then what the kit collected ----------
export function buildReport({ app, version, title = '', description = '', context = {}, platform = {}, form }) {
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
  const what = form ? form.fields.body_markdown.label : 'What happened';
  return {
    title: title.trim(),
    description: description.trim(),
    details: `## State\n${table}\n\n## What they did\n${stepsMd}\n\n## Last thing seen\n${lastSeen}\n\n## Settings\n${settings}\n`,
    body: `## ${what}\n${description.trim() || '_(nothing written)_'}\n\n## State\n${table}\n\n## What they did\n${stepsMd}\n\n## Last thing seen\n${lastSeen}\n\n## Settings\n${settings}\n`,
  };
}

// ---------- attachments: the limits, enforced before anything is sent ----------
export const MB = 1024 * 1024;
export const formatSize = (bytes) => `${(bytes / MB).toFixed(2)} MB`;
export const extensionOf = (name) => { const m = /\.([A-Za-z0-9]+)$/.exec(name || ''); return m ? m[1].toLowerCase() : ''; };
export const isImage = (file) => /^image\//.test(file.type || '') || ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(extensionOf(file.name));

// Adds `incoming` to `existing` one by one; each refusal carries the wording the
// form gives (refused_prefix + the limits hint), with the file's name as data.
export function acceptFiles(form, existing, incoming) {
  const a = form.attachments; const accepted = [...existing]; const refused = [];
  const refuse = (file) => refused.push({ file, message: `${form.wording.refused_prefix}${file.name}. ${a.hint}` });
  for (const file of incoming) {
    const total = accepted.reduce((n, f) => n + f.size, 0);
    if (!a.extensions.includes(extensionOf(file.name))) refuse(file);
    else if (file.size > a.max_file_mb * MB) refuse(file);
    else if (accepted.length >= a.max_files) refuse(file);
    else if (total + file.size > a.max_total_mb * MB) refuse(file);
    else if (accepted.some(f => f.name === file.name && f.size === file.size)) continue;
    else accepted.push(file);
  }
  return { accepted, refused };
}

// Clipboard images become files named paste-1.png, paste-2.png, … (numbered after
// the pastes already in the list, so a removed paste is not renamed).
export function filesFromPaste(clipboardData, existing = []) {
  const out = []; if (!clipboardData) return out;
  let n = existing.filter(f => /^paste-\d+\.png$/.test(f.name)).length;
  for (const item of Array.from(clipboardData.items || [])) {
    if (item.kind !== 'file' || !/^image\//.test(item.type)) continue;
    const blob = item.getAsFile && item.getAsFile(); if (!blob) continue;
    n += 1;
    out.push(new File([blob], `paste-${n}.png`, { type: blob.type || 'image/png' }));
  }
  return out;
}

export async function encodeAttachments(files) {
  const out = [];
  for (const file of files) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    let bin = ''; for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    out.push({ name: file.name, content_type: file.type || 'application/octet-stream', data_base64: btoa(bin) });
  }
  return out;
}

// ---------- the post: native HTTP inside Capacitor (no CORS), fetch elsewhere ----------
async function post(url, payload, { fetch: fetchFn } = {}) {
  const body = JSON.stringify(payload);
  const headers = { 'Content-Type': 'application/json' };
  const cap = typeof window !== 'undefined' ? window.Capacitor : null;
  const native = cap && cap.isNativePlatform && cap.isNativePlatform() && cap.Plugins && cap.Plugins.CapacitorHttp;
  if (native && !fetchFn) {
    const r = await native.request({ url, method: 'POST', headers, data: payload, connectTimeout: INTAKE_TIMEOUT_MS, readTimeout: INTAKE_TIMEOUT_MS });
    return { status: r.status, json: typeof r.data === 'string' ? safeJson(r.data) : (r.data || {}) };
  }
  const f = fetchFn || globalThis.fetch;
  const r = await f(url, { method: 'POST', headers, body, signal: AbortSignal.timeout(INTAKE_TIMEOUT_MS) });
  return { status: r.status, json: safeJson(await r.text()) };
}
const safeJson = (text) => { try { return JSON.parse(text || '{}'); } catch (e) { return {}; } };

// Posts one report. Resolves to { ok, message, number?, url?, refused? }; the
// message is already the sentence the dialog shows. Never throws.
export async function sendReport({ form, slug, version, kind, title, body, email, fingerprint, files = [], visibility, supportEmail = FAMILY_SUPPORT_EMAIL, fetch: fetchFn }) {
  const w = form.wording;
  const failed = { ok: false, message: fill(w.failed, { support_email: supportEmail }) };
  if (!slug) return failed;
  let result;
  try {
    const attachments = await encodeAttachments(files);
    const payload = { slug, app_version: version, kind, title, body_markdown: body };
    if (email) payload.email = email;
    if (fingerprint) payload.fingerprint = fingerprint;
    if (attachments.length) payload.attachments = attachments;
    result = await post(`${form.intake_url}/v1/reports`, payload, { fetch: fetchFn });
  } catch (e) { return failed; }
  const { status, json } = result;
  if (status === 400 && json && json.error === 'attachment refused') {
    return { ok: false, refused: json.file, message: `${w.refused_prefix}${json.file || ''}. ${form.attachments.hint}` };
  }
  if (status !== 200 && status !== 201 && status !== 202) return failed;
  const number = json.number; const url = json.url || null;
  const isPublic = visibility ? visibility === 'public' : Boolean(url);
  return { ok: true, number, url, message: fill(isPublic ? w.received_public : w.received_private, { number: number == null ? '' : number }) };
}

// ---------- the dialog ----------
const FIELD = 'display:block;min-height:44px;width:100%;margin-top:6px;border-radius:10px;border:1px solid var(--ms-line);background:var(--ms-panel);color:var(--ms-ink);padding:0 10px;font:inherit;box-sizing:border-box';
const AREA = FIELD.replace('min-height:44px', 'min-height:96px').replace('padding:0 10px', 'padding:10px');
const esc = (s) => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

export async function openReport(opts) {
  const form = opts.form || await loadForm();
  const { app, version, platform = {}, context = () => ({}) } = opts;
  const slug = opts.slug || appConfig.slug; const visibility = opts.visibility || appConfig.visibility;
  const supportEmail = opts.email || FAMILY_SUPPORT_EMAIL;
  const w = form.wording; const f = form.fields; const a = form.attachments;
  let ctx = {}; try { ctx = context() || {}; } catch (e) { ctx = { contextError: String(e) }; }
  let files = [];

  const dlg = document.createElement('dialog'); dlg.className = 'ms-card ms-report';
  dlg.style.cssText = 'max-width:430px;width:92vw;max-height:92vh;overflow:auto;border:1px solid var(--ms-line);background:var(--ms-panel);color:var(--ms-ink)';
  dlg.innerHTML = `
    <h2>${esc(fill(w.heading, { app }))}</h2>
    <p class="ms-small ms-muted">${esc(w.intro)}</p>
    <div class="ms-row">
      <label class="ms-small ms-muted" style="flex:1 1 160px">${esc(f.kind.label)}
        <select id="ms-kind" style="${FIELD}">${form.kinds.map(k => `<option value="${esc(k.value)}">${esc(k.label)}</option>`).join('')}</select></label>
      <label class="ms-small ms-muted" style="flex:1 1 120px">${esc(f.app_version.label)}
        <input id="ms-version" value="${esc(version)}" style="${FIELD}"></label>
    </div>
    <label class="ms-small ms-muted">${esc(f.title.label)}
      <input id="ms-title" maxlength="${Number(f.title.max_length) || ''}" placeholder="${esc(f.title.placeholder || '')}" style="${FIELD}"></label>
    <label class="ms-small ms-muted">${esc(f.body_markdown.label)}
      <textarea id="ms-desc" rows="4" placeholder="${esc(f.body_markdown.placeholder || '')}" style="${AREA}"></textarea></label>
    <label class="ms-small ms-muted">${esc(f.email.label)} <span>(${esc(f.email.note)})</span>
      <input id="ms-email" type="email" autocomplete="email" style="${FIELD}"></label>
    <div class="ms-small ms-muted">${esc(f.files.label)} <span>(${esc(f.files.note)})</span>
      <label id="ms-drop" style="${FIELD};position:relative;display:flex;align-items:center;gap:8px;border-style:dashed;padding:10px;cursor:pointer">
        <span>${esc(f.files.prompt)}</span>
        <input id="ms-files" type="file" multiple accept="${a.extensions.map(e => '.' + e).join(',')}" style="position:absolute;width:1px;height:1px;opacity:0;overflow:hidden">
      </label>
      <ul id="ms-file-list" style="list-style:none;margin:6px 0 0;padding:0;display:flex;flex-direction:column;gap:6px"></ul>
      <div id="ms-file-note" class="ms-small ms-muted" role="status">${esc(a.hint)}</div>
    </div>
    <details class="ms-fold"><summary class="ms-small ms-muted" style="font-weight:400;line-height:1.3;padding:8px 0">${esc(w.details_note)}</summary>
      <div><textarea id="ms-details" rows="10" style="width:100%;font-family:var(--ms-mono);font-size:12px;border-radius:10px;border:1px solid var(--ms-line);background:var(--ms-bg);color:var(--ms-ink);padding:10px;box-sizing:border-box"></textarea></div></details>
    <div id="ms-report-status" class="ms-note" role="status" hidden></div>
    <div class="ms-row" id="ms-report-actions"></div>`;
  const q = (s) => dlg.querySelector(s);
  const status = (text) => { const el = q('#ms-report-status'); el.textContent = text; el.hidden = !text; };

  // The collected details are shown once, editable; what the box says is what is sent.
  q('#ms-details').value = buildReport({ app, version, context: ctx, platform, form }).details;
  const compose = () => {
    const title = q('#ms-title').value.trim(); const description = q('#ms-desc').value.trim();
    const body = `## ${f.body_markdown.label}\n${description || '_(nothing written)_'}\n\n${q('#ms-details').value.trim()}\n`;
    return { title, body, kind: q('#ms-kind').value, version: q('#ms-version').value.trim() || version, email: q('#ms-email').value.trim() };
  };
  const asText = () => { const r = compose(); return `${r.title}\n\n${r.body}`; };
  const copy = async () => { try { await navigator.clipboard.writeText(asText()); } catch (e) {} };

  // Files: chosen, dropped or pasted; each shown with a thumbnail, its size and a way off the list.
  const urls = new Set();
  const render = () => {
    const ul = q('#ms-file-list'); ul.replaceChildren();
    for (const file of files) {
      const li = document.createElement('li'); li.style.cssText = 'display:flex;align-items:center;gap:10px;border:1px solid var(--ms-line);border-radius:10px;padding:6px 8px';
      if (isImage(file) && typeof URL !== 'undefined' && URL.createObjectURL) {
        const img = document.createElement('img'); const u = URL.createObjectURL(file); urls.add(u);
        img.src = u; img.alt = ''; img.style.cssText = 'width:44px;height:44px;object-fit:cover;border-radius:6px;background:var(--ms-bg)'; li.appendChild(img);
      }
      const name = document.createElement('span'); name.textContent = file.name; name.style.cssText = 'flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap';
      const size = document.createElement('span'); size.className = 'ms-small ms-muted'; size.textContent = formatSize(file.size);
      const rm = button({ label: '', mark: 'remove', onClick: () => { files = files.filter(x => x !== file); render(); }, attrs: { 'aria-label': `${w.cancel}: ${file.name}`, style: 'flex:0 0 auto;min-width:44px;padding:0 10px' } });
      li.append(name, size, rm); ul.appendChild(li);
    }
  };
  const add = (incoming) => {
    const r = acceptFiles(form, files, incoming); files = r.accepted; render();
    q('#ms-file-note').textContent = r.refused.length ? r.refused.map(x => x.message).join(' ') : a.hint;
  };
  q('#ms-files').addEventListener('change', (e) => { add(Array.from(e.target.files || [])); e.target.value = ''; });
  const drop = q('#ms-drop');
  drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.style.borderColor = 'var(--ms-accent, currentColor)'; });
  drop.addEventListener('dragleave', () => { drop.style.borderColor = ''; });
  drop.addEventListener('drop', (e) => { e.preventDefault(); drop.style.borderColor = ''; add(Array.from((e.dataTransfer && e.dataTransfer.files) || [])); });
  dlg.addEventListener('paste', (e) => { const pasted = filesFromPaste(e.clipboardData, files); if (pasted.length) { e.preventDefault(); add(pasted); } });

  const actions = q('#ms-report-actions');
  const send = primary({ label: w.send, mark: 'send', onClick: async () => {
    const r = compose();
    send.disabled = true; status(w.sending);
    const sent = await sendReport({ form, slug, version: r.version, kind: r.kind, title: r.title, body: r.body, email: r.email || undefined, files, visibility, supportEmail, fetch: opts.fetch });
    if (sent.ok) {
      status(sent.message);
      if (sent.url) { const link = document.createElement('a'); link.href = sent.url; link.target = '_blank'; link.rel = 'noopener'; link.textContent = sent.url; q('#ms-report-status').append(' ', link); }
      actions.replaceChildren(button({ label: w.cancel, mark: 'cancel', onClick: () => dlg.close() }));
      return;
    }
    await copy();
    status(sent.message); send.disabled = false;
  } });
  actions.appendChild(send);
  if (typeof navigator !== 'undefined' && navigator.share) actions.appendChild(button({ label: 'Share', mark: 'share', onClick: () => navigator.share({ title: compose().title, text: asText() }).catch(() => {}) }));
  actions.appendChild(button({ label: w.copy, mark: 'copy', onClick: copy }));
  actions.appendChild(button({ label: w.cancel, mark: 'cancel', onClick: () => dlg.close() }));
  document.body.appendChild(dlg);
  dlg.addEventListener('close', () => { for (const u of urls) { try { URL.revokeObjectURL(u); } catch (e) {} } dlg.remove(); });
  try { dlg.showModal(); } catch (e) { dlg.setAttribute('open', ''); }
  setTimeout(() => { try { q('#ms-title').focus(); } catch (e) {} }, 0);
  return dlg;
}
