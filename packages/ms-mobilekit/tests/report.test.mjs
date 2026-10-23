// The report logic is DOM-free apart from the trail: the body builder, the
// attachment limits, the paste-to-file step and the post to the intake are all
// asserted here with a fake fetch. Every sentence shown comes from
// src/report_form.json, so the tests read their expectations from that file.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
globalThis.window = { scrollTo() {} }; globalThis.document = { querySelector: () => null, querySelectorAll: () => [], dispatchEvent() {} , createElement: () => ({ classList: { add() {}, toggle() {} }, appendChild() {}, append() {}, addEventListener() {}, dataset: {}, setAttribute() {} }) };
const { buildReport, acceptFiles, filesFromPaste, encodeAttachments, sendReport, fill, FAMILY_SUPPORT_EMAIL } = await import('../src/report.js');
const { trail } = await import('../src/kit.js');
const form = JSON.parse(readFileSync(new URL('../src/report_form.json', import.meta.url), 'utf8'));

const png = (bytes = 100) => new File([new Uint8Array(bytes).fill(1)], 'shot.png', { type: 'image/png' });
const named = (name, bytes = 10, type = '') => new File([new Uint8Array(bytes)], name, { type });
const fakeFetch = (status, json, seen = {}) => async (url, init) => {
  seen.url = url; seen.init = init; seen.body = JSON.parse(init.body);
  return { status, text: async () => JSON.stringify(json) };
};

test('report leads with what happened, then one contiguous state table, then the trail (labels only)', () => {
  trail.clear(); trail.push('opened', 'Home'); trail.push('pressed', 'Start the job'); trail.push('pressed', 'Start the job');
  const r = buildReport({ app: 'Example', version: '1.2.0', title: 'It stopped', description: 'Pressed start', context: { screen: 'Job', connected: 'nothing', settings: { a: 1 } }, form });
  assert.equal(r.title, 'It stopped');
  assert.ok(r.body.startsWith(`## ${form.fields.body_markdown.label}\nPressed start`));
  assert.ok(r.body.indexOf('## State') < r.body.indexOf('## What they did'));
  assert.doesNotMatch(r.body.split('## State')[1].split('## What they did')[0], /\n\n\|/, 'a blank line inside the table stops GitHub rendering it');
  assert.match(r.body, /pressed Start the job ×2/);
  assert.match(r.body, /"a": 1/);
  assert.ok(r.body.includes(r.details), 'the editable details are the tail of the body');
});

test('the limits in the form are enforced before anything is sent, with the refused_prefix wording', () => {
  const a = form.attachments;
  let r = acceptFiles(form, [], [named('notes.exe')]);
  assert.equal(r.accepted.length, 0);
  assert.ok(r.refused[0].message.startsWith(form.wording.refused_prefix + 'notes.exe'));
  assert.ok(r.refused[0].message.endsWith(a.hint));
  r = acceptFiles(form, [], [named('big.png', a.max_file_mb * 1024 * 1024 + 1)]);
  assert.equal(r.refused.length, 1, 'one file over max_file_mb');
  r = acceptFiles(form, [], Array.from({ length: a.max_files + 1 }, (_, i) => named(`f${i}.txt`)));
  assert.equal(r.accepted.length, a.max_files); assert.equal(r.refused.length, 1, 'one file too many');
  const each = Math.ceil((a.max_total_mb * 1024 * 1024) / 3) + 1;
  r = acceptFiles(form, [], [named('a.log', each), named('b.log', each), named('c.log', each)]);
  assert.equal(r.accepted.length, 2); assert.equal(r.refused[0].file.name, 'c.log', 'the file that crosses max_total_mb');
  r = acceptFiles(form, [named('a.csv')], [named('a.csv')]);
  assert.equal(r.accepted.length, 1, 'the same file twice is listed once');
  r = acceptFiles(form, [], [named('Shot.PNG', 5, 'image/png')]);
  assert.equal(r.accepted.length, 1, 'extensions compare case-insensitively');
});

test('a pasted screenshot becomes paste-1.png, the next paste-2.png', () => {
  const item = (type) => ({ kind: 'file', type, getAsFile: () => new Blob([new Uint8Array(8)], { type }) });
  const first = filesFromPaste({ items: [item('image/png'), { kind: 'string', type: 'text/plain' }] }, []);
  assert.equal(first.length, 1); assert.equal(first[0].name, 'paste-1.png'); assert.equal(first[0].type, 'image/png');
  assert.ok(first[0] instanceof File);
  const second = filesFromPaste({ items: [item('image/png')] }, first);
  assert.equal(second[0].name, 'paste-2.png');
  assert.deepEqual(filesFromPaste(null, []), []);
  assert.deepEqual(filesFromPaste({ items: [{ kind: 'string', type: 'text/plain' }] }, []), []);
});

test('the post is the intake JSON: slug, app_version, kind, title, body_markdown, email, base64 attachments', async () => {
  const seen = {};
  const r = await sendReport({ form, slug: 'example-tool', version: '1.2.0', kind: 'bug', title: 'It stopped', body: '## What\nx', email: 'a@b.c', files: [png(3)], fetch: fakeFetch(201, { number: 12, url: null }, seen) });
  assert.equal(seen.url, `${form.intake_url}/v1/reports`);
  assert.equal(seen.init.method, 'POST'); assert.equal(seen.init.headers['Content-Type'], 'application/json');
  assert.ok(seen.init.signal, 'a timeout rides on every post');
  assert.deepEqual(Object.keys(seen.body).sort(), ['app_version', 'attachments', 'body_markdown', 'email', 'kind', 'slug', 'title']);
  assert.equal(seen.body.slug, 'example-tool'); assert.equal(seen.body.app_version, '1.2.0'); assert.equal(seen.body.kind, 'bug');
  assert.deepEqual(seen.body.attachments, [{ name: 'shot.png', content_type: 'image/png', data_base64: Buffer.from([1, 1, 1]).toString('base64') }]);
  assert.equal(r.ok, true); assert.equal(r.number, 12);
  const [enc] = await encodeAttachments([named('x.txt', 70000, 'text/plain')]);
  assert.equal(Buffer.from(enc.data_base64, 'base64').length, 70000, 'large files encode whole');
});

test('no email and no files: the optional keys are left out, not sent empty', async () => {
  const seen = {};
  await sendReport({ form, slug: 's', version: '1', kind: 'improvement', title: 't', body: 'b', fetch: fakeFetch(201, { number: 1 }, seen) });
  assert.deepEqual(Object.keys(seen.body).sort(), ['app_version', 'body_markdown', 'kind', 'slug', 'title']);
});

test('success wording follows the repository: private shows the number, public shows the link', async () => {
  const priv = await sendReport({ form, slug: 's', version: '1', kind: 'bug', title: 't', body: 'b', visibility: 'private', fetch: fakeFetch(201, { number: 7, url: null }) });
  assert.equal(priv.message, fill(form.wording.received_private, { number: 7 }));
  const pub = await sendReport({ form, slug: 's', version: '1', kind: 'bug', title: 't', body: 'b', visibility: 'public', fetch: fakeFetch(201, { number: 8, url: 'https://github.com/x/y/issues/8' }) });
  assert.equal(pub.message, fill(form.wording.received_public, { number: 8 })); assert.equal(pub.url, 'https://github.com/x/y/issues/8');
  const dup = await sendReport({ form, slug: 's', version: '1', kind: 'bug', title: 't', body: 'b', fetch: fakeFetch(200, { number: 3, status: 'duplicate' }) });
  assert.equal(dup.ok, true, 'a duplicate was still received');
});

test('failure wording names the support address; a 5xx, a network error and a missing slug all fail the same way', async () => {
  const expected = fill(form.wording.failed, { support_email: FAMILY_SUPPORT_EMAIL });
  assert.match(expected, /software-support@machinesaver\.net/);
  const down = await sendReport({ form, slug: 's', version: '1', kind: 'bug', title: 't', body: 'b', fetch: fakeFetch(503, {}) });
  assert.equal(down.ok, false); assert.equal(down.message, expected);
  const offline = await sendReport({ form, slug: 's', version: '1', kind: 'bug', title: 't', body: 'b', fetch: async () => { throw new TypeError('Failed to fetch'); } });
  assert.equal(offline.message, expected);
  const noSlug = await sendReport({ form, version: '1', kind: 'bug', title: 't', body: 'b', fetch: async () => { throw new Error('must not be called'); } });
  assert.equal(noSlug.message, expected);
  const other = await sendReport({ form, slug: 's', version: '1', kind: 'bug', title: 't', body: 'b', supportEmail: 'x@y.z', fetch: fakeFetch(404, {}) });
  assert.match(other.message, /x@y\.z/);
});

test('an attachment the intake refuses is named with the refused_prefix wording', async () => {
  const r = await sendReport({ form, slug: 's', version: '1', kind: 'bug', title: 't', body: 'b', files: [png()], fetch: fakeFetch(400, { error: 'attachment refused', rule: 'extension', file: 'shot.png' }) });
  assert.equal(r.ok, false); assert.equal(r.refused, 'shot.png');
  assert.ok(r.message.startsWith(form.wording.refused_prefix + 'shot.png'));
});

test('the kit no longer builds GitHub issue or mailto links', async () => {
  const mod = await import('../src/report.js');
  assert.equal(mod.issueUrl, undefined); assert.equal(mod.mailtoUrl, undefined);
  assert.doesNotMatch(readFileSync(new URL('../src/report.js', import.meta.url), 'utf8'), /mailto:|issues\/new/);
});
