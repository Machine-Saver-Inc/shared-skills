// ---- 16. single sign-on buttons come from the kit ----
// The first app drew its own "Continue with Google / Microsoft" buttons; the next one would have
// drawn them differently, and neither offered Apple, which App Review asks for beside Google and
// Microsoft. The rule: an app that starts a sign-in draws the buttons with the kit's mountSignIn,
// and no page carries a hand-made "Sign in with …" or "Continue with …" button.
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative } from 'node:path';

function walk(dir, exts, out = []) {
  if (!existsSync(dir)) return out;
  for (const n of readdirSync(dir)) {
    if (n === 'vendor' || n === 'node_modules' || n.startsWith('.')) continue;
    const p = join(dir, n);
    if (statSync(p).isDirectory()) walk(p, exts, out);
    else if (exts.some(e => n.endsWith(e))) out.push(p);
  }
  return out;
}

export function checkSignIn(root) {
  const errs = [];
  const www = join(root, 'www');
  if (!existsSync(www)) return errs;
  const handMade = /<button\b[^>]*>(?:(?!<\/button>)[\s\S])*?\b(?:Continue|Sign in|Log in) with (?:Google|Apple|Microsoft)\b/i;
  for (const f of walk(www, ['.html'])) {
    const html = readFileSync(f, 'utf8');
    if (handMade.test(html) || /\bdata-signin=/.test(html)) errs.push(`${relative(root, f)}: a sign-in button is drawn by hand — use the kit's mountSignIn so every app shows the same "Sign in with …" stack`);
  }
  const js = walk(join(www, 'js'), ['.js', '.mjs']).map(f => readFileSync(f, 'utf8')).join('\n');
  if (/\/auth\/start/.test(js) && !/\bmountSignIn\s*\(/.test(js)) errs.push("www/js starts a sign-in (/auth/start) but never calls the kit's mountSignIn — the buttons must come from the kit");
  return errs;
}
