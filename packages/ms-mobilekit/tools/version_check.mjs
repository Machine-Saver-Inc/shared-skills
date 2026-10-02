import { checkVersion, checkChangelog } from '../housekeeping/index.mjs';
const root = process.argv[2] || process.cwd();
const errs = [...checkVersion(root), ...checkChangelog(root)];
if (errs.length) { console.error(errs.join('\n')); process.exit(1); }
console.log('version consistent');
