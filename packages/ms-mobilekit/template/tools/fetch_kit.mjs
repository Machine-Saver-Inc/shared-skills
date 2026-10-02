// Installs ms-mobilekit from the shared-skills repository into node_modules/,
// then vendors it into www/. npm cannot install a subfolder of a git repo, so
// this does it: download the repo tarball at a ref, extract packages/ms-mobilekit.
//
//   "msKit": { "repo": "Machine-Saver-Inc/shared-skills", "ref": "main" }   in package.json
//   node tools/fetch_kit.mjs            (runs from postinstall)
//
// Pin "ref" to a tag or commit when the app must be reproducible.
import { readFileSync, mkdirSync, rmSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';

const pkg = JSON.parse(readFileSync('package.json', 'utf8'));
const { repo = 'Machine-Saver-Inc/shared-skills', ref = 'main', path = 'packages/ms-mobilekit' } = pkg.msKit || {};
const dest = join('node_modules', 'ms-mobilekit');
const url = `https://codeload.github.com/${repo}/tar.gz/${ref}`;

const res = await fetch(url, { signal: AbortSignal.timeout(60000) });
if (!res.ok) { console.error(`fetch_kit: ${url} → HTTP ${res.status}`); process.exit(1); }
const buf = Buffer.from(await res.arrayBuffer());
rmSync(dest, { recursive: true, force: true }); mkdirSync(dest, { recursive: true });
// tarball root is <repo-name>-<ref-with-slashes-replaced>; strip that plus the two path segments
const depth = 1 + path.split('/').length;
execFileSync('tar', ['-xzf', '-', '--strip-components', String(depth), '-C', dest, `--wildcards`, `*/${path}/*`], { input: buf, stdio: ['pipe', 'inherit', 'inherit'] });
if (!existsSync(join(dest, 'package.json'))) { console.error('fetch_kit: extracted nothing — check msKit.path'); process.exit(1); }
const v = JSON.parse(readFileSync(join(dest, 'package.json'), 'utf8')).version;
console.log(`ms-mobilekit ${v} installed from ${repo}@${ref}`);
execFileSync('node', [join(dest, 'tools', 'vendor_kit.mjs')], { stdio: 'inherit' });
