"""Tests for mlb.results_archive — per-day score archive and helpers."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from mlb import results_archive as ra


class ParseDateTests(unittest.TestCase):
    def test_iso_date(self):
        self.assertEqual(ra.parse_date("2026-05-29"), datetime(2026, 5, 29))

    def test_bad_date_raises(self):
        with self.assertRaises(ValueError):
            ra.parse_date("05/29/2026")


class DaterangeTests(unittest.TestCase):
    def test_inclusive_range(self):
        days = list(ra.daterange(datetime(2026, 5, 1), datetime(2026, 5, 3)))
        self.assertEqual([d.day for d in days], [1, 2, 3])

    def test_single_day(self):
        days = list(ra.daterange(datetime(2026, 5, 1), datetime(2026, 5, 1)))
        self.assertEqual(len(days), 1)

    def test_empty_when_start_after_end(self):
        self.assertEqual(list(ra.daterange(datetime(2026, 5, 5),
                                           datetime(2026, 5, 1))), [])


ROWS = [
    {"date": "2026-05-29", "away": "Atlanta Braves", "home": "Cincinnati Reds",
     "away_score": 8, "home_score": 3, "winner": "Atlanta Braves",
     "home_sp": "Chris Paddack", "away_sp": "Grant Holmes"},
]


class ResultsArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.archive = ra.ResultsArchive(root=Path(self.tmp.name))
        self.date = datetime(2026, 5, 29)

    def tearDown(self):
        self.tmp.cleanup()

    def test_day_dir_naming(self):
        self.assertTrue(str(self.archive.day_dir(self.date)).endswith("05-29-26"))

    def test_save_then_load_round_trip(self):
        path = self.archive.save_scores(ROWS, self.date)
        self.assertTrue(path.exists())
        loaded = self.archive.load_scores(self.date)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["winner"], "Atlanta Braves")
        self.assertEqual(loaded[0]["away"], "Atlanta Braves")

    def test_save_writes_only_known_fields(self):
        rows = [dict(ROWS[0], extra="ignore me")]
        self.archive.save_scores(rows, self.date)
        loaded = self.archive.load_scores(self.date)
        self.assertNotIn("extra", loaded[0])

    def test_load_missing_returns_empty(self):
        self.assertEqual(self.archive.load_scores(datetime(2000, 1, 1)), [])

    def test_snapshot_copies_existing_files(self):
        src = Path(self.tmp.name) / "predictions.txt"
        src.write_text("hello", encoding="utf-8")
        missing = Path(self.tmp.name) / "nope.txt"
        out_dir = self.archive.snapshot(self.date, src, missing)
        self.assertTrue((out_dir / "predictions.txt").exists())
        self.assertFalse((out_dir / "nope.txt").exists())

    def test_load_predictions_text_round_trip(self):
        src = Path(self.tmp.name) / "predictions.txt"
        src.write_text("Toronto Blue Jays 63.1%", encoding="utf-8")
        self.archive.snapshot(self.date, src)
        self.assertIn("63.1%", self.archive.load_predictions_text(self.date))

    def test_load_predictions_text_missing_returns_none(self):
        self.assertIsNone(self.archive.load_predictions_text(self.date))

    def test_available_dates_lists_days_chronologically(self):
        # Save out of order; available_dates returns ascending ISO strings.
        self.archive.save_scores(ROWS, datetime(2026, 5, 29))
        self.archive.save_scores(ROWS, datetime(2026, 4, 30))
        # A predictions-only day (results not archived yet) is still listed, so
        # a just-played day shows up in the picker.
        snap_only = Path(self.tmp.name) / "predictions.txt"
        snap_only.write_text("x", encoding="utf-8")
        self.archive.snapshot(datetime(2026, 6, 1), snap_only)
        self.assertEqual(self.archive.available_dates(),
                         ["2026-04-30", "2026-05-29", "2026-06-01"])

    def test_available_dates_ignores_folders_without_data(self):
        # A dated folder with neither scores nor predictions is not reviewable.
        (self.archive.base_dir / "07-04-26").mkdir(parents=True)
        self.archive.save_scores(ROWS, datetime(2026, 5, 29))
        self.assertEqual(self.archive.available_dates(), ["2026-05-29"])

    def test_available_dates_empty_when_no_archive(self):
        empty = ra.ResultsArchive(root=Path(self.tmp.name) / "elsewhere")
        self.assertEqual(empty.available_dates(), [])


class FakeApi:
    def __init__(self, rows):
        self._rows = rows

    def final_scores(self, date_str):
        return self._rows


class ArchiveDayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.archive = ra.ResultsArchive(root=Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_writes_when_games_exist(self):
        rows, path = ra.archive_day(FakeApi(ROWS), datetime(2026, 5, 29), self.archive)
        self.assertEqual(len(rows), 1)
        self.assertIsNotNone(path)
        self.assertTrue(path.exists())

    def test_no_path_when_empty(self):
        rows, path = ra.archive_day(FakeApi([]), datetime(2026, 5, 29), self.archive)
        self.assertEqual(rows, [])
        self.assertIsNone(path)


if __name__ == "__main__":
    unittest.main()
