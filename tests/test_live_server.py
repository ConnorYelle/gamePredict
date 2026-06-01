"""Tests for mlb.live_server -- the dashboard HTTP server.

Starts the real ThreadingHTTPServer on an ephemeral port with an injected
payload_provider (no network, no MLB API), then exercises the routes over real
HTTP so the request handling and cache behaviour are covered end to end.
"""

import json
import threading
import unittest
import urllib.request
from urllib.error import HTTPError

from mlb import live_server


class ServerTestBase(unittest.TestCase):
    def make(self, **kwargs):
        kwargs.setdefault("payload_provider", lambda: {"date": "2026-05-31",
                                                       "error": None, "games": []})
        self.server = live_server.make_server("127.0.0.1", 0, **kwargs)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()
        self.addCleanup(self._shutdown)
        return f"http://127.0.0.1:{self.port}"

    def _shutdown(self):
        self.server.shutdown()
        self.server.server_close()

    @staticmethod
    def get(url):
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read().decode()


class RouteTests(ServerTestBase):
    def test_root_serves_html(self):
        base = self.make()
        status, ctype, body = self.get(base + "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ctype)
        self.assertIn("MLB Live Predictions", body)
        self.assertIn("/api/live", body)  # the page polls this route

    def test_api_live_serves_json(self):
        base = self.make()
        status, ctype, body = self.get(base + "/api/live")
        self.assertEqual(status, 200)
        self.assertIn("application/json", ctype)
        self.assertEqual(json.loads(body)["date"], "2026-05-31")

    def test_unknown_route_404s(self):
        base = self.make()
        with self.assertRaises(HTTPError) as cm:
            self.get(base + "/nope")
        self.assertEqual(cm.exception.code, 404)


class CacheTests(ServerTestBase):
    def test_payload_cached_within_ttl(self):
        calls = {"n": 0}

        def provider():
            calls["n"] += 1
            return {"date": "d", "error": None, "games": []}

        base = self.make(payload_provider=provider, ttl=60)
        self.get(base + "/api/live")
        self.get(base + "/api/live")
        self.assertEqual(calls["n"], 1)  # second request hit the cache

    def test_stale_payload_reused_on_failure(self):
        state = {"fail": False}

        def provider():
            if state["fail"]:
                raise RuntimeError("api down")
            return {"date": "d", "error": None, "games": [{"home": "x"}]}

        # ttl=0 forces a refresh on every request.
        base = self.make(payload_provider=provider, ttl=0)
        self.get(base + "/api/live")  # primes last-good
        state["fail"] = True
        _, _, body = self.get(base + "/api/live")
        payload = json.loads(body)
        self.assertIn("api down", payload["error"])
        self.assertEqual(payload["games"], [{"home": "x"}])  # stale reused


if __name__ == "__main__":
    unittest.main()
