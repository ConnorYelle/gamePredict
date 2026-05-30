"""Tests for mlb.trainer.WeightTrainer — log-loss, coordinate descent, helpers."""

import io
import math
import unittest
from contextlib import redirect_stdout

from mlb import config
from mlb.trainer import WeightTrainer, season_window
from tests.test_backtester import TEAMS, FakeApi


def neutral_inputs(n_home_wins, n_away_wins):
    """Games with empty team dicts -> model always returns p=0.5."""
    games = []
    for _ in range(n_home_wins):
        games.append({"home": {}, "away": {}, "home_sp": None,
                      "away_sp": None, "home_won": True})
    for _ in range(n_away_wins):
        games.append({"home": {}, "away": {}, "home_sp": None,
                      "away_sp": None, "home_won": False})
    return games


class SeasonWindowTests(unittest.TestCase):
    def test_full_season_window(self):
        self.assertEqual(season_window(2024), ("2024-03-01", "2024-11-30"))


class LogLossTests(unittest.TestCase):
    def test_empty_inputs_is_infinite(self):
        self.assertEqual(WeightTrainer.log_loss([], config.DEFAULT_WEIGHTS),
                         float("inf"))

    def test_neutral_probability_log_loss(self):
        inputs = neutral_inputs(2, 2)
        self.assertAlmostEqual(
            WeightTrainer.log_loss(inputs, config.DEFAULT_WEIGHTS),
            -math.log(0.5), places=9)

    def test_confident_correct_beats_confident_wrong(self):
        # Strong home that won should give lower loss than the same team losing.
        right = [{"home": TEAMS[10], "away": {}, "home_sp": None,
                  "away_sp": None, "home_won": True}]
        wrong = [{"home": TEAMS[10], "away": {}, "home_sp": None,
                  "away_sp": None, "home_won": False}]
        self.assertLess(WeightTrainer.log_loss(right, config.DEFAULT_WEIGHTS),
                        WeightTrainer.log_loss(wrong, config.DEFAULT_WEIGHTS))


class OptimizeTests(unittest.TestCase):
    def setUp(self):
        self.trainer = WeightTrainer(api=object())

    def test_optimize_never_worsens_loss(self):
        # Separable-ish set: strong home wins, strong away (as home) loses.
        inputs = (
            [{"home": TEAMS[10], "away": TEAMS[20], "home_sp": None,
              "away_sp": None, "home_won": True}] * 5
            + [{"home": TEAMS[20], "away": TEAMS[10], "home_sp": None,
                "away_sp": None, "home_won": False}] * 5
        )
        init = dict(config.DEFAULT_WEIGHTS)
        start = self.trainer.log_loss(inputs, init)
        learned, best = self.trainer.optimize(inputs, init, iters=10)
        self.assertLessEqual(best, start + 1e-9)
        self.assertEqual(set(learned), set(init))

    def test_optimize_is_deterministic(self):
        inputs = neutral_inputs(3, 1)
        a, _ = self.trainer.optimize(inputs, dict(config.DEFAULT_WEIGHTS), iters=5)
        b, _ = self.trainer.optimize(inputs, dict(config.DEFAULT_WEIGHTS), iters=5)
        self.assertEqual(a, b)


class CollectInputsTests(unittest.TestCase):
    def test_aggregates_across_seasons(self):
        games = [{"date": "d", "home_id": 10, "away_id": 20,
                  "home_won": True, "home_sp_id": None, "away_sp_id": None}]
        trainer = WeightTrainer(api=FakeApi(TEAMS, games))
        out = io.StringIO()
        with redirect_stdout(out):
            inputs = trainer.collect_inputs([2023, 2024], use_pitchers=False)
        self.assertEqual(len(inputs), 2)  # one game per season
        self.assertIn("loading 2023", out.getvalue())


class ReportTests(unittest.TestCase):
    def test_report_prints_metrics(self):
        trainer = WeightTrainer(api=object())
        inputs = neutral_inputs(1, 1)
        out = io.StringIO()
        with redirect_stdout(out):
            trainer.report("val", inputs, config.DEFAULT_WEIGHTS)
        text = out.getvalue()
        self.assertIn("accuracy", text)
        self.assertIn("Brier", text)


if __name__ == "__main__":
    unittest.main()
