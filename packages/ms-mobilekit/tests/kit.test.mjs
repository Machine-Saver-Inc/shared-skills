import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { marks, lucide } from '../src/icons.js';
import { compareVersions, explainNetworkError, pickStore } from '../src/update.js';

test('every mark in the register has a vendored file and a Lucide source', () => {
  for (const m of marks) {
    assert.ok(existsSync(new URL(`../src/icons/${m}.svg`, import.meta.url)), `icons/${m}.svg`);
    assert.ok(lucide[m], `SOURCE for ${m}`);
  }
  assert.ok(existsSync(new URL('../src/icons/LICENSE', import.meta.url)));
});

test('the desktop register marks are all present, so vocabulary carries across', () => {
  for (const m of ['back','forward','cancel','discard','settings','save','retry','report','refresh','notes','download','later','open','copy','connect','search','folder','start','stop']) assert.ok(marks.includes(m), m);
});

test('versions compare numerically, not as strings', () => {
  assert.equal(compareVersions('1.10.0', '1.9.0'), 1);
  assert.equal(compareVersions('v1.2.3', '1.2.3'), 0);
  assert.equal(compareVersions('0.9', '1.0.0'), -1);
});

test('network failures are explained, not quoted', () => {
  assert.match(explainNetworkError(new Error('TimeoutError: aborted')), /took too long/);
  assert.match(explainNetworkError(new Error('Failed to fetch')), /No internet/);
});

test('the store link follows the platform', () => {
  const s = { ios: 'https://apps.apple.com/x', android: 'https://play.google.com/x' };
  assert.equal(pickStore(s, 'ios'), s.ios); assert.equal(pickStore(s, 'android'), s.android); assert.equal(pickStore(s, 'web'), null);
});

// Just enough of a DOM for the banner: elements that hold children and click.
function fakeDocument() {
  const make = (tag) => {
    const listeners = {};
    const node = {
      tag, children: [], dataset: {}, attrs: {}, className: '', textContent: '',
      classList: { add() {}, toggle() {} },
      setAttribute(k, v) { this.attrs[k] = v; },
      addEventListener(ev, fn) { (listeners[ev] ||= []).push(fn); },
      click() { for (const fn of listeners.click || []) fn({ target: node }); },
      append(...xs) { this.children.push(...xs); },
      appendChild(x) { this.children.push(x); return x; },
      replaceChildren(...xs) { this.children = xs; },
      insertAdjacentHTML() {},
      remove() {},
    };
    return node;
  };
  return { createElement: make };
}

test('Update now pressed twice starts one update, and can be pressed again once it ends', async () => {
  const saved = { document: globalThis.document, fetch: globalThis.fetch };
  globalThis.document = fakeDocument();
  globalThis.fetch = async () => ({ text: async () => '<svg></svg>' });
  try {
    const { banner } = await import('../src/kit.js');
    let calls = 0; let finish;
    const el = banner({ version: '1.3.0', onUpdate: () => { calls++; return new Promise((r) => { finish = r; }); } });
    const update = el.children.find((c) => c.textContent === 'Update now');
    update.click(); update.click();
    assert.equal(calls, 1, 'a second press while the first is working does nothing');
    finish(); await new Promise((r) => setTimeout(r, 0));
    update.click();
    assert.equal(calls, 2, 'once it has ended, it can be tried again');
  } finally {
    globalThis.document = saved.document; globalThis.fetch = saved.fetch;
  }
});
