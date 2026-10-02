// Generates screenshots/ offscreen, identical every release. Drive the app through window.ms.
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { createRequire } from 'node:module';
const { start } = createRequire(import.meta.url)('ms-mobilekit/tools/static.cjs');
mkdirSync('screenshots', { recursive: true });
const srv = await start();
const b = await chromium.launch();
const shots = [['home', 'home', 'light'], ['job', 'job', 'dark'], ['help', 'help', 'light']];
for (const [name, screen, scheme] of shots) {
  const p = await b.newPage({ viewport: { width: 390, height: 844 }, colorScheme: scheme, deviceScaleFactor: 2 });
  await p.goto(srv.url); await p.waitForTimeout(400);
  await p.evaluate(s => window.ms.screens.go(s), screen); await p.waitForTimeout(300);
  await p.screenshot({ path: `screenshots/${name}.png` }); await p.close();
}
await b.close(); srv.close(); console.log('screenshots written');
