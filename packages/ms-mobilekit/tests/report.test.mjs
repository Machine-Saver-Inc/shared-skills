// The report builder is DOM-free apart from the trail, so its output can be asserted.
import test from 'node:test';
import assert from 'node:assert/strict';
globalThis.window = { scrollTo() {} }; globalThis.document = { querySelector: () => null, querySelectorAll: () => [], dispatchEvent() {} , createElement: () => ({ classList: { add() {}, toggle() {} }, appendChild() {}, append() {}, addEventListener() {}, dataset: {}, setAttribute() {} }) };
const { buildReport, issueUrl } = await import('../src/report.js');
const { trail } = await import('../src/kit.js');

test('report leads with what happened, then one contiguous state table, then the trail (labels only)', () => {
  trail.clear(); trail.push('opened', 'Home'); trail.push('pressed', 'Start the job'); trail.push('pressed', 'Start the job');
  const r = buildReport({ app: 'Example', version: '1.2.0', summary: 'It stopped', context: { screen: 'Job', connected: 'nothing', settings: { a: 1 } } });
  assert.equal(r.title, '[bug] It stopped');
  assert.ok(r.body.indexOf('## What happened') < r.body.indexOf('## State'));
  assert.doesNotMatch(r.body.split('## State')[1].split('## What they did')[0], /\n\n\|/, 'a blank line inside the table stops GitHub rendering it');
  assert.match(r.body, /pressed Start the job ×2/);
  assert.match(r.body, /"a": 1/);
});

test('an issue URL never exceeds ~6000 chars; the full report stays on the clipboard', () => {
  const url = issueUrl('Machine-Saver-Inc/x', { title: 't', body: 'x'.repeat(20000) });
  assert.ok(url.length <= 6000, url.length);
  assert.match(decodeURIComponent(url), /trimmed/);
});
