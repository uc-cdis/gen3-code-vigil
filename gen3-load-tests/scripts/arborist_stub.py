"""Lightweight mock Arborist service for local testing."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class ArboristStubHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        """Respond to health checks from ArboristClient."""
        path = self.path.split("?")[0]
        if path in ["/_health", "/health", "/", "/_status"]:
            body = json.dumps({"status": "healthy"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        """Respond to authz policy checks and mappings."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            _ = self.rfile.read(content_length)

        path = self.path.split("?")[0]
        if path == "/auth/request":
            payload = {"auth": True}
        elif path == "/auth/mapping":
            payload = {
                "/fhir/Patient": [{"service": "gen3-fhir-proxy", "method": "read"}]
            }
        else:
            payload = {}

        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = ThreadedHTTPServer(("0.0.0.0", 8081), ArboristStubHandler)
    print("Mock Arborist server running on http://localhost:8081")
    server.serve_forever()
