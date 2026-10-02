// Minimal static server for www/ so ES modules load under test (file:// blocks them).
const http = require('http'); const fs = require('fs'); const path = require('path');
const types = { '.html': 'text/html', '.js': 'text/javascript', '.svg': 'image/svg+xml', '.mp3': 'audio/mpeg', '.pdf': 'application/pdf', '.css': 'text/css' };
module.exports.start = function (root = path.resolve('www')) {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      const p = path.join(root, decodeURIComponent(req.url.split('?')[0]) === '/' ? 'index.html' : decodeURIComponent(req.url.split('?')[0]));
      fs.readFile(p, (err, data) => {
        if (err) { res.writeHead(404); res.end(); return; }
        res.writeHead(200, { 'content-type': types[path.extname(p)] || 'application/octet-stream' }); res.end(data);
      });
    }).listen(0, '127.0.0.1', () => resolve({ url: `http://127.0.0.1:${srv.address().port}/`, close: () => srv.close() }));
  });
};
