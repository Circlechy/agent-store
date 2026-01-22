import asyncio
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

from registration_agent.app import RegistrationApp


app = RegistrationApp()
WEB_ROOT = Path(__file__).resolve().parent / "web"


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_bytes(self, *, code: int, data: bytes, content_type: str):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path in ("/", "/index.html"):
            index_path = WEB_ROOT / "index.html"
            if not index_path.exists():
                self._send(404, {"error": "missing web/index.html"})
                return
            data = index_path.read_bytes()
            self._send_bytes(code=200, data=data, content_type="text/html; charset=utf-8")
            return

        if parsed.path.startswith("/web/"):
            rel = parsed.path[len("/web/"):]
            file_path = (WEB_ROOT / rel).resolve()
            if WEB_ROOT not in file_path.parents or not file_path.exists() or file_path.is_dir():
                self._send(404, {"error": "not found"})
                return
            data = file_path.read_bytes()
            if file_path.suffix == ".css":
                ct = "text/css; charset=utf-8"
            elif file_path.suffix == ".js":
                ct = "application/javascript; charset=utf-8"
            elif file_path.suffix == ".svg":
                ct = "image/svg+xml"
            else:
                ct = "application/octet-stream"
            self._send_bytes(code=200, data=data, content_type=ct)
            return

        self._send(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path not in ("/session", "/step"):
            self._send(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            self._send(400, {"error": "invalid json"})
            return

        if parsed.path == "/session":
            sid = app.new_session()
            self._send(200, {"session_id": sid})
            return

        # /step
        session_id = payload.get("session_id")
        if not session_id:
            self._send(400, {"error": "missing session_id"})
            return

        # run async step
        try:
            loop = asyncio.new_event_loop()
            try:
                res = loop.run_until_complete(app.step(session_id=session_id, payload=payload))
            finally:
                loop.close()
        except Exception as e:
            self._send(500, {"error": str(e)})
            return

        self._send(200, res)


def main():
    server = HTTPServer(("127.0.0.1", 8080), Handler)
    print("HTTP server listening on http://127.0.0.1:8080")
    print("Open UI: http://127.0.0.1:8080/")
    print("POST /session -> {session_id}")
    print("POST /step -> drive the state machine")
    server.serve_forever()


if __name__ == "__main__":
    main()
