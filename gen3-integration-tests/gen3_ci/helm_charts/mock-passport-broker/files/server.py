#!/usr/bin/env python3
"""Minimal, dependency-free mock GA4GH passport broker for testing token exchange.

Signs the passport defined in generate_passport.py with an RSA private key and
serves:

    GET /openid/connect/v1.1/userinfo     {"sub": ..., "passport_jwt_v11": <passport>}
                                          (the RAS userinfo format; a freshly
                                          minted passport on every request)
    GET /.well-known/openid-configuration
    GET /.well-known/jwks.json            RFC 7517 JWKS with n/e
    GET /jwt/keys                         {"keys": [[kid, public_key_pem]]}
                                          (the fence / authutils format)
    GET /_status

Only the public half of the key is ever served. Configuration comes from the
environment: KEY_PATH, KID, ISSUER, PORT. KID defaults to the RFC 7638
thumbprint of the key.

Runs on the Python standard library only, so it needs no image build and no
network access at startup.
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from generate_passport import BASE_PASSPORT, generate_passport
from rs256 import RSAPrivateKey

# where fence's RAS login flow fetches a user's passport (RAS_USERINFO_ENDPOINT)
USERINFO_PATH = "/openid/connect/v1.1/userinfo"


def build_routes(private_key, kid, issuer):
    """Map each path to a function returning its JSON document."""
    jwks = {"keys": [private_key.public_jwk(kid)]}
    base = issuer.rstrip("/")
    openid_configuration = {
        "issuer": issuer,
        "jwks_uri": base + "/.well-known/jwks.json",
        "userinfo_endpoint": base + USERINFO_PATH,
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "scopes_supported": ["openid", "ga4gh_passport_v1"],
    }
    static_documents = {
        "/.well-known/openid-configuration": openid_configuration,
        "/.well-known/jwks.json": jwks,
        "/jwt/keys": {"keys": [[kid, private_key.public_key_pem()]]},
        "/_status": {"status": "ok", "issuer": issuer, "kid": kid},
    }
    routes = {
        path: (lambda document=document: document)
        for path, document in static_documents.items()
    }
    routes[USERINFO_PATH] = lambda: {
        "sub": BASE_PASSPORT["sub"],
        "passport_jwt_v11": generate_passport(private_key, issuer=issuer, kid=kid),
    }
    return routes


class Handler(BaseHTTPRequestHandler):
    server_version = "mock-passport-broker/1.0"
    routes = {}

    def _respond(self, status, payload):
        body = json.dumps(payload, indent=2).encode() + b"\n"
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _route(self):
        path = self.path.split("?", 1)[0]
        if len(path) > 1:
            path = path.rstrip("/")
        route = self.routes.get(path)
        if route is None:
            self._respond(404, {"error": "not found", "paths": sorted(self.routes)})
        else:
            self._respond(200, route())

    def do_GET(self):
        self._route()

    def do_HEAD(self):
        self._route()

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


def main():
    key_path = os.environ.get("KEY_PATH", "/signing-key/private_key.pem")
    issuer = os.environ["ISSUER"]
    port = int(os.environ.get("PORT", "8080"))

    with open(key_path) as handle:
        private_key = RSAPrivateKey.from_pem(handle.read())
    kid = os.environ.get("KID") or private_key.thumbprint()
    Handler.routes = build_routes(private_key, kid, issuer)

    print(
        "mock-passport-broker serving issuer=%s kid=%s on port %d"
        % (issuer, kid, port),
        flush=True,
    )
    print("paths: %s" % ", ".join(sorted(Handler.routes)), flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
