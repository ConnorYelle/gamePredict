"""A tiny stdlib HTTP server that powers the live matchup dashboard.

Two routes, no dependencies:

* ``GET /``           -> the dashboard page (``templates/dashboard.html``)
* ``GET /api/live``   -> the JSON payload from :func:`mlb.live.build_live_payload`

The browser can't poll the MLB Stats API directly (it's a ``file://`` page and
the API sends no CORS headers), so this server is the bridge: the page fetches
``/api/live`` on load and every 30s, and this server fetches MLB on its behalf.
Live responses are cached for ``ttl`` seconds and the last good payload is kept,
so a burst of viewers (or a transient API hiccup) never hammers or breaks the
page. ``payload_provider`` can be injected to bypass the network entirely in
tests.
"""

import json
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import config
from .live import build_live_payload
from .stats_api import MlbStatsApi

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "dashboard.html"
DEFAULT_PREDICTIONS = config.ROOT / "outputs" / "predictions.txt"


class LiveDashboard:
    """Holds the dashboard's data sources and a short-lived payload cache.

    The handler is intentionally dumb; all the policy (what to fetch, how long
    to cache, how to degrade) lives here so it can be unit-tested directly.
    """

    def __init__(self, api=None, predictions_path=DEFAULT_PREDICTIONS,
                 date_fn=None, ttl=20.0, payload_provider=None,
                 template_path=TEMPLATE_PATH, stats_dir=None):
        self.api = api or MlbStatsApi()
        self.predictions_path = Path(predictions_path)
        self.date_fn = date_fn or (lambda: datetime.now().strftime("%Y-%m-%d"))
        self.ttl = ttl
        self.payload_provider = payload_provider
        self.template_path = Path(template_path)
        self.stats_dir = stats_dir
        self._cache = None
        self._cache_at = 0.0
        self._last_good = None
        self._lock = threading.Lock()

    def _fresh_payload(self):
        if self.payload_provider is not None:
            return self.payload_provider()
        return build_live_payload(self.api, self.predictions_path,
                                  self.date_fn(), self.stats_dir)

    def payload(self):
        """Return the live payload, served from cache within ``ttl`` seconds.

        On an unexpected failure the last good payload is reused (flagged with
        an ``error``) rather than surfacing a 500 to the page."""
        with self._lock:
            now = time.monotonic()
            if self._cache is not None and now - self._cache_at < self.ttl:
                return self._cache
            try:
                payload = self._fresh_payload()
                self._cache, self._cache_at = payload, now
                self._last_good = payload
                return payload
            except Exception as exc:
                if self._last_good is not None:
                    stale = dict(self._last_good)
                    stale["error"] = f"Live refresh failed: {exc}"
                    return stale
                return {"date": self.date_fn(), "error": str(exc), "games": []}

    def template(self):
        """Read the dashboard HTML (read per-request so edits show on reload)."""
        return self.template_path.read_text(encoding="utf-8")


def _make_handler(dashboard):
    class Handler(BaseHTTPRequestHandler):
        server_version = "gamePredictLive/1.0"

        def _send(self, status, body, content_type):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                try:
                    self._send(200, dashboard.template(), "text/html; charset=utf-8")
                except OSError:
                    self._send(500, "Dashboard template missing", "text/plain")
            elif path == "/api/live":
                body = json.dumps(dashboard.payload())
                self._send(200, body, "application/json")
            else:
                self._send(404, "Not found", "text/plain")

        do_HEAD = do_GET

        def log_message(self, fmt, *args):  # quieter than the noisy default
            pass

    return Handler


def make_server(host="127.0.0.1", port=8000, dashboard=None, **kwargs):
    """Create (but don't start) a ``ThreadingHTTPServer`` for the dashboard.

    Pass an existing ``dashboard`` or kwargs forwarded to :class:`LiveDashboard`
    (e.g. ``payload_provider`` in tests). Port 0 binds an ephemeral port, which
    tests read back from ``server.server_address``.
    """
    dashboard = dashboard or LiveDashboard(**kwargs)
    return ThreadingHTTPServer((host, port), _make_handler(dashboard))


def serve(host="127.0.0.1", port=8000, open_browser=True, **kwargs):
    """Start the dashboard server and block until interrupted."""
    server = make_server(host, port, **kwargs)
    actual_port = server.server_address[1]
    url = f"http://{host}:{actual_port}/"
    print(f"Live dashboard at {url}  (Ctrl+C to stop)")
    if open_browser:
        import webbrowser
        threading.Thread(target=lambda: webbrowser.open(url), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping live dashboard.")
    finally:
        server.shutdown()
        server.server_close()
