import { shell, button, primary, actionBar, signature, banner, screens, openReport, watchForUpdates, installUpdate, feedUrl, describeOutcome } from '../vendor/ms-mobilekit/index.js';
import { VERSION } from './version.js';

const APP = 'Example Tool';

// slug and visibility as in ms-app.json: the report is filed against that repository by the intake,
// and the update feed is the store's latest.json for that slug
const ms = shell({ app: APP, version: VERSION, home: 'home', slug: 'example-tool', visibility: 'public' });
window.ms = ms;                                   // the UI gate and screenshot tool drive the app through this

const report = () => openReport({ app: APP, version: VERSION, context: () => ({ screen: screens.current, connected: 'nothing', settings: {} }) });

// Checks by itself at launch, on return to the foreground and when the connection returns, hourly at most.
// The banner shows on "newer"; the other two outcomes are said only when the footer button asked.
const updates = watchForUpdates({ version: VERSION, feed: feedUrl('example-tool'), onResult: (r, { forced }) => {
  if (r.status === 'newer') document.getElementById('banner').replaceChildren(banner({ version: r.latest, onWhatsNew: () => alert(r.notes),
    onUpdate: (e, el) => installUpdate(r, { onStatus: (s) => el.say(s) }) }));
  else if (forced) document.getElementById('status').textContent = describeOutcome(r, VERSION);
} });
const check = () => updates.check(true);
for (const id of ['signature-home', 'signature-more']) document.getElementById(id).replaceChildren(signature({ app: APP, version: VERSION, onReport: report, onCheck: check }));

document.getElementById('job-actions').replaceChildren(actionBar({
  back: button({ label: 'Back', mark: 'back', onClick: () => screens.go('home') }),
  forward: primary({ label: 'Continue', mark: 'forward', onClick: () => { document.getElementById('status').textContent = 'Done.'; screens.go('home'); } }),
}));
document.querySelectorAll('[data-ex]').forEach(b => b.addEventListener('click', () => { document.getElementById('status').textContent = b.dataset.ex === 'ok' ? 'Worked: a plain sentence with a colour.' : 'Failed: what happened, what it means, what to do.'; screens.go('job'); }));
