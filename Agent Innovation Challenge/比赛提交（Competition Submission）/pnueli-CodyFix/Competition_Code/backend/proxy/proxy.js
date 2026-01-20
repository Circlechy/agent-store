#!/usr/bin/env node
const http = require('http');
const https = require('https');
const { URL } = require('url');

const PORT = process.env.PORT || 3000;
const MAX_BODY_BYTES = parseInt(process.env.MAX_BODY_BYTES, 10) || 1024 * 1024; // 1 MB
const DEFAULT_TIMEOUT_MS = parseInt(process.env.DEFAULT_TIMEOUT_MS, 10) || 5000;
const DEFAULT_RETRIES = parseInt(process.env.DEFAULT_RETRIES, 10) || 2;

function timestamp() {
  return new Date().toISOString();
}

function log(...args) {
  console.log(`[${timestamp()}]`, ...args);
}

function sendJson(res, statusCode, obj) {
  const payload = JSON.stringify(obj);
  const headers = {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(payload),
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  };
  res.writeHead(statusCode, headers);
  res.end(payload);
}

function collectRequestBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let received = 0;
    req.on('data', (c) => {
      received += c.length;
      if (received > MAX_BODY_BYTES) {
        // terminate connection on large payloads
        req.destroy(new Error('Request body too large'));
        return;
      }
      chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks).toString()));
    req.on('error', reject);
  });
}

function tryParseMaybeJsonOrHeaders(v) {
  if (v === undefined || v === null) return v;
  if (typeof v !== 'string') return v;

  // 1) Try strict JSON
  try {
    return JSON.parse(v);
  } catch (_) {}

  // 2) Try converting single quotes to double quotes (handles "{'A':'B'}")
  try {
    const alt = v.replace(/'/g, '"');
    return JSON.parse(alt);
  } catch (_) {}

  // 3) Try simple header/body list parsing: "A: B, C: D" or "A=B;C=D"
  const obj = {};
  const parts = v.split(/\s*[;,|&]\s*/);
  let found = false;
  for (const part of parts) {
    const m = part.match(/^\s*([^:=]+)\s*[:=]\s*(.+)\s*$/);
    if (m) {
      const key = m[1].trim();
      const val = m[2].trim();
      obj[key] = val;
      found = true;
    }
  }
  if (found) return obj;

  // Fallback: return original string (caller will decide)
  return v;
}

function parsePayloadFromQuery(searchParams) {
  const payload = {};
  for (const [k, v] of searchParams.entries()) {
    if (k === 'headers' || k === 'body') {
      payload[k] = tryParseMaybeJsonOrHeaders(v);
    } else if (k === 'timeoutMs' || k === 'retries') {
      const n = parseInt(v, 10);
      if (!Number.isNaN(n)) payload[k] = n;
    } else {
      payload[k] = v;
    }
  }
  return payload;
}

function proxyRequest({ targetUrl, method = 'GET', headers = {}, body, timeoutMs = DEFAULT_TIMEOUT_MS, retries = DEFAULT_RETRIES }) {
  return new Promise(async (resolve, reject) => {
    let urlObj;
    try {
      urlObj = new URL(targetUrl);
    } catch (err) {
      return reject(new Error('Invalid target URL'));
    }

    const isHttps = urlObj.protocol === 'https:';
    const requestModule = isHttps ? https : http;

    const optionsBase = {
      protocol: urlObj.protocol,
      hostname: urlObj.hostname,
      port: urlObj.port || (isHttps ? 443 : 80),
      path: urlObj.pathname + urlObj.search,
      method,
      headers: { ...headers },
    };

    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const result = await new Promise((innerResolve, innerReject) => {
          const options = { ...optionsBase };
          const req = requestModule.request(options, (resp) => {
            const chunks = [];
            resp.on('data', (c) => chunks.push(c));
            resp.on('end', () => {
              const text = Buffer.concat(chunks).toString();
              innerResolve({ statusCode: resp.statusCode, body: text, headers: resp.headers });
            });
            resp.on('error', (err) => innerReject(err));
          });

          req.on('error', (err) => innerReject(err));

          // timeout
          req.setTimeout(timeoutMs, () => {
            req.abort();
            const e = new Error('Upstream request timed out');
            e.code = 'ETIMEDOUT';
            innerReject(e);
          });

          if (body) {
            let str;
            if (typeof body === 'object') {
              str = JSON.stringify(body);
              if (!options.headers['content-type'] && !options.headers['Content-Type']) {
                req.setHeader('Content-Type', 'application/json');
              }
            } else {
              str = String(body);
            }
            req.setHeader('Content-Length', Buffer.byteLength(str));
            req.write(str);
          }

          req.end();
        });

        return resolve(result);
      } catch (err) {
        const isLast = attempt === retries;
        if (isLast) return reject(err);
        const backoff = 100 * Math.pow(2, attempt); // exponential backoff starting at 100ms
        await new Promise((r) => setTimeout(r, backoff));
        // retry
        continue;
      }
    }

    return reject(new Error('Unreachable'));
  });
}

const server = http.createServer(async (req, res) => {
  const parsedUrl = new URL(req.url, `http://${req.headers.host || 'localhost'}`);

  // Handle CORS preflight
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    });
    return res.end();
  }

  if (parsedUrl.pathname === '/proxyToJson' && (req.method === 'POST' || req.method === 'GET')) {
    log(`Incoming /proxyToJson ${req.method} request`);
    
    let payload;

    if (req.method === 'GET') {
        log(parsedUrl.searchParams);
      // parse payload from query params
      payload = parsePayloadFromQuery(parsedUrl.searchParams);
    } else {
      let raw;
      try {
        raw = await collectRequestBody(req);
      } catch (err) {
        log('Failed to read body:', err.message);
        return sendJson(res, 413, { responseCode: -1, responseText: `Failed to read request body: ${err.message}` });
      }

      try {
        payload = raw ? JSON.parse(raw) : {};
      } catch (err) {
        return sendJson(res, 400, { responseCode: -1, responseText: 'Invalid JSON in request body' });
      }
    }
    log('Payload:', payload);
    
    const { url: targetUrl, 
      method: proxyMethod = req.method, //'GET', 
      headers = { Authorization: "Basic YW1pcjoxMTFkY2Y5YWExOTRhMGViMmZkNjg5OTU5NWExODExOTU1"}, 
      body, timeoutMs = DEFAULT_TIMEOUT_MS, retries = DEFAULT_RETRIES } = payload;

    if (!targetUrl) {
      return sendJson(res, 400, { responseCode: -1, responseText: 'Missing "url" field in body' });
    }
    if (typeof headers !== 'object' || Array.isArray(headers)) {
      return sendJson(res, 400, { responseCode: -1, responseText: '"headers" must be an object' });
    }

    try {
      log(`Proxying to ${targetUrl} [method=${proxyMethod}] timeout=${timeoutMs} retries=${retries}`);
      const result = await proxyRequest({ targetUrl, method: proxyMethod, headers, body, timeoutMs, retries });
      log(`Proxied result: ${result.statusCode}`);
      return sendJson(res, 200, { responseCode: result.statusCode, responseText: result.body });
    } catch (err) {
      log('Proxy error:', err.message);
      return sendJson(res, 502, { responseCode: -1, responseText: err.message });
    }
  }

  // Not found
  sendJson(res, 404, { responseCode: -1, responseText: 'Not Found' });
});

server.listen(PORT, () => {
  console.log(`Proxy server listening on http://0.0.0.0:${PORT}`);
});

// Usage example (curl):
// curl -X POST http://localhost:3000/proxyToJson -H "Content-Type: application/json" \
//   -d '{"url":"https://httpbin.org/get","method":"GET","headers":{"X-Test":"abc"}}'
