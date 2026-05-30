"""Tests for the thin CLI script modules (importable functions only).

The network-bound ``main()`` paths are out of scope here; we exercise the
pure/injectable helpers each script exposes.
"""

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import collect_pitchers
import scheduleFetcher
import statsCollector


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


class StatsCollectorFallbackTests(unittest.TestCase):
    def test_fallback_copies_latest_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            cwd = os.getcwd()
            os.chdir(d)
            try:
                snap = Path(d) / "data" / "rawData" / "05-29-26"
                snap.mkdir(parents=True)
                (snap / "team_batting_stats.csv").write_text("x", encoding="utf-8")
                statsCollector._fallback_to_local_data()
                self.assertTrue((Path(d) / "team_batting_stats.csv").exists())
            finally:
                os.chdir(cwd)

    def test_fallback_no_rawdata_is_graceful(self):
        with tempfile.TemporaryDirectory() as d:
            cwd = os.getcwd()
            os.chdir(d)
            try:
                statsCollector._fallback_to_local_data()  # must not raise
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
