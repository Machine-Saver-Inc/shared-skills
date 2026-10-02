// Copies the kit's runtime into www/vendor/ms-mobilekit so the app ships
// self-contained. Run after `npm install` and whenever the kit is updated.
// Usage: node node_modules/ms-mobilekit/tools/vendor_kit.mjs [app root]
import { cpSync, mkdirSync, writeFileSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const here = dirname(fileURLToPath(import.meta.url));
const root = process.argv[2] || process.cwd();
const dest = join(root, 'www/vendor/ms-mobilekit');
mkdirSync(dest, { recursive: true });
cpSync(join(here, '../src'), dest, { recursive: true });
const v = JSON.parse(readFileSync(join(here, '../package.json'), 'utf8')).version;
writeFileSync(join(dest, 'KIT_VERSION'), v + '\n');
console.log(`ms-mobilekit ${v} vendored into ${dest}`);
