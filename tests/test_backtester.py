"""Tests for mlb.backtester — input assembly, metric math, and report output."""

import io
import math
import unittest
from contextlib import redirect_stdout

from mlb import backtester, config


class FakeApi:
    """Minimal MlbStatsApi stand-in for build_game_inputs."""

    def __init__(self, team_stats, games, season_stats=None, recent=2.0):
        self._team_stats = team_stats
        self._games = games
        self._season_stats = season_stats or {}
        self._recent = recent
        self.recent_calls = []

    def team_model_stats(self, season, use_cache=False):
        return self._team_stats

    def season_games(self, start, end, season, use_cache=False):
        return self._games

    def pitcher_season_stats(self, pid, season, use_cache=False):
        return self._season_stats.get(pid)

    def recent_era(self, pid, season, before_date=None, use_cache=False):
        self.recent_calls.append((pid, before_date))
        return self._recent


TEAMS = {
    10: {"runsPerGame": 5.0, "onBasePercentage": 0.33, "sluggingPercentage": 0.44,
         "runsAllowedPerGame": 4.0, "fieldingPercentage": 0.985},
    20: {"runsPerGame": 4.0, "onBasePercentage": 0.30, "sluggingPercentage": 0.39,
         "runsAllowedPerGame": 4.5, "fieldingPercentage": 0.980},
}


class BuildGameInputsTests(unittest.TestCase):
    def test_basic_assembly_with_pitchers(self):
        games = [{"date": "2025-05-01", "home_id": 10, "away_id": 20,
                  "home_won": True, "home_sp_id": 1, "away_sp_id": 2}]
        api = FakeApi(TEAMS, games,
                      season_stats={1: {"era": 3.0, "whip": 1.1, "k9": 9.0},
                                    2: {"era": 4.0, "whip": 1.3, "k9": 7.0}})
        inputs = backtester.build_game_inputs(api, 2025, "a", "b", use_pitchers=True)
        self.assertEqual(len(inputs), 1)
        self.assertEqual(inputs[0]["home"], TEAMS[10])
        self.assertEqual(inputs[0]["home_sp"]["recentEra"], 2.0)
        self.assertTrue(inputs[0]["home_won"])

    def test_skips_games_with_unknown_team(self):
        games = [{"date": "d", "home_id": 10, "away_id": 999,
                  "home_won": True, "home_sp_id": None, "away_sp_id": None}]
        inputs = backtester.build_game_inputs(FakeApi(TEAMS, games), 2025, "a", "b")
        self.assertEqual(inputs, [])

    def test_no_pitchers_flag_yields_none(self):
        games = [{"date": "d", "home_id": 10, "away_id": 20,
                  "home_won": False, "home_sp_id": 1, "away_sp_id": 2}]
        api = FakeApi(TEAMS, games, season_stats={1: {"era": 3.0}})
        inputs = backtester.build_game_inputs(api, 2025, "a", "b", use_pitchers=False)
        self.assertIsNone(inputs[0]["home_sp"])
        self.assertIsNone(inputs[0]["away_sp"])
        self.assertEqual(api.recent_calls, [])

    def test_missing_pitcher_stats_yield_none(self):
        games = [{"date": "d", "home_id": 10, "away_id": 20,
                  "home_won": True, "home_sp_id": 7, "away_sp_id": None}]
        api = FakeApi(TEAMS, games, season_stats={})  # pid 7 unknown
        inputs = backtester.build_game_inputs(api, 2025, "a", "b")
        self.assertIsNone(inputs[0]["home_sp"])
        self.assertIsNone(inputs[0]["away_sp"])


class EvaluateTests(unittest.TestCase):
    def test_empty_inputs(self):
        res = backtester.evaluate([], config.DEFAULT_WEIGHTS)
        self.assertEqual(res["games_evaluated"], 0)
        self.assertEqual(res["accuracy"], 0.0)
        self.assertEqual(res["brier_score"], 0.0)

    def test_bookkeeping_with_neutral_probability(self):
        # Empty team dicts -> home_win_probability == 0.5 for every game.
        inputs = [
            {"home": {}, "away": {}, "home_sp": None, "away_sp": None, "home_won": True},
            {"home": {}, "away": {}, "home_sp": None, "away_sp": None, "home_won": False},
        ]
        res = backtester.evaluate(inputs, config.DEFAULT_WEIGHTS)
        self.assertEqual(res["games_evaluated"], 2)
        self.assertEqual(res["accuracy"], 0.5)          # p>=0.5 picks home both times
        self.assertEqual(res["home_field_baseline"], 0.5)
        self.assertAlmostEqual(res["average_winner_prob"], 0.5)
        self.assertAlmostEqual(res["brier_score"], 0.25)
        # p=0.5 every game -> per-game log-loss is -ln(0.5).
        self.assertAlmostEqual(res["log_loss"], -math.log(0.5))

    def test_accuracy_when_model_is_right(self):
        # Strong home team that actually won -> correct, high winner prob.
        inputs = [{"home": TEAMS[10], "away": {}, "home_sp": None,
                   "away_sp": None, "home_won": True}]
        res = backtester.evaluate(inputs, config.DEFAULT_WEIGHTS)
        self.assertEqual(res["accuracy"], 1.0)
        self.assertGreater(res["average_winner_prob"], 0.9)


class RunBacktestTests(unittest.TestCase):
    def test_reports_metrics(self):
        games = [{"date": "d", "home_id": 10, "away_id": 20,
                  "home_won": True, "home_sp_id": None, "away_sp_id": None}]
        api = FakeApi(TEAMS, games)
        out = io.StringIO()
        with redirect_stdout(out):
            backtester.run_backtest(2025, "a", "b", use_pitchers=False, api=api)
        text = out.getvalue()
        self.assertIn("Model accuracy:", text)
        self.assertIn("Games evaluated:     1", text)

    def test_handles_no_games(self):
        api = FakeApi(TEAMS, [])
        out = io.StringIO()
        with redirect_stdout(out):
            backtester.run_backtest(2025, "a", "b", use_pitchers=False, api=api)
        self.assertIn("No completed games", out.getvalue())


if __name__ == "__main__":
    unittest.main()
