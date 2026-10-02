// Applies native.json to the generated platform projects after `npx cap add`:
// Info.plist usage strings on iOS, <uses-permission> and <uses-feature> on Android.
// Idempotent. Usage: node node_modules/ms-mobilekit/tools/apply_native.mjs [app root]
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
const root = process.argv[2] || process.cwd();
const n = JSON.parse(readFileSync(join(root, 'native.json'), 'utf8'));
const plistPath = join(root, 'ios/App/App/Info.plist');
if (existsSync(plistPath)) {
  let p = readFileSync(plistPath, 'utf8');
  for (const cfg of Object.values(n.capabilities || {})) for (const key of (cfg.ios && cfg.ios.plist) || []) {
    if (!p.includes(`<key>${key}</key>`)) p = p.replace(/<\/dict>\s*<\/plist>\s*$/, `\t<key>${key}</key>\n\t<string>${cfg.usage}</string>\n</dict>\n</plist>\n`);
  }
  writeFileSync(plistPath, p); console.log('Info.plist updated');
}
const manPath = join(root, 'android/app/src/main/AndroidManifest.xml');
if (existsSync(manPath)) {
  let m = readFileSync(manPath, 'utf8');
  for (const cfg of Object.values(n.capabilities || {})) {
    for (const perm of (cfg.android && cfg.android.permissions) || []) if (!m.includes(perm)) m = m.replace('<application', `<uses-permission android:name="${perm}" />\n    <application`);
    for (const feat of (cfg.android && cfg.android.features) || []) if (!m.includes(feat)) m = m.replace('<application', `<uses-feature android:name="${feat}" android:required="false" />\n    <application`);
  }
  writeFileSync(manPath, m); console.log('AndroidManifest.xml updated');
}
