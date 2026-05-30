"""Shared test doubles. Named with a leading underscore so unittest's
``test*.py`` discovery never collects it as a test module."""


class FakeClient:
    """Stand-in for ``mlb.http_client.JsonHttpClient``.

    Maps URLs (or URL substrings) to canned JSON payloads so ``MlbStatsApi`` can
    be exercised without touching the network. Records every requested URL.
    """

    def __init__(self, responses=None, default=None):
        # responses: dict of {url_substring: payload}
        self.responses = responses or {}
        self.default = default if default is not None else {}
        self.calls = []

    def get_json(self, url, use_cache=False):
        self.calls.append((url, use_cache))
        for needle, payload in self.responses.items():
            if needle in url:
                if isinstance(payload, Exception):
                    raise payload
                return payload
        if isinstance(self.default, Exception):
            raise self.default
        return self.default


def stats_group(splits):
    """Wrap split dicts in the ``{"stats": [{"splits": [...]}]}`` envelope the
    MLB Stats API uses for team/pitcher stat responses."""
    return {"stats": [{"splits": splits}]}


def schedule_payload(dates):
    """Wrap day dicts in the ``{"dates": [...]}`` schedule envelope."""
    return {"dates": dates}
