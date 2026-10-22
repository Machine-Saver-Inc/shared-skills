#!/usr/bin/env node
// The template passes every house rule it ships, so what a new app is copied
// from can never be behind the rules it is checked against. Run from the kit:
//     node tools/check_template.mjs
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { CHECKS } from '../housekeeping/index.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..', 'template');
// A real app vendors the kit in postinstall; the template is checked the same
// way it would ship, with the kit beside it (www/vendor/ is gitignored).
execFileSync(process.execPath, [join(here, 'vendor_kit.mjs'), root], { stdio: 'inherit' });
let failures = 0;
for (const [name, check] of Object.entries(CHECKS)) {
  let errs;
  try { errs = check(root); } catch (e) { errs = [`threw: ${e.message}`]; }
  if (errs.length) { failures += errs.length; console.log(`${name}:`); for (const e of errs) console.log(`  ${e}`); }
}
console.log(`${Object.keys(CHECKS).length} checks over the template, ${failures} faults`);
process.exit(failures ? 1 : 0);
