#!/usr/bin/env node
// The template passes every house rule it ships, so what a new app is copied
// from can never be behind the rules it is checked against. Run from the kit:
//     node tools/check_template.mjs
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { CHECKS } from '../housekeeping/index.mjs';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', 'template');
let failures = 0;
for (const [name, check] of Object.entries(CHECKS)) {
  let errs;
  try { errs = check(root); } catch (e) { errs = [`threw: ${e.message}`]; }
  if (errs.length) { failures += errs.length; console.log(`${name}:`); for (const e of errs) console.log(`  ${e}`); }
}
console.log(`${Object.keys(CHECKS).length} checks over the template, ${failures} faults`);
process.exit(failures ? 1 : 0);
