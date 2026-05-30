"""End-to-end CLI tests for validate_predictions.py via subprocess.

Exercises the script's argument handling and the offline grading modes (no
network), so the real entrypoint users invoke is covered.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "validate_predictions.py"

PREDICTIONS = "Boston Red Sox 60.0%\nNew York Yankees 40.0%\n"
GAMES = "Boston Red Sox | New York Yankees\n"
RESULTS_CSV = (
    "date,away,home,away_score,home_score,winner,home_sp,away_sp\n"
    "2026-05-30,New York Yankees,Boston Red Sox,3,5,Boston Red Sox,H,A\n"
)


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          cwd=str(ROOT), capture_output=True, text=True)


class ValidateCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.preds = self.dir / "predictions.txt"
        self.games = self.dir / "games.txt"
        self.results = self.dir / "final_scores.csv"
        self.preds.write_text(PREDICTIONS, encoding="utf-8")
        self.games.write_text(GAMES, encoding="utf-8")
        self.results.write_text(RESULTS_CSV, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_slate_validation_mode(self):
        res = run("--predictions", str(self.preds), "--games", str(self.games))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Validation Results", res.stdout)
        self.assertIn("accuracy", res.stdout)

    def test_results_mode(self):
        res = run("--predictions", str(self.preds), "--results", str(self.results))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Validation vs. Archived Scores", res.stdout)
        self.assertIn("matched: 1", res.stdout)

    def test_missing_predictions_file_reports(self):
        res = run("--predictions", str(self.dir / "nope.txt"),
                  "--games", str(self.games))
        self.assertIn("Missing predictions file", res.stdout)

    def test_missing_results_file_reports(self):
        res = run("--predictions", str(self.preds),
                  "--results", str(self.dir / "nope.csv"))
        self.assertIn("Missing results file", res.stdout)


if __name__ == "__main__":
    unittest.main()
