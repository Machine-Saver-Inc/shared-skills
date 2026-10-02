import { shell, button, primary, actionBar, signature, banner, screens, openReport, checkForUpdate } from '../vendor/ms-mobilekit/index.js';
import { VERSION } from './version.js';

const APP = 'Example Tool';
const REPO = 'Machine-Saver-Inc/example-tool';   // public → GitHub issue; set to null and give email for a private repo

const ms = shell({ app: APP, version: VERSION, home: 'home' });
window.ms = ms;                                   // the UI gate and screenshot tool drive the app through this

const report = () => openReport({ app: APP, version: VERSION, repo: REPO, context: () => ({ screen: screens.current, connected: 'nothing', settings: {} }) });
const check = async () => {
  const r = await checkForUpdate({ version: VERSION, source: `https://github.com/${REPO}` });
  if (r.status === 'newer') document.getElementById('banner').replaceChildren(banner({ version: r.latest, onWhatsNew: () => alert(r.notes), onUpdate: () => window.open(r.url, '_blank') }));
  else document.getElementById('status').textContent = r.status === 'current' ? `You have the latest version (${VERSION}).` : r.reason;
};
for (const id of ['signature-home', 'signature-more']) document.getElementById(id).replaceChildren(signature({ app: APP, version: VERSION, onReport: report, onCheck: check }));

document.getElementById('job-actions').replaceChildren(actionBar({
  back: button({ label: 'Back', mark: 'back', onClick: () => screens.go('home') }),
  forward: primary({ label: 'Continue', mark: 'forward', onClick: () => { document.getElementById('status').textContent = 'Done.'; screens.go('home'); } }),
}));
document.querySelectorAll('[data-ex]').forEach(b => b.addEventListener('click', () => { document.getElementById('status').textContent = b.dataset.ex === 'ok' ? 'Worked: a plain sentence with a colour.' : 'Failed: what happened, what it means, what to do.'; screens.go('job'); }));
