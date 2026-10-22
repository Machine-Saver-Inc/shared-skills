// The family checks added in 1.1.x, each proved to fail on a broken copy of the
// template and pass on the template itself.
import test from 'node:test';
import assert from 'node:assert/strict';
import { cpSync, mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { checkCI, checkManifest, checkSupportEmail, checkTemplateDrift, FAMILY_SUPPORT_EMAIL } from '../housekeeping/index.mjs';

const template = join(dirname(fileURLToPath(import.meta.url)), '..', 'template');

function copy() {
  const root = mkdtempSync(join(tmpdir(), 'ms-template-'));
  cpSync(template, root, { recursive: true, filter: (p) => !p.includes('vendor') });
  return root;
}
const edit = (p, from, to) => writeFileSync(p, readFileSync(p, 'utf8').replace(from, to));

test('ci.yml must run on a schedule as well', () => {
  const root = copy();
  try {
    assert.deepEqual(checkCI(root), []);
    edit(join(root, '.github/workflows/ci.yml'), /\r?\n\s*schedule:\r?\n\s*- cron: "[^"]+"\r?\n/, '\n');
    assert.ok(checkCI(root).some((e) => e.includes('schedule')));
  } finally { rmSync(root, { recursive: true, force: true }); }
});

test('the manifest must agree with the app and pin a kit tag', () => {
  const root = copy();
  try {
    assert.deepEqual(checkManifest(root), []);
    edit(join(root, 'package.json'), /"ref": "[^"]+"/, '"ref": "main"');
    assert.ok(checkManifest(root).some((e) => e.includes('never main')));
    edit(join(root, 'package.json'), '"ref": "main"', '"ref": "ms-mobilekit/v9.9.9"');
    assert.ok(checkManifest(root).some((e) => e.includes('9.9.9')));
    rmSync(join(root, 'ms-app.json'));
    assert.ok(checkManifest(root)[0].includes('missing'));
  } finally { rmSync(root, { recursive: true, force: true }); }
});

test("a report address is the family's", () => {
  const root = copy();
  try {
    assert.deepEqual(checkSupportEmail(root), []);
    writeFileSync(join(root, 'www/js/extra.js'), "openReport({ email: 'support@machinesaver.net' });\n");
    const errs = checkSupportEmail(root);
    assert.equal(errs.length, 1);
    assert.ok(errs[0].includes(FAMILY_SUPPORT_EMAIL));
  } finally { rmSync(root, { recursive: true, force: true }); }
});

test('the copied house-rules test carries the current marker', () => {
  const root = copy();
  try {
    assert.deepEqual(checkTemplateDrift(root), []);
    edit(join(root, 'tests/house_rules.test.mjs'), 'ms-mobilekit template v1', 'ms-mobilekit template v0');
    assert.ok(checkTemplateDrift(root).some((e) => e.includes('v0')));
    edit(join(root, 'tests/house_rules.test.mjs'), /\/\/ ms-mobilekit template v0\r?\n/, '');
    assert.ok(checkTemplateDrift(root).some((e) => e.includes('no "ms-mobilekit template vN" marker')));
  } finally { rmSync(root, { recursive: true, force: true }); }
});
