"""Tests for mlb.slate_grader — parsing, fuzzy team matching, and grading."""

import tempfile
import unittest
from pathlib import Path

from mlb import slate_grader as sg


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return str(path)


class ParsePredictionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_pairs_consecutive_lines(self):
        path = write(self.dir / "p.txt",
                     "Boston Red Sox 60.0%\nNew York Yankees 40.0%\n")
        games = sg.parse_predictions(path)
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["team_a"], "Boston Red Sox")
        self.assertAlmostEqual(games[0]["prob_a"], 0.60)
        self.assertAlmostEqual(games[0]["prob_b"], 0.40)

    def test_ignores_non_percent_lines(self):
        path = write(self.dir / "p.txt",
                     "=== Header ===\nBoston Red Sox 60.0%\n"
                     "New York Yankees 40.0%\nFavorite: Boston\n")
        self.assertEqual(len(sg.parse_predictions(path)), 1)

    def test_drops_unpaired_trailing_line(self):
        path = write(self.dir / "p.txt",
                     "A Team 55%\nB Team 45%\nLone Team 50%\n")
        self.assertEqual(len(sg.parse_predictions(path)), 1)


class ParseGamesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_pipe_format(self):
        path = write(self.dir / "g.txt", "Boston Red Sox | New York Yankees\n")
        self.assertEqual(sg.parse_games(path),
                         [("Boston Red Sox", "New York Yankees")])

    def test_at_format(self):
        path = write(self.dir / "g.txt", "New York Yankees @ Boston Red Sox\n")
        self.assertEqual(sg.parse_games(path),
                         [("New York Yankees", "Boston Red Sox")])

    def test_blank_lines_skipped(self):
        path = write(self.dir / "g.txt", "\nA | B\n\n")
        self.assertEqual(len(sg.parse_games(path)), 1)


class MatchTeamTests(unittest.TestCase):
    def test_normalize_strips_punctuation(self):
        self.assertEqual(sg.normalize("St. Louis Cardinals!"), "st louis cardinals")

    def test_exact_match(self):
        self.assertTrue(sg.match_team("Athletics", "Athletics"))

    def test_token_overlap_match(self):
        self.assertTrue(sg.match_team("Boston Red Sox", "Red Sox"))

    def test_substring_match(self):
        self.assertTrue(sg.match_team("Yankees", "New York Yankees"))

    def test_single_shared_token_is_not_a_match(self):
        self.assertFalse(sg.match_team("Chicago Cubs", "Chicago White Sox"))


class ValidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_correct_pick(self):
        preds = write(self.dir / "p.txt",
                      "Boston Red Sox 60.0%\nNew York Yankees 40.0%\n")
        games = write(self.dir / "g.txt", "Boston Red Sox | New York Yankees\n")
        res = sg.validate(preds, games)
        self.assertEqual(res["matched"], 1)
        self.assertEqual(res["accuracy"], 1.0)
        self.assertAlmostEqual(res["brier_score"], 0.16)

    def test_incorrect_pick(self):
        preds = write(self.dir / "p.txt",
                      "Boston Red Sox 60.0%\nNew York Yankees 40.0%\n")
        # First token on the games line is treated as the winner -> Yankees won.
        games = write(self.dir / "g.txt", "New York Yankees | Boston Red Sox\n")
        res = sg.validate(preds, games)
        self.assertEqual(res["accuracy"], 0.0)


class GradeAgainstResultsTests(unittest.TestCase):
    def test_order_independent_grading(self):
        pred_games = [{"team_a": "Boston Red Sox", "prob_a": 0.60,
                       "team_b": "New York Yankees", "prob_b": 0.40}]
        results = [{"home": "New York Yankees", "away": "Boston Red Sox",
                    "winner": "Boston Red Sox"}]
        res = sg.grade_against_results(pred_games, results)
        self.assertEqual(res["matched"], 1)
        self.assertEqual(res["accuracy"], 1.0)
        self.assertAlmostEqual(res["average_winner_prob"], 0.60)

    def test_unmatched_results_are_skipped(self):
        pred_games = [{"team_a": "Boston Red Sox", "prob_a": 0.60,
                       "team_b": "New York Yankees", "prob_b": 0.40}]
        results = [{"home": "Chicago Cubs", "away": "Miami Marlins",
                    "winner": "Chicago Cubs"}]
        res = sg.grade_against_results(pred_games, results)
        self.assertEqual(res["matched"], 0)
        self.assertEqual(res["accuracy"], 0.0)

    def test_missing_winner_skipped(self):
        pred_games = [{"team_a": "A", "prob_a": 0.5, "team_b": "B", "prob_b": 0.5}]
        results = [{"home": "A", "away": "B", "winner": ""}]
        self.assertEqual(sg.grade_against_results(pred_games, results)["matched"], 0)


if __name__ == "__main__":
    unittest.main()
