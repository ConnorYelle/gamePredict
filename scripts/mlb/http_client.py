"""HTTP gateway with optional on-disk JSON caching.

A single ``JsonHttpClient`` is the only thing in the package that touches the
network, so retries, headers, timeouts, and caching are configured in one place.
Caching is keyed by URL and intended for immutable past-season data, which makes
repeated training/backtest runs fast.
"""

import hashlib
import json
import urllib.request


class JsonHttpClient:
    def __init__(self, cache_dir, user_agent="gamePrediction", timeout=60):
        self.cache_dir = cache_dir
        self.user_agent = user_agent
        self.timeout = timeout

    def get_json(self, url, use_cache=False):
        """GET ``url`` and parse JSON, optionally reading/writing a disk cache."""
        cache_file = None
        if use_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            key = hashlib.md5(url.encode("utf-8")).hexdigest()
            cache_file = self.cache_dir / f"{key}.json"
            if cache_file.exists():
                try:
                    return json.loads(cache_file.read_text(encoding="utf-8"))
                except ValueError:
                    pass  # corrupt cache entry -> refetch

        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if cache_file is not None:
            cache_file.write_text(json.dumps(data), encoding="utf-8")
        return data
