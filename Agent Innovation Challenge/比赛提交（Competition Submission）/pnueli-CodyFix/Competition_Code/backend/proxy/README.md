# Simple HTTP Proxy (proxyToJson)

Small Node.js proxy server that exposes a single endpoint:

POST /proxyToJson

Request JSON body (examples):
- url (string, required): target URL to call
- method (string, optional): HTTP method, default GET
- headers (object, optional): headers to add
- body (string or object, optional): body to send (object will be JSON-stringified)
- timeoutMs (number, optional): upstream timeout in ms (default 5000)
- retries (number, optional): number of retries on upstream failure (default 2)

Response JSON:
{ responseCode, responseText }
- responseCode: upstream HTTP status code, or -1 on error
- responseText: upstream response body (as string), or error message

Environment variables:
- PORT (default 3000)
- MAX_BODY_BYTES (default 1048576)
- DEFAULT_TIMEOUT_MS (default 5000)
- DEFAULT_RETRIES (default 2)

Run:

- Install dev tools (optional): `npm i -D nodemon`
- Start: `npm start` or `node proxy.js`
- Dev: `npm run dev`
- Test: `npm test` (runs a basic integration test)

Example POST curl:

curl -X POST http://localhost:3000/proxyToJson -H "Content-Type: application/json" \
  -d '{"url":"https://httpbin.org/get","method":"GET","headers":{"X-Test":"abc"}}'

GET usage (payload in URL query params):

# Values that are objects (headers, body) must be URL-encoded JSON strings
curl "http://localhost:3000/proxyToJson?url=http%3A%2F%2Flocalhost%3A4001%2Fecho&method=POST&headers=%7B%22X-Test%22%3A%22abc%22%7D&body=%7B%22hello%22%3A%22world%22%7D"

Note: URL-encode JSON strings in query params (or use a library to build URLs).
