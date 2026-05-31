"""Tests for mlb.raw_stats — the TeamStandard*.txt format the C++ engine reads.

These pin the column contract (indices) and the two-filler-row convention the
C++ loader depends on (it discards the final two rows), so a team is never
silently dropped.
"""

import tempfile
import unittest
from pathlib import Path

from mlb import raw_stats

TEAMS = [
    {"name": "Boston Red Sox", "runsPerGame": 4.53, "battingAvg": 0.265,
     "onBasePercentage": 0.330, "sluggingPercentage": 0.430, "homeRuns": 60,
     "runsAllowedPerGame": 4.02, "fieldingPercentage": 0.985},
    {"name": "New York Yankees", "runsPerGame": 5.10, "battingAvg": 0.255,
     "onBasePercentage": 0.322, "sluggingPercentage": 0.445, "homeRuns": 71,
     "runsAllowedPerGame": 3.80, "fieldingPercentage": 0.982},
]


class BattingRowsTests(unittest.TestCase):
    def setUp(self):
        self.rows = raw_stats.batting_rows(TEAMS)

    def test_header_first(self):
        self.assertEqual(self.rows[0], raw_stats.BATTING_HEADER)

    def test_row_count_is_header_plus_teams_plus_two_filler(self):
        self.assertEqual(len(self.rows), 1 + len(TEAMS) + 2)

    def test_two_trailing_filler_rows_so_loader_keeps_all_teams(self):
        # The C++ loader processes rows[1 .. len-3]; the last two are discarded.
        self.assertEqual(self.rows[-2][raw_stats.B_TM], "League Average")
        self.assertEqual(self.rows[-1][raw_stats.B_TM], "League Totals")
        # First real team is at index 1 and survives the discard.
        self.assertEqual(self.rows[1][raw_stats.B_TM], "Boston Red Sox")

    def test_values_land_at_expected_indices(self):
        row = self.rows[1]
        self.assertEqual(row[raw_stats.B_RG], "4.53")
        self.assertEqual(row[raw_stats.B_HR], "60")
        self.assertEqual(row[raw_stats.B_BA], "0.265")
        self.assertEqual(row[raw_stats.B_OBP], "0.330")
        self.assertEqual(row[raw_stats.B_SLG], "0.430")

    def test_rows_have_full_width(self):
        for row in self.rows:
            self.assertEqual(len(row), len(raw_stats.BATTING_HEADER))


class FieldingRowsTests(unittest.TestCase):
    def setUp(self):
        self.rows = raw_stats.fielding_rows(TEAMS)

    def test_values_land_at_expected_indices(self):
        row = self.rows[1]
        self.assertEqual(row[raw_stats.F_TM], "Boston Red Sox")
        self.assertEqual(row[raw_stats.F_RAG], "4.02")
        self.assertEqual(row[raw_stats.F_FLD], "0.985")

    def test_filler_rows_present(self):
        self.assertEqual(self.rows[-2][raw_stats.F_TM], "League Average")
        self.assertEqual(self.rows[-1][raw_stats.F_TM], "League Totals")

    def test_missing_fields_default_to_zero(self):
        rows = raw_stats.fielding_rows([{"name": "Sparse Team"}])
        self.assertEqual(rows[1][raw_stats.F_RAG], "0.00")
        self.assertEqual(rows[1][raw_stats.F_FLD], "0.000")


class BullpenRowsTests(unittest.TestCase):
    def test_header_and_values(self):
        rows = raw_stats.bullpen_rows([
            {"name": "Boston Red Sox", "bullpenEra": 3.45, "bullpenKbb": 2.10},
        ])
        self.assertEqual(rows[0], raw_stats.BULLPEN_HEADER)
        self.assertEqual(rows[1], ["Boston Red Sox", "3.450", "2.100"])

    def test_unknown_values_written_blank(self):
        # Missing key and the -1 sentinel both render as an empty cell.
        rows = raw_stats.bullpen_rows([{"name": "Sparse", "bullpenEra": -1.0}])
        self.assertEqual(rows[1], ["Sparse", "", ""])


class WriteAndDetectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_write_creates_both_files(self):
        batting, fielding = raw_stats.write_stat_files(TEAMS, self.dir)
        self.assertTrue(batting.exists() and fielding.exists())
        self.assertEqual(batting.name, "TeamStandardBatting.txt")
        self.assertEqual(fielding.name, "TeamFielding.txt")

    def test_is_populated_false_when_missing(self):
        self.assertFalse(raw_stats.is_populated(self.dir))

    def test_is_populated_true_after_write(self):
        raw_stats.write_stat_files(TEAMS, self.dir)
        self.assertTrue(raw_stats.is_populated(self.dir))

    def test_round_trip_is_comma_separated_with_header(self):
        batting, _ = raw_stats.write_stat_files(TEAMS, self.dir)
        lines = batting.read_text(encoding="utf-8").splitlines()
        self.assertTrue(lines[0].startswith("Tm,"))
        self.assertEqual(lines[1].split(",")[0], "Boston Red Sox")


if __name__ == "__main__":
    unittest.main()
