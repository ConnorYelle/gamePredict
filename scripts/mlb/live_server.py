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
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import config
from .live import build_history_payload, build_live_payload
from .results_archive import ResultsArchive, archive_day, parse_date
from .stats_api import MlbStatsApi

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "dashboard.html"
MATCHUP_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "matchup.html"
DEFAULT_PREDICTIONS = config.ROOT / "outputs" / "predictions.txt"


class LiveDashboard:
    """Holds the dashboard's data sources and a short-lived payload cache.

    The handler is intentionally dumb; all the policy (what to fetch, how long
    to cache, how to degrade) lives here so it can be unit-tested directly.
    """

    def __init__(self, api=None, predictions_path=DEFAULT_PREDICTIONS,
                 date_fn=None, ttl=20.0, payload_provider=None,
                 template_path=TEMPLATE_PATH, stats_dir=None,
                 archive=None, stats_root=None,
                 matchup_template_path=MATCHUP_TEMPLATE_PATH):
        self.api = api or MlbStatsApi()
        self.predictions_path = Path(predictions_path)
        self.date_fn = date_fn or (lambda: datetime.now().strftime("%Y-%m-%d"))
        self.ttl = ttl
        self.payload_provider = payload_provider
        self.template_path = Path(template_path)
        self.matchup_template_path = Path(matchup_template_path)
        self.stats_dir = stats_dir
        self.archive = archive or ResultsArchive()
        # Where per-day team-stat folders live (MM-DD-YY), used to populate the
        # matchup-detail panel for a historical day when that day's stats are
        # still on disk; otherwise the panel just reports stats unavailable.
        self.stats_root = (Path(stats_root) if stats_root
                           else config.ROOT / "data" / "rawData")
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

    def _history_stats_dir(self, date_str):
        """The data/rawData/<MM-DD-YY> folder for a date, if it's still on disk."""
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
        except (TypeError, ValueError):
            return None
        day_dir = self.stats_root / date.strftime("%m-%d-%y")
        return day_dir if day_dir.is_dir() else None

    def _ensure_results(self, date_str):
        """Best-effort: if a day has saved predictions but its finals aren't
        archived yet (e.g. yesterday), fetch and persist them so the picks can
        be graded. Silent on any failure -- the view degrades to ungraded."""
        try:
            date = parse_date(date_str)
        except (TypeError, ValueError):
            return
        if self.archive.load_scores(date):
            return  # already archived
        if not self.archive.load_predictions_text(date):
            return  # nothing to grade, no point fetching
        try:
            archive_day(self.api, date, self.archive)
        except Exception:
            pass

    def history(self, date_str):
        """Graded payload for a past day (no caching -- the archive is static)."""
        self._ensure_results(date_str)
        return build_history_payload(date_str, self.archive,
                                     self._history_stats_dir(date_str))

    def history_dates(self):
        """Reviewable past days for the picker: ``{"dates": [YYYY-MM-DD,...]}``.

        Today is excluded -- it's the live view, not a history entry."""
        today = self.date_fn()
        dates = [d for d in self.archive.available_dates() if d < today]
        return {"dates": dates}

    def matchup(self, date_str, away, home):
        """Single-matchup payload for the per-matchup page.

        Reuses the live or history payload for the date and isolates the one
        game, so the matchup page shows exactly what the dashboard card does
        (probabilities, score/result, starters, the stat comparison)."""
        if not date_str or date_str == self.date_fn():
            payload = self.payload()
        else:
            payload = self.history(date_str)
        game = next((g for g in payload.get("games", [])
                     if g.get("away") == away and g.get("home") == home), None)
        return {
            "date": payload.get("date", date_str),
            "mode": payload.get("mode"),
            "found": game is not None,
            "game": game,
        }

    def template(self):
        """Read the dashboard HTML (read per-request so edits show on reload)."""
        return self.template_path.read_text(encoding="utf-8")

    def matchup_template(self):
        """Read the per-matchup page HTML (read per-request for live edits)."""
        return self.matchup_template_path.read_text(encoding="utf-8")


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
            parsed = urllib.parse.urlsplit(self.path)
            path = parsed.path
            if path in ("/", "/index.html"):
                try:
                    self._send(200, dashboard.template(), "text/html; charset=utf-8")
                except OSError:
                    self._send(500, "Dashboard template missing", "text/plain")
            elif path == "/matchup":
                try:
                    self._send(200, dashboard.matchup_template(),
                               "text/html; charset=utf-8")
                except OSError:
                    self._send(500, "Matchup template missing", "text/plain")
            elif path == "/api/live":
                body = json.dumps(dashboard.payload())
                self._send(200, body, "application/json")
            elif path == "/api/history/dates":
                body = json.dumps(dashboard.history_dates())
                self._send(200, body, "application/json")
            elif path == "/api/history":
                qs = urllib.parse.parse_qs(parsed.query)
                date = (qs.get("date") or [""])[0]
                body = json.dumps(dashboard.history(date))
                self._send(200, body, "application/json")
            elif path == "/api/matchup":
                qs = urllib.parse.parse_qs(parsed.query)
                date = (qs.get("date") or [""])[0]
                away = (qs.get("away") or [""])[0]
                home = (qs.get("home") or [""])[0]
                body = json.dumps(dashboard.matchup(date, away, home))
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
