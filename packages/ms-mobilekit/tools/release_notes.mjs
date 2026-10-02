// Composes a release body: what changed first (from CHANGELOG), then where to get it.
import { readFileSync } from 'node:fs';
const root = process.argv[2] || process.cwd();
const v = readFileSync(`${root}/www/js/version.js`, 'utf8').match(/VERSION\s*=\s*['"]([^'"]+)['"]/)[1];
const log = readFileSync(`${root}/CHANGELOG.md`, 'utf8');
const start = log.indexOf(`## [${v}]`); const end = log.indexOf('\n## [', start + 1);
const entry = log.slice(start, end < 0 ? undefined : end).split('\n').slice(1).join('\n').trim();
const pkg = JSON.parse(readFileSync(`${root}/package.json`, 'utf8'));
const stores = pkg.msStores || {};
process.stdout.write(`${entry}

## Get it
${stores.ios ? `- **iPhone**: ${stores.ios}\n` : '- **iPhone**: TestFlight / App Store (see README)\n'}${stores.android ? `- **Android**: ${stores.android}\n` : '- **Android**: `app-release.aab` below for Play Console; the `.apk` sideloads on a test phone\n'}
Full changelog: ${pkg.repository ? pkg.repository.url.replace(/\.git$/, '') : ''}/blob/main/CHANGELOG.md
`);
