"""Tests for mlb.model.PredictionModel — the win-probability formula.

These pin the exact arithmetic so the Python model stays a faithful port of
cpp/GamePredictor.cpp (the trainer/backtester rely on that parity).
"""

import unittest

from mlb import config
from mlb.model import PredictionModel

TEAM = {
    "runsPerGame": 4.5,
    "onBasePercentage": 0.320,
    "sluggingPercentage": 0.410,
    "runsAllowedPerGame": 4.0,
    "fieldingPercentage": 0.985,
}


class PitcherScoreTests(unittest.TestCase):
    def setUp(self):
        self.model = PredictionModel({
            "pitcherEraWeight": 2.0,
            "pitcherWhipWeight": 1.0,
            "pitcherK9Weight": 0.1,
            "pitcherRecentFormWeight": 0.5,
        })

    def test_none_pitcher_scores_zero(self):
        self.assertEqual(self.model.pitcher_score(None), 0.0)

    def test_empty_dict_scores_zero(self):
        self.assertEqual(self.model.pitcher_score({}), 0.0)

    def test_full_formula(self):
        p = {"era": 3.0, "whip": 1.2, "k9": 9.0, "recentEra": 2.5}
        expected = ((1 / 3.1) * 2.0 + (1 / 1.3) * 1.0
                    + 9.0 * 0.1 + (1 / 2.6) * 0.5)
        self.assertAlmostEqual(self.model.pitcher_score(p), expected, places=9)

    def test_negative_values_are_skipped(self):
        # -1 sentinel means "unknown"; only k9 should contribute.
        p = {"era": -1, "whip": -1, "k9": 8.0, "recentEra": -1}
        self.assertAlmostEqual(self.model.pitcher_score(p), 8.0 * 0.1, places=9)

    def test_missing_keys_treated_as_unknown(self):
        self.assertEqual(self.model.pitcher_score({"era": 3.0,
                                                   "whip": -1, "k9": -1,
                                                   "recentEra": -1}),
                         (1 / 3.1) * 2.0)


class HomeWinProbabilityTests(unittest.TestCase):
    def setUp(self):
        self.model = PredictionModel(config.DEFAULT_WEIGHTS)

    def test_identical_teams_home_favored_by_hfa(self):
        p = self.model.home_win_probability(TEAM, TEAM, None, None)
        self.assertGreater(p, 0.5)

    def test_probabilities_are_complementary(self):
        a = dict(TEAM, runsPerGame=6.0)
        p_home = self.model.home_win_probability(TEAM, a, None, None)
        # away stronger offensively -> home below the HFA-only baseline
        self.assertTrue(0.0 < p_home < 1.0)

    def test_exact_value_for_identical_teams(self):
        p = self.model.home_win_probability(TEAM, TEAM, None, None)
        offense = 4.5 * 0.4 + 0.320 * 50 + 0.410 * 30
        defense = (1.0 / (4.0 + 0.1)) * 0.985 * 100
        home = (offense * 0.6 + defense * 0.4) * 1.05
        away = (offense * 0.6 + defense * 0.4)
        self.assertAlmostEqual(p, home / (home + away), places=9)

    def test_zero_strength_returns_half(self):
        empty = {}
        self.assertEqual(self.model.home_win_probability(empty, empty, None, None), 0.5)

    def test_clamped_to_ceiling(self):
        strong = dict(TEAM, runsPerGame=50.0, sluggingPercentage=3.0)
        weak = {}
        p = self.model.home_win_probability(strong, weak, None, None)
        self.assertLessEqual(p, 0.99)
        self.assertGreater(p, 0.9)

    def test_clamped_to_floor(self):
        strong = dict(TEAM, runsPerGame=50.0, sluggingPercentage=3.0)
        weak = {}
        p = self.model.home_win_probability(weak, strong, None, None)
        self.assertGreaterEqual(p, 0.01)

    def test_pitcher_term_shifts_probability(self):
        weights = dict(config.DEFAULT_WEIGHTS)
        weights["pitcherEraWeight"] = 5.0
        model = PredictionModel(weights)
        ace = {"era": 1.5, "whip": -1, "k9": -1, "recentEra": -1}
        base = model.home_win_probability(TEAM, TEAM, None, None)
        with_ace = model.home_win_probability(TEAM, TEAM, ace, None)
        self.assertGreater(with_ace, base)


if __name__ == "__main__":
    unittest.main()
