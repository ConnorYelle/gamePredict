"""Tests for the thin CLI script modules (importable functions only).

The network-bound ``main()`` paths are out of scope here; we exercise the
pure/injectable helpers each script exposes.
"""

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import collect_pitchers
import scheduleFetcher
import statsCollector
from mlb import config, raw_stats


class FakeScheduleApi:
    def __init__(self, games):
        self._games = games

    def scheduled_games(self, date_str):
        return self._games


class ScheduleFetcherTests(unittest.TestCase):
    def test_formats_games_with_starters(self):
        api = FakeScheduleApi([
            {"home": "Boston Red Sox", "away": "New York Yankees",
             "home_sp": "Ace H", "away_sp": "Ace A"},
        ])
        lines = scheduleFetcher.fetch_games(api, "2026-05-30")
        self.assertEqual(lines,
                         ["Boston Red Sox | New York Yankees | Ace H | Ace A"])

    def test_fetch_handles_api_error(self):
        class Boom:
            def scheduled_games(self, d):
                raise RuntimeError("down")
        self.assertEqual(scheduleFetcher.fetch_games(Boom(), "2026-05-30"), [])

    def test_save_games_writes_file(self):
        with tempfile.TemporaryDirectory() as d:
            cwd = os.getcwd()
            os.chdir(d)
            try:
                scheduleFetcher.save_games(["A | B | | "])
                out = Path(d) / "outputs" / "games.txt"
                self.assertTrue(out.exists())
                self.assertEqual(out.read_text(encoding="utf-8"), "A | B | | \n")
            finally:
                os.chdir(cwd)


class FakePitcherApi:
    def probable_starters(self, date_str):
        return {1: "Ace One", 2: "Ace Two"}

    def pitcher_season_stats(self, pid, season):
        return {"era": 2.5, "whip": 1.1, "k9": 9.0} if pid == 1 else None

    def recent_era(self, pid, season):
        return 3.0 if pid == 1 else -1.0


class CollectPitchersTests(unittest.TestCase):
    def test_fmt_blanks_unknown(self):
        self.assertEqual(collect_pitchers._fmt(None), "")
        self.assertEqual(collect_pitchers._fmt(-1.0), "")
        self.assertEqual(collect_pitchers._fmt(2.5), "2.500")

    def test_collect_rows(self):
        rows = collect_pitchers.collect_starting_pitchers(
            FakePitcherApi(), datetime(2026, 5, 30))
        self.assertEqual(len(rows), 2)
        ace = next(r for r in rows if r["name"] == "Ace One")
        self.assertEqual(ace["era"], "2.500")
        self.assertEqual(ace["recentEra"], "3.000")
        # pitcher 2 has no season stats -> blank fields
        other = next(r for r in rows if r["name"] == "Ace Two")
        self.assertEqual(other["era"], "")

    def test_collect_handles_schedule_error(self):
        class Boom:
            def probable_starters(self, d):
                raise RuntimeError("nope")
        rows = collect_pitchers.collect_starting_pitchers(
            Boom(), datetime(2026, 5, 30))
        self.assertEqual(rows, [])


class FakeStandardApi:
    """team_standard_stats stand-in that counts how often it is called."""

    def __init__(self, teams=None, raises=None):
        self.teams = teams if teams is not None else {
            10: {"name": "Boston Red Sox", "runsPerGame": 4.5, "battingAvg": 0.265,
                 "onBasePercentage": 0.330, "sluggingPercentage": 0.430,
                 "homeRuns": 60, "runsAllowedPerGame": 4.0, "fieldingPercentage": 0.985},
            20: {"name": "New York Yankees", "runsPerGame": 5.1, "battingAvg": 0.255,
                 "onBasePercentage": 0.322, "sluggingPercentage": 0.445,
                 "homeRuns": 71, "runsAllowedPerGame": 3.8, "fieldingPercentage": 0.982},
        }
        self.raises = raises
        self.calls = 0

    def team_standard_stats(self, season, use_cache=False):
        self.calls += 1
        if self.raises:
            raise self.raises
        return self.teams


class StatsCollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # Redirect config.ROOT so writes land in the temp tree, not the repo.
        self.patch = mock.patch.object(config, "ROOT", Path(self.tmp.name))
        self.patch.start()
        self.today = datetime(2026, 5, 30)

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_writes_files_when_absent(self):
        api = FakeStandardApi()
        out_dir, wrote = statsCollector.collect_team_stats(api, self.today)
        self.assertTrue(wrote)
        self.assertTrue(raw_stats.is_populated(out_dir))
        self.assertEqual(api.calls, 1)

    def test_skips_when_already_collected(self):
        api = FakeStandardApi()
        statsCollector.collect_team_stats(api, self.today)        # first run writes
        out_dir, wrote = statsCollector.collect_team_stats(api, self.today)
        self.assertFalse(wrote)
        self.assertEqual(api.calls, 1)  # second run did NOT hit the API

    def test_force_refetches(self):
        api = FakeStandardApi()
        statsCollector.collect_team_stats(api, self.today)
        _, wrote = statsCollector.collect_team_stats(api, self.today, force=True)
        self.assertTrue(wrote)
        self.assertEqual(api.calls, 2)

    def test_api_error_is_graceful(self):
        api = FakeStandardApi(raises=RuntimeError("network down"))
        out_dir, wrote = statsCollector.collect_team_stats(api, self.today)
        self.assertFalse(wrote)
        self.assertFalse(raw_stats.is_populated(out_dir))  # nothing written


if __name__ == "__main__":
    unittest.main()
