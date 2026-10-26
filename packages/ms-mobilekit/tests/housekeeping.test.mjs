// The family checks added in 1.1.x and 1.2.0, each proved to fail on a broken
// copy of the template and pass on the template itself.
import test from 'node:test';
import assert from 'node:assert/strict';
import { cpSync, mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { checkCI, checkManifest, checkSupportEmail, checkTemplateDrift, checkReportForm, checkUpdateFeed, checkNative, FAMILY_SUPPORT_EMAIL, TEMPLATE_VERSION } from '../housekeeping/index.mjs';

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

test('the app checks for updates by itself from the store feed, can install one, and its release writes the feed last', () => {
  const root = copy();
  try {
    assert.deepEqual(checkUpdateFeed(root), []);
    assert.deepEqual(checkNative(root), [], 'the template declares the install permission with a usage string');
    const app = join(root, 'www/js/app.js'); const src = readFileSync(app, 'utf8');
    // the check only runs from the button (1.2 and before)
    writeFileSync(app, src.replace(/watchForUpdates\(/, 'myWatch('));
    assert.ok(checkUpdateFeed(root).some((e) => e.includes('never calls the kit\'s watchForUpdates')));
    // the feed is another app's, or GitHub's API
    writeFileSync(app, src.replace("feedUrl('example-tool')", "feedUrl('other-tool')"));
    assert.ok(checkUpdateFeed(root).some((e) => e.includes("feedUrl('example-tool')")));
    writeFileSync(app, src + "\nfetch('https://api.github.com/repos/x/y/releases/latest', { signal: AbortSignal.timeout(1) });\n");
    assert.ok(checkUpdateFeed(root).some((e) => e.includes('asks GitHub')));
    // Update now opens a page instead of installing; the button no longer forces a check
    writeFileSync(app, src.replace(/installUpdate\(/, 'window.open('));
    assert.ok(checkUpdateFeed(root).some((e) => e.includes('never calls the kit\'s installUpdate')));
    writeFileSync(app, src.replace(', onCheck: check', ''));
    assert.ok(checkUpdateFeed(root).some((e) => e.includes('without onCheck')));
    writeFileSync(app, src);
    assert.deepEqual(checkUpdateFeed(root), []);
    // Android cannot open the build without the permission
    writeFileSync(join(root, 'native.json'), '{ "capabilities": {} }');
    assert.ok(checkUpdateFeed(root).some((e) => e.includes('REQUEST_INSTALL_PACKAGES')));
    // the release never writes the feed, writes it to the wrong place, with a key, or before the files
    const rel = join(root, '.github/workflows/release.yml'); const yml = readFileSync(rel, 'utf8');
    writeFileSync(rel, yml.replace(/.*publish_feed.*\n/, ''));
    assert.ok(checkUpdateFeed(root).some((e) => e.includes('publish_feed')));
    writeFileSync(rel, yml.replace(/machinesaver-mobile-releases/g, 'my-bucket'));
    assert.ok(checkUpdateFeed(root).some((e) => e.includes('mobile release store')));
    writeFileSync(rel, yml.replace('google-github-actions/auth@v2', 'my/auth@v1'));
    assert.ok(checkUpdateFeed(root).some((e) => e.includes('keylessly')));
    writeFileSync(rel, yml.replace(/( *)gcloud storage cp dist\/\* (.*)\n( *)gcloud storage cp latest\.json (.*)\n/, '$1gcloud storage cp latest.json $4\n$3gcloud storage cp dist/* $2\n'));
    assert.ok(checkUpdateFeed(root).some((e) => e.includes('before the build files')), 'the feed written before the files is caught');
    writeFileSync(rel, yml.replace(/.*gcloud storage cp latest\.json.*\n/, ''));
    assert.ok(checkUpdateFeed(root).some((e) => e.includes('never uploads latest.json')));
    rmSync(rel);
    assert.ok(checkUpdateFeed(root).some((e) => e.includes('release.yml is missing')));
  } finally { rmSync(root, { recursive: true, force: true }); }
});
