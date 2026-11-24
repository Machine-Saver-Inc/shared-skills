import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { SSO_PROVIDERS, signInButtonsHtml, signInLabel, providerName } from '../src/signin.js';
import { checkSignIn } from '../housekeeping/signin.mjs';

test('the stack is Google, Apple, Microsoft, each "Sign in with …" with its own logo', () => {
  assert.deepEqual(SSO_PROVIDERS, ['google', 'apple', 'microsoft']);
  const html = signInButtonsHtml();
  const labels = [...html.matchAll(/<span>([^<]+)<\/span>/g)].map(m => m[1]);
  assert.deepEqual(labels, ['Sign in with Google', 'Sign in with Apple', 'Sign in with Microsoft']);
  assert.equal((html.match(/<svg /g) || []).length, 3);
  assert.equal((html.match(/class="ms-sso-btn"/g) || []).length, 3);
  assert.doesNotMatch(html, /Continue with/);
  assert.equal(signInLabel('apple'), 'Sign in with Apple'); assert.equal(providerName('microsoft'), 'Microsoft');
  assert.deepEqual([...signInButtonsHtml(['microsoft', 'facebook']).matchAll(/data-provider="(\w+)"/g)].map(m => m[1]), ['microsoft'], 'unknown providers are dropped');
});

test('kit.css carries both themes for the stack, and Apple stays black in dark', () => {
  const css = readFileSync(new URL('../src/kit.css', import.meta.url), 'utf8');
  assert.match(css, /\.ms-sso-btn\[data-provider="google"\] \{ --sso-bg: #ffffff/);
  assert.match(css, /:root\[data-theme="dark"\] \.ms-sso-btn \{/);
  assert.match(css, /:root\[data-theme="dark"\] \.ms-sso-btn\[data-provider="apple"\] \{ --sso-bg: #000000/);
  assert.match(css, /min-height: 48px/);
});

test('house rule: sign-in buttons come from the kit', () => {
  const root = mkdtempSync(join(tmpdir(), 'sso-'));
  try {
    mkdirSync(join(root, 'www/js'), { recursive: true });
    writeFileSync(join(root, 'www/index.html'), '<main><div id="signin"></div></main>');
    writeFileSync(join(root, 'www/js/app.js'), 'const u = `${base}/auth/start?provider=x`;');
    assert.equal(checkSignIn(root).length, 1, 'starts a sign-in without mountSignIn');
    writeFileSync(join(root, 'www/js/app.js'), 'mountSignIn(el, { onPick }); const u = `${base}/auth/start`;');
    assert.deepEqual(checkSignIn(root), []);
    writeFileSync(join(root, 'www/index.html'), '<button class="btn primary" data-mark="user" data-signin="google">Continue with Google</button>');
    assert.equal(checkSignIn(root).length, 1, 'a hand-made button');
    writeFileSync(join(root, 'www/index.html'), '<p>Sign in with your Google, Apple or Microsoft account.</p><div id="signin"></div>');
    assert.deepEqual(checkSignIn(root), [], 'prose about signing in is fine');
    rmSync(join(root, 'www/js/app.js'));
    assert.deepEqual(checkSignIn(root), [], 'an app without sign-in owes nothing');
  } finally { rmSync(root, { recursive: true, force: true }); }
});
