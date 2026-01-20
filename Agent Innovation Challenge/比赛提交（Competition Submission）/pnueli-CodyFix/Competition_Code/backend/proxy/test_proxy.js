const http = require('http');
const { spawn } = require('child_process');

function startTestTarget() {
  const server = http.createServer((req, res) => {
    if (req.url === '/echo') {
      const chunks = [];
      req.on('data', (c) => chunks.push(c));
      req.on('end', () => {
        const body = Buffer.concat(chunks).toString();
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ method: req.method, headers: req.headers, body }));
      });
      req.on('error', () => res.writeHead(500).end());
      return;
    }

    if (req.url === '/slow') {
      // delay 2s
      setTimeout(() => {
        res.writeHead(200, { 'Content-Type': 'text/plain' });
        res.end('done');
      }, 2000);
      return;
    }

    res.writeHead(404).end('not found');
  });

  return new Promise((resolve) => server.listen(4001, () => resolve(server)));
}

function waitForProxyStart(cp, timeout = 3000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Proxy did not start in time')), timeout);
    cp.stdout.on('data', (chunk) => {
      const s = String(chunk);
      if (s.includes('Proxy server listening')) {
        clearTimeout(timer);
        resolve();
      }
    });
    cp.on('exit', (code) => reject(new Error('Proxy exited early: ' + code)));
  });
}

function postJson(port, path, body) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify(body);
    const req = http.request({ method: 'POST', hostname: '127.0.0.1', port, path, headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload) } }, (res) => {
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => resolve({ statusCode: res.statusCode, body: Buffer.concat(chunks).toString() }));
      res.on('error', reject);
    });
    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

(async () => {
  const target = await startTestTarget();
  const cp = spawn('node', ['proxy.js'], { env: { ...process.env, PORT: '3001' }, stdio: ['ignore', 'pipe', 'pipe'] });

  try {
    await waitForProxyStart(cp);
    console.log('Proxy started — running tests');

    // Test 1: echo (POST)
    const t1 = await postJson(3001, '/proxyToJson', { url: 'http://127.0.0.1:4001/echo', method: 'POST', body: { hello: 'world' } });
    const p1 = JSON.parse(t1.body);
    if (p1.responseCode !== 200) throw new Error('Echo test failed: responseCode != 200');
    if (!p1.responseText.includes('hello')) throw new Error('Echo test failed: body missing');
    console.log('Echo test passed');

    // Test 1.5: echo via GET (query params)
    const params = new URLSearchParams({
      url: 'http://127.0.0.1:4001/echo',
      method: 'POST',
      headers: JSON.stringify({ 'X-Test': 'abc' }),
      body: JSON.stringify({ hello: 'fromget' }),
    });
    const path = '/proxyToJson?' + params.toString();
    const t1b = await new Promise((resolve, reject) => {
      http.get({ hostname: '127.0.0.1', port: 3001, path }, (res) => {
        const chunks = [];
        res.on('data', (c) => chunks.push(c));
        res.on('end', () => resolve({ statusCode: res.statusCode, body: Buffer.concat(chunks).toString() }));
        res.on('error', reject);
      }).on('error', reject);
    });
    const p1b = JSON.parse(t1b.body);
    if (p1b.responseCode !== 200) throw new Error('GET echo test failed: responseCode != 200');
    if (!p1b.responseText.includes('fromget')) throw new Error('GET echo test failed: body missing');
    console.log('GET echo test passed');

    // Test 2: timeout
    const t2 = await postJson(3001, '/proxyToJson', { url: 'http://127.0.0.1:4001/slow', method: 'GET', timeoutMs: 500, retries: 0 });
    const p2 = JSON.parse(t2.body);
    if (t2.statusCode !== 502) throw new Error('Timeout test failed: expected 502');
    if (!p2.responseText.toLowerCase().includes('timed')) throw new Error('Timeout test failed: unexpected message');
    console.log('Timeout test passed');

    console.log('All tests passed');
    process.exit(0);
  } catch (err) {
    console.error('Test failed:', err);
    process.exit(1);
  } finally {
    target.close();
    cp.kill();
  }
})();