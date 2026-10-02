// Copied from ms-mobilekit/template on day one. Do not edit; the rules live in the kit.
import test from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { runAll, CHECKS } from 'ms-mobilekit/housekeeping';
const root = join(dirname(fileURLToPath(import.meta.url)), '..');
for (const [name, fn] of Object.entries(CHECKS)) test(name, () => assert.deepEqual(fn(root), []));
test('all house rules together', () => assert.deepEqual(runAll(root), []));
