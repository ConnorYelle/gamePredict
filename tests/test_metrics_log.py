"""Tests for mlb.metrics_log — the append-only metrics history."""

import math
import tempfile
import unittest
from pathlib import Path

from mlb import metrics_log

SAMPLE = {
    "games_evaluated": 1972,
    "accuracy": 0.5868,
    "home_field_baseline": 0.5289,
    "average_winner_prob": 0.55,
    "brier_score": 0.2353,
    "log_loss": 0.6624,
}


class BuildRecordTests(unittest.TestCase):
    def test_maps_metrics_and_metadata(self):
        rec = metrics_log.build_record(
            SAMPLE, {"probScale": 0.1}, note="added bullpen",
            season=2025, window=("2025-05-01", "2025-10-31"),
            use_pitchers=True, commit="abc123")
        self.assertEqual(rec["note"], "added bullpen")
        self.assertEqual(rec["git"], "abc123")
        self.assertEqual(rec["games"], 1972)
        self.assertAlmostEqual(rec["brier"], 0.2353)
        self.assertAlmostEqual(rec["log_loss"], 0.6624)
        self.assertEqual(rec["window"], ["2025-05-01", "2025-10-31"])
        self.assertEqual(rec["weights"], {"probScale": 0.1})
        self.assertTrue(rec["timestamp"].endswith("Z"))


class LogAndLoadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "history.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_append_then_load_round_trip(self):
        metrics_log.log_run(SAMPLE, {"a": 1}, path=self.path, note="first", commit="c1")
        metrics_log.log_run(SAMPLE, {"a": 2}, path=self.path, note="second", commit="c2")
        history = metrics_log.load_history(self.path)
        self.assertEqual([r["note"] for r in history], ["first", "second"])
        self.assertEqual([r["weights"]["a"] for r in history], [1, 2])

    def test_load_missing_file_is_empty(self):
        self.assertEqual(metrics_log.load_history(self.path), [])

    def test_load_skips_malformed_lines(self):
        self.path.write_text('{"note": "ok", "brier": 0.24}\nnot json\n\n',
                             encoding="utf-8")
        history = metrics_log.load_history(self.path)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["note"], "ok")


class FormatTableTests(unittest.TestCase):
    def test_empty_history_message(self):
        self.assertIn("No metrics history", metrics_log.format_table([]))

    def test_shows_brier_delta_between_rows(self):
        rows = [
            metrics_log.build_record(dict(SAMPLE, brier_score=0.2400),
                                     {}, note="baseline", commit="c1"),
            metrics_log.build_record(dict(SAMPLE, brier_score=0.2353),
                                     {}, note="bullpen", commit="c2"),
        ]
        table = metrics_log.format_table(rows)
        self.assertIn("baseline", table)
        self.assertIn("bullpen", table)
        self.assertIn("-0.0047", table)  # Brier improved by 0.0047

    def test_missing_numbers_render_as_dash(self):
        rec = metrics_log.build_record({}, {}, note="incomplete", commit="c1")
        table = metrics_log.format_table([rec])
        self.assertIn("incomplete", table)
        self.assertIn("-", table)  # missing metrics render as an ASCII dash
        self.assertTrue(table.isascii())  # safe for cp1252 Windows consoles


class GitCommitTests(unittest.TestCase):
    def test_returns_string(self):
        # Best-effort: a string either way (real sha in a repo, "" otherwise).
        self.assertIsInstance(metrics_log.git_commit(), str)


if __name__ == "__main__":
    unittest.main()
