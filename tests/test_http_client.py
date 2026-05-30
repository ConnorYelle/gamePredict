"""Tests for mlb.http_client.JsonHttpClient — HTTP gateway + disk cache."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mlb.http_client import JsonHttpClient


class _FakeResponse(io.BytesIO):
    """Context-manager byte stream mimicking urlopen's return value."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_urlopen(payload):
    body = json.dumps(payload).encode("utf-8")
    return mock.Mock(side_effect=lambda *a, **k: _FakeResponse(body))


class JsonHttpClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "cache"
        self.client = JsonHttpClient(self.cache)

    def tearDown(self):
        self.tmp.cleanup()

    def test_fetches_and_parses_json(self):
        with mock.patch("mlb.http_client.urllib.request.urlopen",
                        fake_urlopen({"hello": "world"})):
            data = self.client.get_json("http://x/api")
        self.assertEqual(data, {"hello": "world"})

    def test_no_cache_does_not_write_file(self):
        with mock.patch("mlb.http_client.urllib.request.urlopen",
                        fake_urlopen({"a": 1})):
            self.client.get_json("http://x/api", use_cache=False)
        self.assertFalse(self.cache.exists())

    def test_cache_miss_then_write(self):
        urlopen = fake_urlopen({"v": 1})
        with mock.patch("mlb.http_client.urllib.request.urlopen", urlopen):
            self.client.get_json("http://x/cached", use_cache=True)
        cached = list(self.cache.glob("*.json"))
        self.assertEqual(len(cached), 1)
        self.assertEqual(urlopen.call_count, 1)

    def test_cache_hit_skips_network(self):
        urlopen = fake_urlopen({"v": 42})
        with mock.patch("mlb.http_client.urllib.request.urlopen", urlopen):
            first = self.client.get_json("http://x/cached", use_cache=True)
            second = self.client.get_json("http://x/cached", use_cache=True)
        self.assertEqual(first, second)
        self.assertEqual(urlopen.call_count, 1)  # second served from disk

    def test_corrupt_cache_entry_refetches(self):
        # Pre-seed a corrupt cache file for the URL.
        self.cache.mkdir(parents=True, exist_ok=True)
        import hashlib
        url = "http://x/corrupt"
        key = hashlib.md5(url.encode("utf-8")).hexdigest()
        (self.cache / f"{key}.json").write_text("{ broken", encoding="utf-8")

        urlopen = fake_urlopen({"recovered": True})
        with mock.patch("mlb.http_client.urllib.request.urlopen", urlopen):
            data = self.client.get_json(url, use_cache=True)
        self.assertEqual(data, {"recovered": True})
        self.assertEqual(urlopen.call_count, 1)

    def test_distinct_urls_get_distinct_cache_files(self):
        with mock.patch("mlb.http_client.urllib.request.urlopen",
                        fake_urlopen({"v": 1})):
            self.client.get_json("http://x/one", use_cache=True)
            self.client.get_json("http://x/two", use_cache=True)
        self.assertEqual(len(list(self.cache.glob("*.json"))), 2)


if __name__ == "__main__":
    unittest.main()
