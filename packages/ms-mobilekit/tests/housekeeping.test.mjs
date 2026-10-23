// The family checks added in 1.1.x and 1.2.0, each proved to fail on a broken
// copy of the template and pass on the template itself.
import test from 'node:test';
import assert from 'node:assert/strict';
import { cpSync, mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { checkCI, checkManifest, checkSupportEmail, checkTemplateDrift, checkReportForm, FAMILY_SUPPORT_EMAIL, TEMPLATE_VERSION } from '../housekeeping/index.mjs';

const kit = join(dirname(fileURLToPath(import.meta.url)), '..');
const template = join(kit, 'template');

// The template as it ships: the kit vendored beside it, as postinstall does in a real app.
function copy() {
  const root = mkdtempSync(join(tmpdir(), 'ms-template-'));
  cpSync(template, root, { recursive: true, filter: (p) => !p.includes('vendor') });
  cpSync(join(kit, 'src'), join(root, 'www/vendor/ms-mobilekit'), { recursive: true });
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
    edit(join(root, 'tests/house_rules.test.mjs'), `ms-mobilekit template v${TEMPLATE_VERSION}`, 'ms-mobilekit template v0');
    assert.ok(checkTemplateDrift(root).some((e) => e.includes('v0')));
    edit(join(root, 'tests/house_rules.test.mjs'), /\/\/ ms-mobilekit template v0\r?\n/, '');
    assert.ok(checkTemplateDrift(root).some((e) => e.includes('no "ms-mobilekit template vN" marker')));
  } finally { rmSync(root, { recursive: true, force: true }); }
});

test("Report a problem is the kit's form, vendored unchanged, sent through openReport", () => {
  const root = copy();
  try {
    assert.deepEqual(checkReportForm(root), []);
    // the vendored form edited in the app
    const vendored = join(root, 'www/vendor/ms-mobilekit/report_form.json');
    edit(vendored, '"send": "Send to Machine Saver"', '"send": "Send it"');
    assert.ok(checkReportForm(root).some((e) => e.includes('differs')));
    rmSync(vendored);
    assert.ok(checkReportForm(root).some((e) => e.includes('missing')));
    cpSync(join(kit, 'src/report_form.json'), vendored);
    assert.deepEqual(checkReportForm(root), []);
    // the app builds a GitHub issue or mailto link, or its own dialog
    writeFileSync(join(root, 'www/js/extra.js'), "const u = issueUrl('x/y', r); location.href = 'mailto:a@b.c?subject=' + report.title;\n");
    let errs = checkReportForm(root);
    assert.ok(errs.some((e) => e.includes('issueUrl/mailtoUrl')) && errs.some((e) => e.includes('mailto link for a report')));
    writeFileSync(join(root, 'www/js/extra.js'), "location.href = 'mailto:a@b.c?subject=diagnostics';\n");
    assert.deepEqual(checkReportForm(root), [], 'a mailto for something other than a report is allowed');
    writeFileSync(join(root, 'www/js/extra.js'), "const d = document.createElement('dialog'); d.innerHTML = '<h2>Report a problem</h2>';\n");
    assert.ok(checkReportForm(root).some((e) => e.includes('own report dialog')));
    rmSync(join(root, 'www/js/extra.js'));
    // the footer no longer opens the kit's dialog
    const app = join(root, 'www/js/app.js'); const src = readFileSync(app, 'utf8');
    edit(app, /openReport\(/, 'myReport(');
    errs = checkReportForm(root);
    assert.ok(errs.some((e) => e.includes('never calls the kit\'s openReport')));
    writeFileSync(app, src.replace(/onReport: report, /, ''));
    assert.ok(checkReportForm(root).some((e) => e.includes('without onReport')));
    // the slug the intake files against is not the manifest's
    writeFileSync(app, src.replace("slug: 'example-tool'", "slug: 'other-tool'"));
    assert.ok(checkReportForm(root).some((e) => e.includes("slug: 'example-tool'")));
  } finally { rmSync(root, { recursive: true, force: true }); }
});
